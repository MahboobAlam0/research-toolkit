# ─── backend/services/pdf_extractor.py ────────────────────────────────────────
"""
Extract structured text from PDF files using PyMuPDF (fitz).

Strategy:
  - Extract text page-by-page preserving reading order
  - Remove common noise: page numbers, running headers/footers, lone digits
  - Detect abstract via section-header regex so it goes into the abstract field
  - Return clean full text and inferred metadata for downstream chunking
"""
import re
import hashlib
import logging
from dataclasses import dataclass

import fitz  # pymupdf

logger = logging.getLogger(__name__)

_ABSTRACT_RE = re.compile(
    r"(?i)\bAbstract\b[.\s:—–-]*\n?([\s\S]+?)(?=\n\s*\n|\n\s*(?:1\.?\s+intro|keywords?|index terms?))",
    re.IGNORECASE,
)
_NOISE_LINE_RE = re.compile(
    r"^\s*(\d{1,4}|[ivxlcdmIVXLCDM]{1,6}|arXiv:\S+|doi:\S+|©.*|preprint.*)\s*$",
    re.IGNORECASE,
)


@dataclass
class ExtractedPDF:
    title: str
    abstract: str
    full_text: str
    authors: list[str]
    paper_id: str
    num_pages: int
    word_count: int


def extract_pdf(pdf_bytes: bytes) -> ExtractedPDF:
    """
    Parse a PDF and return an ExtractedPDF with cleaned full text.
    Raises ValueError if the file cannot be read or has no extractable text.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Cannot open PDF: {exc}") from exc

    meta = doc.metadata or {}
    title  = (meta.get("title")  or "").strip()
    author = (meta.get("author") or "").strip()

    pages_text: list[str] = []
    for page in doc:
        raw = page.get_text("text") or ""
        pages_text.append(_clean_page(raw))

    doc.close()

    full_text = "\n".join(pages_text).strip()
    if not full_text:
        raise ValueError("PDF contains no extractable text (may be scanned/image-only).")

    if not title:
        title = _infer_title(pages_text[0]) if pages_text else "Untitled PDF"

    abstract = _extract_abstract(full_text)

    fingerprint = hashlib.sha256(pdf_bytes[:8192]).hexdigest()[:20]

    authors: list[str] = []
    if author:
        authors = [a.strip() for a in re.split(r"[,;]", author) if a.strip()]

    logger.info("Extracted PDF '%s' — %d pages, %d words.", title[:60], len(pages_text), len(full_text.split()))

    return ExtractedPDF(
        title=title or "Untitled PDF",
        abstract=abstract,
        full_text=full_text,
        authors=authors,
        paper_id=f"pdf_{fingerprint}",
        num_pages=len(pages_text),
        word_count=len(full_text.split()),
    )


# ── Private helpers ────────────────────────────────────────────────────────────

def _clean_page(text: str) -> str:
    """Remove noise lines (page numbers, arXiv IDs, lone symbols) from a page."""
    lines = text.splitlines()
    cleaned = [ln for ln in lines if not _NOISE_LINE_RE.match(ln)]
    return "\n".join(cleaned)


def _infer_title(first_page: str) -> str:
    """Heuristic: title is the first substantive line on page 1."""
    for line in first_page.splitlines():
        line = line.strip()
        if 8 < len(line) < 220 and not line.lower().startswith(("abstract", "arxiv", "doi")):
            return line
    return ""


def _extract_abstract(text: str) -> str:
    """Return the abstract section if found; fall back to the opening paragraph."""
    m = _ABSTRACT_RE.search(text)
    if m:
        candidate = re.sub(r"\s+", " ", m.group(1)).strip()
        if 40 < len(candidate) < 4000:
            return candidate

    # Fallback: first 600 chars of clean text
    return re.sub(r"\s+", " ", text[:1200]).strip()[:600]
