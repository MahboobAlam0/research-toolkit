# ─── backend/services/bibtex_parser.py ────────────────────────────────────────
"""
Lightweight BibTeX parser — no external dependencies.

Handles the most common entry types used in ML/CS research:
@article, @inproceedings, @conference, @proceedings, @techreport,
@misc, @phdthesis, @mastersthesis, @book, @preprint

Returns a list of flat dicts with lowercased field names plus
  _type : entry type (article, inproceedings, …)
  _key  : cite key
"""
import re
import logging

logger = logging.getLogger(__name__)

# Matches one BibTeX entry.  Works even if closing } is on its own line.
_ENTRY_RE = re.compile(
    r"@(\w+)\s*\{\s*([^,\s]+)\s*,\s*([\s\S]*?)\n\s*\}",
    re.MULTILINE,
)

# Matches a single field.  Handles:
#   field = {value}          (possibly nested braces one level deep)
#   field = {outer {inner} outer}
#   field = "value"
#   field = 2024             (bare number)
_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*"
    r"(?:"
    r"\{((?:[^{}]|\{[^{}]*\})*)\}"   # {…} possibly one level nested
    r'|"([^"]*)"'                     # "…"
    r"|(\d+)"                         # bare integer
    r")",
    re.DOTALL,
)

_LATEX_CMD_RE = re.compile(r"\\[a-zA-Z]+\s*")
_EXTRA_BRACE_RE = re.compile(r"[{}]")
_WHITESPACE_RE = re.compile(r"\s+")


def parse_bibtex(text: str) -> list[dict]:
    """Parse a .bib file and return a list of entry dicts."""
    entries = []
    for m in _ENTRY_RE.finditer(text):
        entry: dict = {
            "_type": m.group(1).lower(),
            "_key":  m.group(2).strip(),
        }
        body = m.group(3)
        for fm in _FIELD_RE.finditer(body):
            name  = fm.group(1).lower()
            value = fm.group(2) or fm.group(3) or fm.group(4) or ""
            entry[name] = _clean(str(value))
        entries.append(entry)

    logger.info("Parsed %d BibTeX entries.", len(entries))
    return entries


def entry_to_paper(entry: dict) -> dict | None:
    """
    Convert a parsed BibTeX entry to a paper ingest dict.
    Returns None if the entry lacks a title (unusable).
    """
    title    = entry.get("title", "").strip()
    abstract = entry.get("abstract", "").strip()

    if not title:
        return None

    # Authors: BibTeX uses " and " as separator
    raw_authors = entry.get("author", "")
    authors = [a.strip() for a in re.split(r"\s+and\s+", raw_authors) if a.strip()]

    # URL: prefer explicit url, then doi, then construct a Scholar query
    url = (
        entry.get("url")
        or (f"https://doi.org/{entry['doi']}" if entry.get("doi") else "")
        or f"https://scholar.google.com/scholar?q={title[:60].replace(' ', '+')}"
    )

    year  = entry.get("year", "")
    venue = entry.get("journal") or entry.get("booktitle") or ""

    return {
        "title":    title,
        "abstract": abstract or f"[No abstract] {title}",
        "authors":  authors,
        "url":      url,
        "source":   "bibtex",
        "paper_id": f"bib_{entry['_key']}",
        "year":     year,
        "venue":    venue,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """Strip LaTeX commands, stray braces, and normalise whitespace."""
    text = _LATEX_CMD_RE.sub(" ", text)
    text = _EXTRA_BRACE_RE.sub("",  text)
    return _WHITESPACE_RE.sub(" ", text).strip()
