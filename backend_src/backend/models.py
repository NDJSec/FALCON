from typing import List, Optional
from pydantic import BaseModel

# --- Request Models ---

class ChatRequest(BaseModel):
    """
    Request model for sending a chat message to the assistant.

    Attributes:
        token: User authentication token.
        prompt: The user's input message.
        provider: LLM provider to use (e.g., "OpenAI", "Gemini").
        model: Model name to use from the provider.
        api_key: Optional API key for the provider.
        use_mcp: Whether to fetch tools from MCP servers.
        conversation_id: Optional conversation ID for ongoing chats.
    """
    token: str
    prompt: str
    provider: str
    model: str
    api_key: Optional[str] = ""
    use_mcp: bool = True
    conversation_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "token": "abc123",
                "prompt": "Summarize the latest FALCON system log activity.",
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "sk-xxxxxx",
                "use_mcp": True,
                "conversation_id": "conv_001"
            }
        }


class FeedbackRequest(BaseModel):
    """
    Request model for submitting feedback on a message.

    Attributes:
        message_id: ID of the message being rated.
        feedback: Feedback value (1 for thumbs up, -1 for thumbs down).
    """
    message_id: int
    feedback: int  # 1 for thumbs up, -1 for thumbs down

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": 42,
                "feedback": 1
            }
        }

# --- Response Models ---

class ChatResponse(BaseModel):
    """
    Response model returned after processing a chat request.

    Attributes:
        answer: The assistant's response text.
        conversation_id: The conversation ID associated with this response.
    """
    answer: str
    conversation_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The FALCON system successfully analyzed 12 server logs.",
                "conversation_id": "conv_001"
            }
        }


class ConversationOut(BaseModel):
    """
    Represents a conversation record for output to the frontend.

    Attributes:
        id: Unique identifier for the conversation.
        started_at: Timestamp when the conversation started.
    """
    id: str
    started_at: str

    class Config:
        orm_mode = True
        json_schema_extra = {
            "example": {
                "id": "conv_001",
                "started_at": "2025-10-06T18:42:00Z"
            }
        }


class MessageOut(BaseModel):
    """
    Represents a message record for output to the frontend.

    Attributes:
        id: Unique identifier for the message.
        role: Role of the sender ('user' or 'assistant').
        content: The message content.
        feedback: Optional feedback value (1 or -1).
    """
    id: int
    role: str
    content: str
    feedback: Optional[int] = None

    class Config:
        orm_mode = True
        json_schema_extra = {
            "example": {
                "id": 101,
                "role": "assistant",
                "content": "Here’s the summary of the last deployment logs...",
                "feedback": 1
            }
        }


class ToolOut(BaseModel):
    """
    Represents a tool available from MCP servers.

    Attributes:
        name: Name of the tool.
    """
    name: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "query_knowledge_base"
            }
        }
