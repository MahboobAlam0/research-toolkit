# ─── backend/routes/query.py ──────────────────────────────────────────────────
"""
Chat / RAG endpoint.

POST /api/chat/query  — answer a question using saved papers
"""
import logging
from fastapi import APIRouter, HTTPException
from models.schemas import ChatQuery, ChatResponse
from services.rag_pipeline import rag_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/query", response_model=ChatResponse)
async def query_papers(req: ChatQuery):
    """
    RAG-powered Q&A over the user's paper library.

    - Embeds the query
    - Retrieves top-k relevant chunks from Qdrant
    - Generates a cited answer with Groq LLM
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    try:
        answer, sources = await rag_query(
            query=req.query,
            history=req.history,
            top_k=req.top_k,
        )
    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail=f"RAG error: {e}")

    return ChatResponse(answer=answer, sources=sources)
