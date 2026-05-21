# ─── backend/services/paper_tagger.py ─────────────────────────────────────────
"""
Auto-tags a paper using the LLM immediately after ingestion.

Extracts four structured fields from title + abstract:
  task        — the research problem being solved
  methods     — key techniques, models, or algorithms used
  datasets    — benchmarks or datasets mentioned
  key_result  — the single most important finding

Tags are stored in Qdrant payload so they appear on paper cards
and can be used for filtering without re-embedding.
"""
import json
import logging
import re

from qdrant_client.models import FieldCondition, Filter, MatchValue

from services.llm_client import chat_completion
from services.rag_pipeline import COLLECTION, get_qdrant

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*|\s*```")


async def tag_paper(doc_id: str, title: str, abstract: str) -> None:
    """
    Extract structured tags and write them to every Qdrant point that
    belongs to this paper (matched by doc_id).  Runs as a background task.
    """
    tags = await _extract_tags(title, abstract)
    await _write_tags(doc_id, tags)


# ── LLM extraction ─────────────────────────────────────────────────────────────

async def _extract_tags(title: str, abstract: str) -> dict:
    prompt = f"""You are a research metadata extractor.

Paper title: {title[:300]}
Abstract: {abstract[:700]}

Extract structured metadata. Return ONLY valid JSON — no markdown, no explanation.

{{
  "task": "one short phrase for the research task (e.g. 'image generation', 'RAG')",
  "methods": ["up to 4 key methods or architectures (e.g. 'diffusion model', 'LoRA')"],
  "datasets": ["datasets or benchmarks mentioned, or [] if none"],
  "key_result": "one sentence on the most important quantitative or qualitative finding, or empty string"
}}"""

    try:
        raw   = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=180,
        )
        clean = _FENCE_RE.sub("", raw).strip()
        data  = json.loads(clean)
        return {
            "tags_task":       str(data.get("task",       "")),
            "tags_methods":    [str(m) for m in data.get("methods",  [])[:4]],
            "tags_datasets":   [str(d) for d in data.get("datasets", [])[:4]],
            "tags_key_result": str(data.get("key_result", "")),
        }
    except Exception as exc:
        logger.warning("Tag extraction failed for '%s': %s", title[:60], exc)
        return {"tags_task": "", "tags_methods": [], "tags_datasets": [], "tags_key_result": ""}


# ── Qdrant update ──────────────────────────────────────────────────────────────

async def _write_tags(doc_id: str, tags: dict) -> None:
    try:
        client = get_qdrant()
        await client.set_payload(
            collection_name=COLLECTION,
            payload=tags,
            points=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
        )
        logger.info("Tagged paper doc_id=%s task='%s'", doc_id, tags.get("tags_task"))
    except Exception as exc:
        logger.warning("Failed to write tags for doc_id=%s: %s", doc_id, exc)
