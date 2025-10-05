from typing import List, Optional
from pydantic import BaseModel

# --- Request Models ---

class ChatRequest(BaseModel):
    token: str
    prompt: str
    provider: str
    model: str
    api_key: Optional[str] = ""
    use_mcp: bool = True
    conversation_id: Optional[str] = None

class FeedbackRequest(BaseModel):
    message_id: int
    feedback: int # Using 1 for thumbs up, -1 for thumbs down

# --- Response Models ---

class ChatResponse(BaseModel):
    answer: str
    conversation_id: str

class ConversationOut(BaseModel):
    id: str
    started_at: str
    class Config:
        orm_mode = True

class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    feedback: Optional[int] = None
    class Config:
        orm_mode = True

class ToolOut(BaseModel):
    name: str

