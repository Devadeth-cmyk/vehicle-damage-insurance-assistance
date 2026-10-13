from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = "default"
    company: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str = "default"
    sources: list[str] = []


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
