from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.services.chatbot_service import process_chat_message

router = APIRouter()


@router.get("/health")
def chatbot_health():
    return {
        "module": "RAG chatbot",
        "status": "ready",
        "message": "Chatbot endpoint is available.",
    }


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return process_chat_message(db, current_user.id, request)