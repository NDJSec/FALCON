from typing import List, Optional
from pydantic import BaseModel


# --- Request Models ---

class ChatRequest(BaseModel):
    """Model for a user's chat message and configuration."""
    token: str
    prompt: str
    provider: str
    model: str
    api_key: Optional[str] = ""
    use_mcp: bool = True
    conversation_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Model for submitting feedback on a message."""
    message_id: int
    feedback: int  # Using 1 for thumbs up, -1 for thumbs down


# --- Response Models ---

class ChatResponse(BaseModel):
    """Model for the API's response to a chat message."""
    answer: str
    conversation_id: str


class ConversationOut(BaseModel):
    """Model for representing a single conversation in a list."""
    id: str
    started_at: str


class ToolOut(BaseModel):
    """Model for representing a single available tool."""
    name: str
