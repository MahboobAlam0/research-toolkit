# ─── backend/main.py ──────────────────────────────────────────────────────────
"""
ResearchKit AI — FastAPI Backend
Run locally: uvicorn main:app --reload --port 8000
Or via Docker: docker-compose up
"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.ingest      import router as ingest_router
from routes.pdf_upload  import router as pdf_router
from routes.query       import router as query_router
from routes.search      import router as search_router
from routes.synthesize  import router as synthesize_router
from routes.jd_analyzer import router as jd_router
from routes.digest      import router as digest_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s · %(levelname)s · %(name)s · %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ResearchKit AI backend starting…")
    from services.embedder import get_model
    get_model()
    logger.info("Embedding model loaded.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="ResearchKit AI",
    description=(
        "AI-powered researcher toolkit — RAG over saved papers + JD skill-gap analyzer.\n\n"
        "**Key endpoints**\n"
        "- `POST /api/papers/ingest` — embed and store a scraped paper\n"
        "- `POST /api/papers/upload-pdf` — upload and index a full PDF\n"
        "- `GET  /api/papers/search` — fast semantic search (no LLM)\n"
        "- `POST /api/papers/synthesize` — literature synthesis + gap detection\n"
        "- `POST /api/chat/query` — full RAG Q&A with citations\n"
        "- `POST /api/digest/fetch` — arXiv daily digest ranked by library relevance\n"
        "- `POST /api/jd/analyze` — skill-gap analysis against a job description\n"
        "- `GET  /api/stats` — system health & library statistics"
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# ── CORS (allow Chrome extension) ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict to your extension origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(ingest_router)
app.include_router(pdf_router)
app.include_router(search_router)
app.include_router(synthesize_router)
app.include_router(query_router)
app.include_router(jd_router)
app.include_router(digest_router)


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/api/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "ResearchKit AI", "version": app.version}


# ── System stats ───────────────────────────────────────────────────────────────
@app.get("/api/stats", tags=["system"])
async def stats():
    """
    Return library statistics and system configuration.
    Useful for dashboards, debugging, and the extension's settings view.
    """
    from services.rag_pipeline import get_qdrant, COLLECTION
    from services.llm_client import GROQ_MODEL

    client = get_qdrant()
    paper_count = 0
    total_chunks = 0
    source_counts: dict[str, int] = {}

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        info = await client.get_collection(COLLECTION)
        total_chunks = info.points_count or 0

        # Count papers (chunk_idx == 0 → one entry per paper)
        count_result = await client.count(
            collection_name=COLLECTION,
            count_filter=Filter(
                must=[FieldCondition(key="chunk_idx", match=MatchValue(value=0))]
            ),
        )
        paper_count = count_result.count

        # Source breakdown (scroll chunk-0 points only)
        offset = None
        while True:
            batch, next_offset = await client.scroll(
                collection_name=COLLECTION,
                scroll_filter=Filter(
                    must=[FieldCondition(key="chunk_idx", match=MatchValue(value=0))]
                ),
                limit=200,
                offset=offset,
                with_payload=["source"],
            )
            for point in batch:
                src = (point.payload or {}).get("source", "unknown")
                source_counts[src] = source_counts.get(src, 0) + 1
            if next_offset is None:
                break
            offset = next_offset

    except Exception:
        pass  # Qdrant not reachable — return zeros

    from services.embedder import MODEL_NAME
    return {
        "embedding_model": MODEL_NAME,
        "vector_dimensions": 768,
        "llm": GROQ_MODEL,
        "llm_provider": "Groq",
        "papers_saved": paper_count,
        "total_chunks": total_chunks,
        "papers_by_source": source_counts,
    }


# ── Root ───────────────────────────────────────────────────────────────────────
@app.get("/", tags=["system"])
async def root():
    return {
        "message": "ResearchKit AI backend",
        "docs": "/docs",
        "health": "/api/health",
        "stats": "/api/stats",
    }
