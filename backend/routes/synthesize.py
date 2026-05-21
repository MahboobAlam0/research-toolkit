# ─── backend/routes/synthesize.py ─────────────────────────────────────────────
"""
Literature synthesis + research gap detector.

POST /api/papers/synthesize

Given a research question, retrieves the top-k most relevant chunks from the
user's paper library and asks the LLM to produce — in one structured call:

  1. synthesis      — a cited paragraph summarising what the literature says
  2. contradictions — specific tensions/conflicts found between papers
  3. gaps           — what the literature does NOT yet address

The single-call design keeps latency low and ensures the three analyses share
the same context window (better coherence than separate prompts).
"""
import json
import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models.schemas import SourceRef
from services.llm_client import chat_completion
from services.rag_pipeline import retrieve

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/papers", tags=["papers"])

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```")


# ── Schemas ────────────────────────────────────────────────────────────────────

class SynthesisRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500,
                          description="Research question to synthesize literature around")
    top_k:    int = Field(default=8, ge=3, le=30,
                          description="Number of paper chunks to retrieve")


class SynthesisResponse(BaseModel):
    question:       str
    synthesis:      str
    contradictions: list[str]
    gaps:           list[str]
    sources:        list[SourceRef]
    chunks_used:    int


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_literature(req: SynthesisRequest):
    """
    Generate a structured literature synthesis with contradiction detection
    and research-gap identification across all saved papers.
    """
    chunks = await retrieve(req.question, top_k=req.top_k)

    if not chunks:
        raise HTTPException(
            404,
            "No relevant papers found in your library for this question. "
            "Save papers on this topic first, then try again.",
        )

    # Build numbered context block + deduplicated source list
    # Truncate each chunk to 400 chars so the total prompt stays within Groq's
    # request payload limit (413 otherwise with 15 full 512-word chunks).
    context_parts: list[str] = []
    seen_titles:   set[str]  = set()
    sources:       list[SourceRef] = []

    for i, chunk in enumerate(chunks, 1):
        excerpt = chunk["text"][:400].rsplit(" ", 1)[0] + "…"
        context_parts.append(f"[{i}] {chunk['title']}\n{excerpt}")
        if chunk["title"] not in seen_titles:
            seen_titles.add(chunk["title"])
            sources.append(SourceRef(title=chunk["title"], url=chunk["url"], score=chunk["score"]))

    context = "\n\n".join(context_parts)

    prompt = f"""You are an expert research assistant conducting a systematic literature review.

Research question: "{req.question}"

Paper excerpts — cite by [number]:
{context}

Perform the following three analyses and return a SINGLE JSON object. No markdown, no preamble.

1. "synthesis"
   A 3–5 sentence academic paragraph that directly answers the research question by synthesising
   what the papers collectively say. Use inline citations like [1], [2,5]. Be precise; avoid vague
   statements like "various papers discuss…".

2. "contradictions"
   JSON array of strings. Each string identifies a specific factual or methodological conflict
   BETWEEN papers in the excerpts (e.g. "[2] reports 94% accuracy while [5] finds only 78% on
   the same benchmark under similar conditions"). If no real conflict exists, return [].

3. "gaps"
   JSON array of 3–5 strings. Each string names a concrete research gap — something this body of
   literature does NOT address but should. Be specific (e.g. "No paper evaluates performance on
   low-resource languages" rather than "More research is needed").

Required JSON structure:
{{
  "synthesis": "...",
  "contradictions": ["...", "..."],
  "gaps": ["...", "...", "..."]
}}"""

    raw = await chat_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.15,
        max_tokens=900,
    )

    data = _parse_json(raw)
    if data is None:
        logger.error("Synthesis JSON parse failed. Raw: %s", raw[:400])
        raise HTTPException(500, "The LLM returned an unparseable response. Please try again.")

    return SynthesisResponse(
        question=req.question,
        synthesis=data.get("synthesis", ""),
        contradictions=_ensure_list(data.get("contradictions")),
        gaps=_ensure_list(data.get("gaps")),
        sources=sources,
        chunks_used=len(chunks),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict | None:
    clean = _JSON_FENCE_RE.sub("", text).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Try to extract the first {...} block as a fallback
        m = re.search(r"\{[\s\S]+\}", clean)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def _ensure_list(val) -> list[str]:
    if isinstance(val, list):
        return [str(v) for v in val]
    return []
