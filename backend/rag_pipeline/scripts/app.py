"""FastAPI wrapper around the RAG pipeline.

Run from the project root:
    uvicorn scripts.app:app --port 8100
"""

from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from . import rag_config as cfg
    from .rag_pipeline import answer_question
    from .search_knowledge_base import (
        KnowledgeBaseNotReady,
        UnknownCompany,
        get_companies,
        search_knowledge_base,
    )
except ImportError:
    import rag_config as cfg
    from rag_pipeline import answer_question
    from search_knowledge_base import (
        KnowledgeBaseNotReady,
        UnknownCompany,
        get_companies,
        search_knowledge_base,
    )

app = FastAPI(title="Insurance Knowledge Base API", version="2.0.0")


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=cfg.MAX_QUESTION_CHARS)


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=cfg.MAX_QUESTION_CHARS)
    top_k: int = Field(default=cfg.TOP_K, ge=1, le=20)
    company: Optional[str] = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=cfg.MAX_QUESTION_CHARS)
    company: Optional[str] = None
    history: List[Turn] = Field(default_factory=list, max_length=cfg.MAX_HISTORY_TURNS * 2)


def _kb_errors(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except KnowledgeBaseNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except UnknownCompany as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/")
def root():
    return {"status": "ok", "service": "Insurance Knowledge Base"}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "llm_configured": bool(cfg.get_groq_api_key()),
        "llm_model": cfg.GROQ_MODEL,
    }


@app.get("/companies")
def companies():
    return {"companies": _kb_errors(get_companies)}


@app.post("/search")
def search(request: SearchRequest):
    results = _kb_errors(
        search_knowledge_base, request.question, company=request.company, top_k=request.top_k
    )
    return {"question": request.question, "results": results}


@app.post("/chat")
def chat(request: ChatRequest):
    return _kb_errors(
        answer_question,
        request.question,
        company=request.company,
        history=[t.model_dump() for t in request.history],
    )
