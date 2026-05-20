# ─── backend/services/arxiv_client.py ─────────────────────────────────────────
"""
Thin async client for the public arXiv Atom API.

arXiv rate-limit guideline: max 1 request every 3 seconds.
We stay well within that since digest fetches happen at most once per session.
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

_ARXIV_API  = "https://export.arxiv.org/api/query"
_NS         = {"atom": "http://www.w3.org/2005/Atom"}
_CLEAN_WS   = re.compile(r"\s+")


async def fetch_recent_papers(
    query: str,
    max_results: int = 25,
    days: int = 7,
) -> list[dict]:
    """
    Fetch arXiv papers matching `query` published within the last `days` days.

    Returns a list of dicts with keys:
        title, abstract, authors, url, source, paper_id, published
    """
    params = {
        "search_query": f"all:{query}",
        "start":        0,
        "max_results":  max_results,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }

    headers = {
        # arXiv blocks requests without a recognisable User-Agent
        "User-Agent": "ResearchKit-AI/1.1 (https://github.com/researchkit-ai; research tool)",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(_ARXIV_API, params=params, headers=headers)
            r.raise_for_status()
    except Exception as exc:
        logger.warning("arXiv API error for query '%s': %s", query, exc or type(exc).__name__)
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

        authors = [
            a.findtext("atom:name", "", _NS)
            for a in entry.findall("atom:author", _NS)
        ]

        title    = _clean(entry.findtext("atom:title",   "", _NS))
        abstract = _clean(entry.findtext("atom:summary", "", _NS))

        papers.append({
            "title":     title,
            "abstract":  abstract,
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
