import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.db_logger import log_message
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from google.api_core.exceptions import ResourceExhausted
from openai import RateLimitError, AuthenticationError

logger = logging.getLogger(name=__name__)

# --- Corrected, stable model names ---
AVAILABLE_PROVIDERS: Dict[str, List[str]] = {
    "Gemini": ["gemini-2.5-flash", "gemini-1.5-flash"],
    "OpenAI": ["gpt-4o-mini", "gpt-4o"],
}


def get_agent_executor(
    provider: str,
    model: str,
    api_key: Optional[str],
    tools: List[Any]
) -> AgentExecutor:
    """
    Initialize a LangChain agent executor with the specified provider and tools.

    Args:
        provider: The LLM provider, e.g., "Gemini" or "OpenAI".
        model: The model name to use from the provider.
        api_key: API key for the provider.
        tools: List of tools available to the agent.

    Returns:
        An AgentExecutor instance configured with the specified LLM and tools.

    Raises:
        ValueError: If the provider is unsupported.
    """
    if provider == "Gemini":
        llm = ChatGoogleGenerativeAI(
            model=model, google_api_key=api_key, temperature=0.2, max_output_tokens=4096
        )
    elif provider == "OpenAI":
        llm = ChatOpenAI(model=model, api_key=api_key, temperature=0.2, max_tokens=4096)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant specializing in hardware forensics and reverse engineering.",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt_template)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


async def get_chat_response(
    agent_executor: AgentExecutor,
    prompt: str,
    token: str,
    conv_id: Optional[str],
    history: ChatMessageHistory,
) -> Tuple[str, str]:
    """
    Handles a chat request asynchronously, including history loading and logging.

    Args:
        agent_executor: The agent executor to run the prompt.
        prompt: The user input prompt.
        token: Token identifying the user session for logging.
        conv_id: Conversation ID to track the chat session.
        history: ChatMessageHistory object containing previous messages.

    Returns:
        A tuple containing the assistant's response and the conversation ID.

    Raises:
        ValueError: If `conv_id` is not provided.
    """
    final_conv_id = conv_id
    if not final_conv_id:
        raise ValueError("Conversation ID must be provided to get_chat_response.")

    # Log user message
    log_message(
        token=token,
        conversation_id=final_conv_id,
        role="user",
        content=prompt,
        source_ip="api",
    )

    # Wrap the agent with message history
    agent_with_history = RunnableWithMessageHistory(
        runnable=agent_executor,
        get_session_history=lambda session_id: history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    try:
        response: Dict[str, Any] = await agent_with_history.ainvoke(
            input={"input": prompt},
            config={"configurable": {"session_id": final_conv_id}},
        )
    except (ResourceExhausted, RateLimitError) as e:
        logger.warning(f"Rate/Quota exceeded: {e}")
        return (
            "⚠️ You have exceeded your API quota for this model. Please check billing.",
            final_conv_id,
        )
    except AuthenticationError:
        return "⚠️ Authentication Error: Invalid API Key.", final_conv_id
    except Exception as e:
        logger.exception("Unexpected error in get_chat_response")
        return (
            f"⚠️ An unexpected error occurred: {str(e)}",
            final_conv_id,
        )

    # Extract assistant output
    answer: str = response.get("output", "").strip()
    if not answer:
        steps = response.get("intermediate_steps", [])
        if steps:
            last_step = steps[-1]
            if isinstance(last_step, tuple) and len(last_step) > 1:
                tool_result = str(last_step[1])
                answer = f"(Tool call produced no final answer. Last result: {tool_result})"
        if not answer:
            answer = "⚠️ The agent did not return a response."

    # Log the assistant's response
    log_message(
        token=token,
        conversation_id=final_conv_id,
        role="assistant",
        content=answer,
        source_ip="api",
    )

    return answer, final_conv_id
