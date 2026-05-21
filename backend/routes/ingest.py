# ─── backend/routes/ingest.py ─────────────────────────────────────────────────
"""
Paper ingestion API.

POST /api/papers/ingest   — embed + store a new paper
GET  /api/papers/list     — list all saved papers (metadata only)
GET  /api/papers/count    — return { count: N }
DELETE /api/papers/{id}   — remove a paper and its chunks
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

from models.schemas import PaperIngest, PaperRecord
from services.embedder import embed_texts
from services.rag_pipeline import get_qdrant, COLLECTION

logger  = logging.getLogger(__name__)
router  = APIRouter(prefix="/api/papers", tags=["papers"])

VECTOR_DIM = 768   # BAAI/bge-base-en-v1.5 output dimension

# Cached flag so we only check Qdrant for collection existence once per process
_collection_ready = False


# ── Helpers ────────────────────────────────────────────────────────────────────

async def ensure_collection(client: AsyncQdrantClient):
    """
    Create the collection if it doesn't exist, then ensure payload indexes.
    Qdrant Cloud requires explicit indexes before filtered scrolls/counts work.
    Safe to call multiple times — cached after first successful run.
    """
    global _collection_ready
    if _collection_ready:
        return

    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION not in names:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s'.", COLLECTION)

    # Create payload indexes required by Qdrant Cloud for filtered queries
    index_fields = {
        "paper_id":  PayloadSchemaType.KEYWORD,
        "doc_id":    PayloadSchemaType.KEYWORD,
        "source":    PayloadSchemaType.KEYWORD,
        "chunk_idx": PayloadSchemaType.INTEGER,
    }
    for field, schema in index_fields.items():
        try:
            await client.create_payload_index(
                collection_name=COLLECTION,
                field_name=field,
                field_schema=schema,
            )
        except Exception:
            pass  # index already exists — safe to ignore

    logger.info("Payload indexes ready for collection '%s'.", COLLECTION)
    _collection_ready = True


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """Split text into overlapping chunks by word count."""
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        chunk = " ".join(words[start : start + chunk_size])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=dict)
async def ingest_paper(paper: PaperIngest):
    """Embed and store a paper's abstract (chunked) in Qdrant."""
    client = get_qdrant()
    await ensure_collection(client)

    # Check for duplicate
    existing = await client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="paper_id", match=MatchValue(value=paper.paper_id))]
        ),
        limit=1,
    )
    if existing[0]:
        return {"status": "duplicate", "message": "Paper already saved."}

    doc_id  = str(uuid.uuid4())
    content = f"{paper.title}\n\n{paper.abstract}"
    chunks  = chunk_text(content)

    # Embed all chunks in one call (efficient)
    vectors = embed_texts(chunks)

    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "doc_id":   doc_id,
                    "paper_id": paper.paper_id,
                    "chunk_idx": i,
                    "text":     chunk,
                    "title":    paper.title,
                    "authors":  paper.authors,
                    "url":      paper.url,
                    "source":   paper.source,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        )

    await client.upsert(collection_name=COLLECTION, points=points)
    logger.info("Ingested paper '%s' (%d chunks).", paper.title[:60], len(chunks))

    # Auto-tag in background — doesn't slow down the save response
    import asyncio
    from services.paper_tagger import tag_paper
    asyncio.create_task(tag_paper(doc_id, paper.title, paper.abstract))

    return {"status": "ok", "doc_id": doc_id, "chunks": len(chunks)}


@router.get("/list", response_model=List[PaperRecord])
async def list_papers():
    """Return metadata for all saved papers (deduplicated by doc_id)."""
    client = get_qdrant()
    await ensure_collection(client)

    seen     = set()
    records  = []
    offset   = None

    while True:
        batch, next_offset = await client.scroll(
            collection_name=COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
        )
        for point in batch:
            p = point.payload or {}
            doc_id = p.get("doc_id", "")
            if p.get("chunk_idx", 0) == 0 and doc_id not in seen:
                seen.add(doc_id)
                records.append(
                    PaperRecord(
                        id=doc_id,
                        title=p.get("title", ""),
                        authors=p.get("authors", []),
                        url=p.get("url", ""),
                        source=p.get("source", ""),
                        paper_id=p.get("paper_id", ""),
                        saved_at=p.get("saved_at", ""),
                        year=p.get("year", ""),
                        venue=p.get("venue", ""),
                        tags_task=p.get("tags_task", ""),
                        tags_methods=p.get("tags_methods", []),
                        tags_datasets=p.get("tags_datasets", []),
                        tags_key_result=p.get("tags_key_result", ""),
                    )
                )
        if next_offset is None:
            break
        offset = next_offset

    return sorted(records, key=lambda r: r.saved_at, reverse=True)


@router.get("/count")
async def count_papers():
    """Return paper count using Qdrant's native counter (O(1), no full scan)."""
    client = get_qdrant()
    await ensure_collection(client)
    try:
        result = await client.count(
            collection_name=COLLECTION,
            count_filter=Filter(
                must=[FieldCondition(key="chunk_idx", match=MatchValue(value=0))]
            ),
        )
        return {"count": result.count}
    except Exception:
        return {"count": 0}


@router.delete("/{doc_id}")
async def delete_paper(doc_id: str):
    """Delete all chunks belonging to a paper."""
    client = get_qdrant()
    await client.delete(
        collection_name=COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        ),
    )
    return {"status": "deleted", "doc_id": doc_id}
