# ─── backend/routes/search.py ──────────────────────────────────────────────────
"""
Semantic paper search — fast retrieval without LLM generation.

GET /api/papers/search?q=<query>&top_k=10

Returns saved papers ranked by semantic similarity to the query.
Much faster than RAG chat for "do I have anything about X?" lookups.
"""
from fastapi import APIRouter, Query
from services.rag_pipeline import retrieve

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("/search")
async def semantic_search(
    q: str = Query(..., min_length=1, max_length=500, description="Natural-language search query"),
    top_k: int = Query(10, ge=1, le=50, description="Max results to return"),
):
    """
    Search saved papers by semantic similarity.

    Returns deduplicated papers (one entry per paper, best-matching chunk wins)
    ranked by relevance score. Does NOT invoke the LLM — typically <100 ms.
    """
    chunks = await retrieve(q, top_k=top_k)

    # Deduplicate by paper_id, keeping the highest-scoring chunk per paper
    best: dict[str, dict] = {}
    for chunk in chunks:
        pid = chunk["paper_id"]
        if pid not in best or chunk["score"] > best[pid]["score"]:
            best[pid] = chunk

    ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)

    return {
        "query": q,
        "total": len(ranked),
        "results": [
            {
                "title": r["title"],
                "url": r["url"],
                "source": r["source"],
                "paper_id": r["paper_id"],
                "relevance_score": round(r["score"], 4),
                "excerpt": (r["text"][:280] + "…") if len(r["text"]) > 280 else r["text"],
            }
            for r in ranked
        ],
    }
