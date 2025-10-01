import os
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.db_logger import log_message
from langchain_core.messages import BaseMessage

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

from google.api_core.exceptions import ResourceExhausted
from openai import RateLimitError, AuthenticationError

logger = logging.getLogger(__name__)
# Basic config is already set in main.py, but this is a good fallback.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


AVAILABLE_PROVIDERS: Dict[str, List[str]] = {
    "Gemini": ["gemini-2.5-flash", "gemini-1.5-flash"],
    "OpenAI": ["gpt-4o-mini", "gpt-4o"],
}


def get_agent_executor(
    provider: str, model: str, api_key: str, tools: List[Any]
) -> AgentExecutor:
    """
    Initializes and returns a LangChain agent executor.
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
            ("system", "You are a helpful assistant specializing in hardware forensics and reverse engineering."),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    
    # Create the agent using the LLM, tools, and prompt
    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt_template)
    
    # Create the AgentExecutor
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def get_chat_response(
    agent_executor: AgentExecutor,
    prompt: str,
    token: str,
    conv_id: Optional[str],
    history: ChatMessageHistory,
) -> Tuple[str, str]:
    """
    Handles a chat request using the provided agent and history.
    It logs messages to the database and returns the agent's response.
    """
    # Log the user's message. The log_message function will handle creating a new
    # conversation if conv_id is None.
    final_conv_id = log_message(
        token=token,
        conversation_id=conv_id,
        role="user",
        content=prompt,
        source_ip="api", # Assuming we can get a real IP from the request later
    )

    if not final_conv_id:
        # This can happen if the token is invalid.
        logger.error(f"Failed to log user message for token: {token}")
        return "⚠️ Could not process message due to an authentication issue.", conv_id

    # The history is now passed in directly from main.py, already loaded.
    agent_with_history = RunnableWithMessageHistory(
        runnable=agent_executor,
        # The lambda now correctly uses the pre-loaded history object.
        get_session_history=lambda session_id: history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    try:
        response: Dict[str, Any] = agent_with_history.invoke(
            input={"input": prompt},
            # The session_id is used by RunnableWithMessageHistory to fetch history.
            config={"configurable": {"session_id": final_conv_id}},
        )
    except (ResourceExhausted, RateLimitError) as e:
        logger.warning(f"Rate/Quota exceeded: {e}")
        return ("⚠️ You have exceeded your API quota for this model. Please check billing.", final_conv_id)
    except AuthenticationError:
        return "⚠️ Authentication Error: Invalid API Key.", final_conv_id
    except Exception as e:
        logger.exception("Unexpected error in get_chat_response")
        return "⚠️ An unexpected error occurred during the chat. Please try again later.", final_conv_id

    answer: str = response.get("output", "").strip()
    
    # Handle cases where the agent doesn't produce a direct 'output'
    if not answer:
        steps = response.get("intermediate_steps", [])
        if steps:
            last_step = steps[-1]
            if isinstance(last_step, tuple) and len(last_step) > 1:
                tool_result = str(last_step[1])
                answer = f"(⚠️ No final answer. Last tool said: {tool_result})"
        if not answer:
            answer = "⚠️ Agent didn’t return a response."

    # Log the assistant's final response to the database
    log_message(
        token=token,
        conversation_id=final_conv_id,
        role=f"assistant", # Simpler role name
        content=answer,
        source_ip="api",
    )

    return answer, final_conv_id