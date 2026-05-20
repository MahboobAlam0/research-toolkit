# ─── backend/services/rag_pipeline.py ─────────────────────────────────────────
"""
RAG pipeline:
  1. Embed user query.
  2. Search Qdrant for top-k similar paper chunks.
  3. Build a prompt with retrieved context.
  4. Generate answer with Groq LLM.
"""
from typing import List, Tuple
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter
from services.embedder import embed_query
from services.llm_client import chat_completion
from models.schemas import SourceRef, ChatMessage
import os
import logging

logger = logging.getLogger(__name__)

COLLECTION = "papers"
TOP_K      = 5

# Qdrant client — created once at import time
_client: AsyncQdrantClient | None = None


def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        qdrant_url     = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        kwargs = {"url": qdrant_url}
        if qdrant_api_key:
            kwargs["api_key"] = qdrant_api_key   # required for Qdrant Cloud
        _client = AsyncQdrantClient(**kwargs)
        logger.info("Qdrant client → %s (cloud=%s)", qdrant_url, bool(qdrant_api_key))
    return _client


async def retrieve(query: str, top_k: int = TOP_K) -> List[dict]:
    """Embed query and retrieve top-k chunks from Qdrant."""
    q_vec = embed_query(query)
    client = get_qdrant()

    try:
        hits = await client.search(
            collection_name=COLLECTION,
            query_vector=q_vec,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.warning("Qdrant search failed: %s", e)
        return []

    results = []
    for hit in hits:
        payload = hit.payload or {}
        results.append({
            "score":    hit.score,
            "text":     payload.get("text", ""),
            "title":    payload.get("title", ""),
            "url":      payload.get("url", ""),
            "source":   payload.get("source", ""),
            "paper_id": payload.get("paper_id", ""),
        })
    return results


async def rag_query(
    query: str,
    history: List[ChatMessage] | None = None,
    top_k: int = TOP_K,
) -> Tuple[str, List[SourceRef]]:
    """
    Full RAG pipeline.

    Returns:
        (answer_text, list_of_source_refs)
    """
    history = history or []
    chunks  = await retrieve(query, top_k=top_k)

    if not chunks:
        return (
            "I couldn't find relevant papers in your library. "
            "Save some papers first using the Save button on arXiv or PubMed.",
            [],
        )

    # Build context block
    context_parts = []
    seen_titles   = set()
    sources       = []
    for i, c in enumerate(chunks, 1):
        context_parts.append(f"[{i}] {c['title']}\n{c['text']}")
        if c["title"] not in seen_titles:
            seen_titles.add(c["title"])
            sources.append(SourceRef(title=c["title"], url=c["url"], score=c["score"]))

    context = "\n\n".join(context_parts)

    # Build messages
    system_msg = (
        "You are ResearchKit AI, an expert research assistant. "
        "Answer the user's question ONLY using the provided paper contexts. "
        "Be precise and cite papers by [number] inline. "
        "If the context doesn't contain enough information, say so honestly."
    )

    messages = [{"role": "system", "content": system_msg}]

    # Add conversation history (last 6 turns)
    for h in history[-6:]:
        messages.append({"role": h.role, "content": h.content})

    # Final user message with context
    messages.append({
        "role": "user",
        "content": (
            f"Context from saved papers:\n\n{context}\n\n"
            f"Question: {query}"
        ),
    })

    answer = await chat_completion(messages, temperature=0.2, max_tokens=800)
    return answer, sources
