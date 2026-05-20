# ─── backend/routes/digest.py ─────────────────────────────────────────────────
"""
ArXiv Daily Digest.

POST /api/digest/fetch
  Body: { interests: ["transformers", "diffusion models"], days: 3, max_results: 20 }

Algorithm:
  1. Fetch recent papers from arXiv for each interest (in parallel).
  2. Deduplicate across interests.
  3. Embed every abstract in a single batch call.
  4. Score each paper against the user's Qdrant library (top-1 cosine similarity).
     Papers semantically close to what you already read → high relevance.
  5. Return papers ranked by relevance score.

This lets users discover papers they would care about WITHOUT having to define
complex search queries — their saved library acts as an implicit interest profile.
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.arxiv_client import fetch_recent_papers
from services.embedder import embed_texts
from services.rag_pipeline import COLLECTION, get_qdrant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/digest", tags=["digest"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class DigestRequest(BaseModel):
    interests:   list[str] = Field(..., min_length=1, max_length=10,
                                   description="Topics to monitor, e.g. 'diffusion models'")
    days:        int        = Field(default=3, ge=1, le=30)
    max_results: int        = Field(default=20, ge=1, le=50)


class DigestPaper(BaseModel):
    title:            str
    abstract:         str
    authors:          list[str]
    url:              str
    paper_id:         str
    published:        str
    relevance_score:  float
    matched_interest: str


class DigestResponse(BaseModel):
    papers:             list[DigestPaper]
    interests_searched: list[str]
    total_fetched:      int


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/fetch", response_model=DigestResponse)
async def fetch_digest(req: DigestRequest):
    """
    Discover new arXiv papers that match user interests and are semantically
    relevant to their existing paper library.
    """
    # Fetch from arXiv for all interests concurrently
    raw_results = await asyncio.gather(
        *[fetch_recent_papers(i, max_results=25, days=req.days) for i in req.interests],
        return_exceptions=True,
    )

    # Deduplicate across interests; track which interest first matched each paper
    seen:   dict[str, dict] = {}
    for interest, result in zip(req.interests, raw_results):
        if isinstance(result, Exception):
            logger.warning("arXiv fetch failed for '%s': %s", interest, result)
            continue
        for paper in result:
            pid = paper["paper_id"]
            if pid not in seen:
                seen[pid] = {**paper, "matched_interest": interest}

    if not seen:
        return DigestResponse(papers=[], interests_searched=req.interests, total_fetched=0)

    total_fetched = len(seen)
    papers_list   = list(seen.values())

    # Score papers against the user's saved library
    scored = await _score_against_library(papers_list)

    # Sort and truncate
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    top = scored[: req.max_results]

    return DigestResponse(
        papers=[DigestPaper(**p) for p in top],
        interests_searched=req.interests,
        total_fetched=total_fetched,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _score_against_library(papers: list[dict]) -> list[dict]:
    """
    Embed each paper's abstract and find its closest match in Qdrant.
    The cosine similarity of the nearest neighbour becomes the relevance score.
    Falls back to 0.0 if Qdrant is unavailable.
    """
    client = get_qdrant()

    try:
        # Single batch embed — fast even for 50 papers
        abstracts = [p["abstract"][:600] for p in papers]
        vecs      = embed_texts(abstracts)

        scored = []
        for paper, vec in zip(papers, vecs):
            hits = await client.search(
                collection_name=COLLECTION,
                query_vector=vec,
                limit=1,
                with_payload=False,
            )
            score = round(hits[0].score, 4) if hits else 0.0
            scored.append({**paper, "relevance_score": score})

        return scored

    except Exception as exc:
        logger.warning("Library scoring failed (Qdrant unavailable?): %s", exc)
        return [{**p, "relevance_score": 0.0} for p in papers]
