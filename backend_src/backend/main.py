import os
import logging
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel

from backend.models import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    ConversationOut,
    MessageOut,
    ToolOut,
)
from backend.db_logger import (
    init_db,
    log_message,
    log_feedback,
    load_conversations_for_token,
    load_messages_for_conversation,
    get_messages_for_history,
    create_new_conversation,
    is_valid_token,
)
from backend.auth_router import auth_router
from backend.llm_utils import get_agent_executor, get_chat_response, AVAILABLE_PROVIDERS
from backend.mcp_client import MCPClient
from backend import config

from backend.auth_utils import get_current_user

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# --- State Management ---
app_state: Dict[str, Any] = {}


class ServerToggleRequest(BaseModel):
    """Request schema for activating/deactivating MCP servers."""
    active_servers: List[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager to initialize and clean up resources.

    - Initializes the database and MCP client on startup.
    - Clears application state on shutdown.
    """
    # --- Startup ---
    logger.info("Application startup...")
    init_db()

    try:
        server_config: Dict[str, Dict[str, str]] = {
            name: {"url": f"{details['url']}/sse", "transport": "sse"}
            for name, details in config.MCP_SERVER_URLS.items()
        }
        logger.info(f"Initializing MCP client with servers: {server_config}")
        app_state["mcp_client"] = MCPClient(server_config)
    except Exception as e:
        logger.exception(f"Fatal error during MCP client initialization: {e}")
        app_state["mcp_client"] = None

    yield

    # --- Shutdown ---
    logger.info("Application shutdown...")
    app_state.clear()


app = FastAPI(
    title="FALCON API",
    version="1.0.0",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


# --- Dependencies ---
def get_mcp_client() -> MCPClient:
    """
    Dependency to get the initialized MCP client.

    Returns:
        MCPClient: The initialized MCP client instance.

    Raises:
        HTTPException: If the MCP client is unavailable.
    """
    client = app_state.get("mcp_client")
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="MCP services are unavailable at the moment."
        )
    return client


# --- API Endpoints ---
@app.get("/tools", response_model=List[ToolOut])
async def get_tools(client: MCPClient = Depends(get_mcp_client)) -> List[ToolOut]:
    """
    List all available tools from connected MCP servers.

    Args:
        client: MCPClient dependency injected by FastAPI.

    Returns:
        List[ToolOut]: List of available tools.

    Raises:
        HTTPException: If tools cannot be retrieved.
    """
    try:
        tools = await client.get_tools()
        return [ToolOut(name=tool.name) for tool in tools]
    except Exception as e:
        logger.error(f"Failed to get tools from MCP client: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve tools.")


@app.get("/servers")
async def get_mcp_servers() -> Dict[str, Dict[str, str]]:
    """
    Returns the list of available MCP servers and their configurations.

    Returns:
        Dict[str, Dict[str, str]]: Dictionary of server names and configuration details.

    Raises:
        HTTPException: If the server configuration cannot be retrieved.
    """
    try:
        return config.MCP_SERVER_URLS
    except Exception as e:
        logger.error(f"Failed to load MCP servers: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve MCP servers.")


@app.post("/servers/toggle")
async def toggle_servers(
    toggle_req: ServerToggleRequest,
    client: MCPClient = Depends(get_mcp_client),
) -> Dict[str, Any]:
    """
    Activates or deactivates specific MCP servers dynamically.

    Args:
        toggle_req: Request containing list of active servers.
        client: MCPClient dependency.

    Returns:
        Dict[str, Any]: Status and list of active servers.

    Raises:
        HTTPException: If server toggling fails.
    """
    try:
        client.set_active_servers(toggle_req.active_servers)
        return {"status": "ok", "active_servers": toggle_req.active_servers}
    except Exception as e:
        logger.error(f"Failed to toggle servers: {e}")
        raise HTTPException(status_code=500, detail="Could not toggle MCP servers.")


@app.get("/models")
def get_models() -> Dict[str, List[str]]:
    """
    Returns a dictionary of available models grouped by provider.

    Returns:
        Dict[str, List[str]]: Available LLM models per provider.
    """
    return AVAILABLE_PROVIDERS


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    chat_req: ChatRequest,
    client: MCPClient = Depends(get_mcp_client),
    current_user: str = Depends(get_current_user)
) -> ChatResponse:
    """
    Handles a chat request, runs the agent, and returns a response.

    Args:
        chat_req: ChatRequest object containing user input and settings.
        client: MCPClient dependency.

    Returns:
        ChatResponse: The assistant's response and conversation ID.

    Raises:
        HTTPException: If token is invalid or processing fails.
    """
    tools = await client.get_tools() if chat_req.use_mcp else []

    agent_executor = get_agent_executor(
        provider=chat_req.provider,
        model=chat_req.model,
        api_key=chat_req.api_key,
        tools=tools,
    )

    history = get_messages_for_history(chat_req.conversation_id)

    try:
        answer, conv_id = await get_chat_response(
            agent_executor=agent_executor,
            prompt=chat_req.prompt,
            token=current_user,
            conv_id=chat_req.conversation_id,
            history=history,
        )
        return ChatResponse(answer=answer, conversation_id=conv_id)
    except Exception as e:
        logger.exception(f"Error during chat processing for token {chat_req.token}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
def feedback_endpoint(feedback_req: FeedbackRequest) -> Dict[str, str]:
    """
    Logs user feedback for a specific message.

    Args:
        feedback_req: FeedbackRequest containing message ID and feedback.

    Returns:
        Dict[str, str]: Status of the logging operation.
    """
    log_feedback(feedback_req.message_id, feedback_req.feedback)
    return {"status": "ok"}


@app.get("/conversations", response_model=List[ConversationOut])
def list_conversations(current_user: str = Depends(get_current_user)) -> List[ConversationOut]:
    """
    Lists all conversations for a given user token.

    Args:
        current_user: User str to identify the user.

    Returns:
        List[ConversationOut]: List of conversations.
    """
    return load_conversations_for_token(current_user)


@app.get("/messages/{conversation_id}", response_model=List[MessageOut])
def get_messages(conversation_id: str) -> List[MessageOut]:
    """
    Retrieves all messages for a specific conversation.

    Args:
        conversation_id: ID of the conversation to fetch messages for.

    Returns:
        List[MessageOut]: List of messages in the conversation.
    """
    return load_messages_for_conversation(conversation_id)


@app.post("/conversations/new", response_model=Dict[str, str])
def new_conversation(current_user: str = Depends(get_current_user)) -> Dict[str, str]:
    """
    Creates a new, empty conversation for a user.

    Args:
        token: User token for which to create a conversation.

    Returns:
        Dict[str, str]: Newly created conversation ID.

    Raises:
        HTTPException: If token is invalid or conversation creation fails.
    """
    conversation_id = create_new_conversation(current_user)
    if not conversation_id:
        raise HTTPException(status_code=500, detail="Could not create new conversation.")
    return {"conversation_id": conversation_id}
