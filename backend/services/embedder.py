# ─── backend/services/embedder.py ─────────────────────────────────────────────
"""
Singleton embedding service.
Model: BAAI/bge-base-en-v1.5  (768-dim, stronger retrieval than MiniLM-L6)

BGE retrieval note: queries must be prefixed with the instruction string;
document chunks are encoded without any prefix. This asymmetry is what gives
BGE its accuracy advantage on retrieval benchmarks.
"""
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import logging

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-base-en-v1.5"
# BGE retrieval instruction — prepended to queries only, not to documents.
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading embedding model %s…", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model ready.")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed document chunks (no instruction prefix)."""
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()


def embed_query(text: str) -> List[float]:
    """Embed a retrieval query (with BGE instruction prefix)."""
    model = get_model()
    vecs = model.encode(
        [_QUERY_INSTRUCTION + text],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vecs[0].tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity for pre-normalised vectors (just dot product)."""
    return float(np.dot(a, b))
