import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models.chat import ChatMessage, ChatRole
from app.schemas.chatbot import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


def process_chat_message(
    db: Session, user_id: int, request: ChatRequest
) -> ChatResponse:
    """Answer through the project's shared policy RAG pipeline.

    Keep this import lazy so the rest of the API can start even if optional RAG
    dependencies have not been installed. The endpoint then returns a useful
    setup error instead of silently answering from a canned generic fallback.
    """
    try:
        from rag_pipeline.scripts.rag_pipeline import answer_question
    except ImportError as exc:
        logger.exception("RAG chatbot dependencies or package are unavailable")
        raise HTTPException(
            status_code=503,
            detail="The policy knowledge base is unavailable. Install backend/rag_pipeline/requirements-rag.txt and restart the backend.",
        ) from exc

    session_id = request.session_id or "default"
    user_msg = ChatMessage(
        user_id=user_id,
        session_id=session_id,
        role=ChatRole.USER,
        content=request.message,
    )

    try:
        result = answer_question(request.message, company=request.company)
    except Exception as exc:
        logger.exception("Policy RAG query failed")
        raise HTTPException(
            status_code=503,
            detail="The policy knowledge base could not answer this question. Check that its vector index is built and the backend has been restarted.",
        ) from exc

    answer = str(result.get("answer") or "The policy knowledge base returned no answer.")
    sources = [
        (
            f"{source.get('company', 'Policy')}: {source.get('document', 'Document')} "
            f"(pp. {source.get('page_start', '?')}-{source.get('page_end', '?')})"
        )
        for source in result.get("sources", [])
    ]

    db.add(user_msg)
    db.add(
        ChatMessage(
            user_id=user_id,
            session_id=session_id,
            role=ChatRole.ASSISTANT,
            content=answer,
        )
    )
    db.commit()

    return ChatResponse(
        response=answer,
        session_id=session_id,
        sources=sources,
    )
