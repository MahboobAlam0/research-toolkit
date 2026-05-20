# ─── backend/routes/pdf_upload.py ─────────────────────────────────────────────
"""
PDF upload endpoint.

POST /api/papers/upload-pdf  (multipart/form-data, field name: "file")

Extracts full paper text via PyMuPDF, chunks it, embeds it, and stores in
Qdrant — same pipeline as web-scraped papers but richer content (full text
vs. abstract only).
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointStruct

from routes.ingest import ensure_collection, chunk_text
from services.embedder import embed_texts
from services.pdf_extractor import extract_pdf
from services.rag_pipeline import COLLECTION, get_qdrant

logger = router_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/papers", tags=["papers"])

_MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Ingest a PDF paper into the vector library.

    Accepts standard research PDFs (arXiv, conference proceedings, journals).
    Returns the number of text chunks indexed and the inferred title.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files (.pdf) are accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > _MAX_PDF_BYTES:
        raise HTTPException(413, f"PDF exceeds the {_MAX_PDF_BYTES // 1_048_576} MB limit.")

    try:
        extracted = extract_pdf(pdf_bytes)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    client = get_qdrant()
    await ensure_collection(client)

    # Duplicate detection by content fingerprint
    existing, _ = await client.scroll(
        collection_name=COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="paper_id", match=MatchValue(value=extracted.paper_id))]
        ),
        limit=1,
    )
    if existing:
        return {"status": "duplicate", "message": "This PDF is already in your library."}

    doc_id = str(uuid.uuid4())
    content = f"{extracted.title}\n\n{extracted.full_text}"
    chunks  = chunk_text(content)
    vectors = embed_texts(chunks)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={
                "doc_id":    doc_id,
                "paper_id":  extracted.paper_id,
                "chunk_idx": i,
                "text":      chunk,
                "title":     extracted.title,
                "authors":   extracted.authors,
                "abstract":  extracted.abstract,
                "url":       f"pdf://{file.filename}",
                "source":    "pdf_upload",
                "saved_at":  datetime.now(timezone.utc).isoformat(),
            },
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors))
    ]

    await client.upsert(collection_name=COLLECTION, points=points)
    logger.info(
        "Ingested PDF '%s' — %d pages, %d words, %d chunks.",
        extracted.title[:60], extracted.num_pages, extracted.word_count, len(chunks),
    )

    return {
        "status":  "ok",
        "doc_id":  doc_id,
        "title":   extracted.title,
        "pages":   extracted.num_pages,
        "words":   extracted.word_count,
        "chunks":  len(chunks),
    }
