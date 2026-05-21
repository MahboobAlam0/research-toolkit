# ─── backend/routes/bibtex_import.py ──────────────────────────────────────────
"""
BibTeX bulk import.

POST /api/papers/import-bibtex  (multipart/form-data, field: "file")

Parses a .bib file, ingests every entry that has a title, skips duplicates,
and fires auto-tagging for each new paper in the background.

This is the killer feature for researchers who already have a Zotero/Mendeley
library — they can import their entire collection in one click.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from routes.ingest import VECTOR_DIM, chunk_text, ensure_collection
from services.bibtex_parser import entry_to_paper, parse_bibtex
from services.embedder import embed_texts
from services.paper_tagger import tag_paper
from services.rag_pipeline import COLLECTION, get_qdrant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/papers", tags=["papers"])

_MAX_BIB_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/import-bibtex")
async def import_bibtex(file: UploadFile = File(...)):
    """
    Bulk-import a Zotero / Mendeley / JabRef .bib export.

    Each entry with a title is chunked, embedded, and stored.
    Duplicates (same cite key) are skipped.  Auto-tagging runs in background.

    Returns a summary: imported / duplicates / skipped (no title or abstract).
    """
    if not (file.filename or "").lower().endswith((".bib", ".bibtex")):
        raise HTTPException(400, "Only .bib / .bibtex files are accepted.")

    raw = await file.read()
    if len(raw) > _MAX_BIB_BYTES:
        raise HTTPException(413, "File too large (max 10 MB).")

    text    = raw.decode("utf-8", errors="ignore")
    entries = parse_bibtex(text)

    if not entries:
        raise HTTPException(422, "No BibTeX entries found in the file.")

    client = get_qdrant()
    await ensure_collection(client)

    imported   = 0
    duplicates = 0
    skipped    = 0
    titles     = []

    for entry in entries:
        paper = entry_to_paper(entry)
        if paper is None:
            skipped += 1
            continue

        # Duplicate check by paper_id
        existing, _ = await client.scroll(
            collection_name=COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="paper_id", match=MatchValue(value=paper["paper_id"]))]
            ),
            limit=1,
        )
        if existing:
            duplicates += 1
            continue

        doc_id  = str(uuid.uuid4())
        content = f"{paper['title']}\n\n{paper['abstract']}"
        chunks  = chunk_text(content)
        vectors = embed_texts(chunks)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "doc_id":    doc_id,
                    "paper_id":  paper["paper_id"],
                    "chunk_idx": i,
                    "text":      chunk,
                    "title":     paper["title"],
                    "authors":   paper["authors"],
                    "url":       paper["url"],
                    "source":    "bibtex",
                    "year":      paper.get("year", ""),
                    "venue":     paper.get("venue", ""),
                    "saved_at":  datetime.now(timezone.utc).isoformat(),
                },
            )
            for i, (chunk, vec) in enumerate(zip(chunks, vectors))
        ]

        await client.upsert(collection_name=COLLECTION, points=points)
        asyncio.create_task(tag_paper(doc_id, paper["title"], paper["abstract"]))

        imported += 1
        titles.append(paper["title"][:80])
        logger.info("BibTeX imported: '%s'", paper["title"][:60])

    return {
        "imported":   imported,
        "duplicates": duplicates,
        "skipped":    skipped,
        "total":      len(entries),
        "titles":     titles[:10],   # first 10 for confirmation
    }
