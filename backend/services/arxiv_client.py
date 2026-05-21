# ─── backend/services/arxiv_client.py ─────────────────────────────────────────
"""
Thin async client for the public arXiv Atom API.

arXiv rate-limit guideline: max 1 request every 3 seconds.
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_NS        = {"atom": "http://www.w3.org/2005/Atom"}
_CLEAN_WS  = re.compile(r"\s+")

# Maps common interest phrases → arXiv category codes.
# When a match is found the query becomes "cat:X AND ti:phrase" which is
# far more precise than "all:phrase" (which returns any paper mentioning
# the topic anywhere, including unrelated papers).
_CATEGORY_MAP: dict[str, str] = {
    "computer vision":        "cs.CV",
    "vision":                 "cs.CV",
    "image generation":       "cs.CV",
    "object detection":       "cs.CV",
    "segmentation":           "cs.CV",
    "image classification":   "cs.CV",
    "diffusion model":        "cs.CV",
    "diffusion models":       "cs.CV",
    "nlp":                    "cs.CL",
    "natural language":       "cs.CL",
    "language model":         "cs.CL",
    "language models":        "cs.CL",
    "llm":                    "cs.CL",
    "large language":         "cs.CL",
    "text generation":        "cs.CL",
    "machine translation":    "cs.CL",
    "sentiment analysis":     "cs.CL",
    "machine learning":       "cs.LG",
    "deep learning":          "cs.LG",
    "neural network":         "cs.LG",
    "reinforcement learning": "cs.LG",
    "rl":                     "cs.LG",
    "transformer":            "cs.LG",
    "attention mechanism":    "cs.LG",
    "graph neural":           "cs.LG",
    "federated learning":     "cs.LG",
    "robotics":               "cs.RO",
    "robot":                  "cs.RO",
    "speech":                 "eess.AS",
    "audio":                  "eess.AS",
    "multimodal":             "cs.CV",
    "rag":                    "cs.IR",
    "information retrieval":  "cs.IR",
    "recommendation":         "cs.IR",
    "cybersecurity":          "cs.CR",
    "security":               "cs.CR",
    "cryptography":           "cs.CR",
    "quantum":                "quant-ph",
    "bioinformatics":         "q-bio",
}


def _build_query(interest: str) -> str:
    """
    Build the most precise arXiv search query for an interest phrase.

    Strategy:
      1. Check for a known category mapping → use "cat:X AND ti:phrase"
         This restricts results to the correct sub-field and requires the
         topic to appear in the title (not just mentioned in passing).
      2. No mapping found → fall back to "(ti:phrase OR abs:phrase)"
         Still more precise than "all:phrase" which includes comments, etc.
    """
    lower = interest.lower().strip()

    # Find the most specific matching category
    cat = None
    for phrase, code in sorted(_CATEGORY_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            cat = code
            break

    if cat:
        return f"cat:{cat} AND (ti:{interest} OR abs:{interest})"
    return f"ti:{interest} OR abs:{interest}"


async def fetch_recent_papers(
    query: str,
    max_results: int = 25,
    days: int = 7,
) -> list[dict]:
    """
    Fetch arXiv papers matching `query` published within the last `days` days.
    Uses category-aware search so "computer vision" returns cs.CV papers,
    not LLM papers that mention vision in passing.
    """
    search_query = _build_query(query)
    logger.info("arXiv query for '%s': %s", query, search_query)

    params = {
        "search_query": search_query,
        "start":        0,
        "max_results":  max_results,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }
    headers = {
        "User-Agent": "ResearchKit-AI/1.1 (https://github.com/MahboobAlam0/research-toolkit; research tool)",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(_ARXIV_API, params=params, headers=headers)
            r.raise_for_status()
    except Exception as exc:
        logger.warning("arXiv API error for '%s': %s", query, exc or type(exc).__name__)
        return []

    return _parse(r.text, days=days)


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse(xml_text: str, days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("arXiv XML parse error: %s", exc)
        return []

    papers = []
    for entry in root.findall("atom:entry", _NS):
        published_str = entry.findtext("atom:published", "", _NS)
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            published = datetime.now(timezone.utc)

        if published < cutoff:
            continue

        id_url   = entry.findtext("atom:id", "", _NS)
        arxiv_id = _extract_arxiv_id(id_url)
        authors  = [a.findtext("atom:name", "", _NS)
                    for a in entry.findall("atom:author", _NS)]

        papers.append({
            "title":     _clean(entry.findtext("atom:title",   "", _NS)),
            "abstract":  _clean(entry.findtext("atom:summary", "", _NS)),
            "authors":   authors,
            "url":       f"https://arxiv.org/abs/{arxiv_id}",
            "source":    "arxiv",
            "paper_id":  arxiv_id,
            "published": published.isoformat(),
        })

    return papers


def _extract_arxiv_id(id_url: str) -> str:
    if "/abs/" in id_url:
        return id_url.split("/abs/")[-1].split("v")[0]
    return id_url


def _clean(text: str) -> str:
    return _CLEAN_WS.sub(" ", text).strip()
