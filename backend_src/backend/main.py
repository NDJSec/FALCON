import os
import logging
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Correctly import from the backend package
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
from backend.llm_utils import get_agent_executor, get_chat_response, AVAILABLE_PROVIDERS
from backend.mcp_client import MCPClient
from backend import config

# Correctly configure logging by reading from an environment variable
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# --- State Management ---
# This dictionary will hold the initialized MCP client.
app_state: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Application startup...")
    init_db()

    # Initialize the Multi-Server MCP Client on startup.
    try:
        # FIX: Append the required /sse endpoint to the MCP server URLs from config.
        server_config = {
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


app = FastAPI(title="FALCON API", lifespan=lifespan)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Dependencies ---
def get_mcp_client() -> MCPClient:
    """Dependency to get the initialized MCP client."""
    client = app_state.get("mcp_client")
    if client is None:
        raise HTTPException(
            status_code=503, detail="MCP services are unavailable at the moment."
        )
    return client


# --- API Endpoints ---
@app.get("/tools", response_model=List[ToolOut])
async def get_tools(client: MCPClient = Depends(get_mcp_client)):
    """Lists all available tools from the connected MCP servers."""
    try:
        tools = await client.get_tools()
        return [ToolOut(name=tool.name) for tool in tools]
    except Exception as e:
        logger.error(f"Failed to get tools from MCP client: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve tools.")


@app.get("/models")
def get_models() -> Dict[str, List[str]]:
    """Returns a dictionary of available models grouped by provider."""
    return AVAILABLE_PROVIDERS


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_req: ChatRequest, client: MCPClient = Depends(get_mcp_client)):
    """Handles a chat request, processes it, and returns a response."""
    if not is_valid_token(chat_req.token):
        raise HTTPException(status_code=403, detail="Invalid token")

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
            token=chat_req.token,
            conv_id=chat_req.conversation_id,
            history=history,
        )
        return ChatResponse(answer=answer, conversation_id=conv_id)
    except Exception as e:
        logger.exception(f"Error during chat processing for token {chat_req.token}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
def feedback_endpoint(feedback_req: FeedbackRequest):
    """Logs user feedback for a specific message."""
    log_feedback(feedback_req.message_id, feedback_req.feedback)
    return {"status": "ok"}


@app.get("/conversations/{token}", response_model=List[ConversationOut])
def list_conversations(token: str):
    """Lists all conversations for a given user token."""
    if not is_valid_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")
    conversations = load_conversations_for_token(token)
    return conversations

@app.get("/messages/{conversation_id}", response_model=List[MessageOut])
def get_messages(conversation_id: str):
    """Retrieves all messages for a specific conversation."""
    messages = load_messages_for_conversation(conversation_id)
    return messages


@app.post("/conversations/new/{token}", response_model=Dict[str, str])
def new_conversation(token: str):
    """Creates a new, empty conversation for a user."""
    if not is_valid_token(token):
        raise HTTPException(status_code=403, detail="Invalid token")
    conversation_id = create_new_conversation(token)
    if not conversation_id:
        raise HTTPException(status_code=500, detail="Could not create new conversation.")
    return {"conversation_id": conversation_id}
