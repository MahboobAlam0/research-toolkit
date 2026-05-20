"""
Shared pytest fixtures.

All external I/O (embedding model, Qdrant, Groq LLM) is mocked so the test
suite runs without Docker, a GPU, or any API keys.
"""
import sys
import os
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock

# Make the backend package importable from the tests/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

FAKE_DIM = 768


def _fake_vecs(n: int) -> list[list[float]]:
    """Return n normalised unit vectors that are deterministically cosine-close."""
    rng = np.random.default_rng(42)
    vecs = rng.random((n, FAKE_DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs.tolist()


@pytest.fixture(autouse=True)
def mock_embedder(monkeypatch):
    """
    Replace the embedding model with a fast stub.
    Patched in every module that imported the functions at load time.
    """
    def fake_embed_texts(texts):
        return _fake_vecs(len(texts))

    def fake_embed_query(text):
        return _fake_vecs(1)[0]

    monkeypatch.setattr("services.embedder.embed_texts", fake_embed_texts)
    monkeypatch.setattr("services.embedder.embed_query", fake_embed_query)
    # Also patch references copied into other modules via "from X import Y"
    monkeypatch.setattr("routes.jd_analyzer.embed_texts", fake_embed_texts)
    monkeypatch.setattr("services.rag_pipeline.embed_query", fake_embed_query)

    # Prevent the real SentenceTransformer from being loaded during lifespan
    mock_model = MagicMock()
    mock_model.encode.side_effect = lambda texts, **_: np.array(_fake_vecs(len(texts)))
    monkeypatch.setattr("services.embedder.get_model", lambda: mock_model)


@pytest.fixture
def mock_qdrant(monkeypatch):
    """
    Inject a fully-async mock Qdrant client.
    Also sets the collection-ready flag so ensure_collection() is skipped.
    """
    client = AsyncMock()
    client.get_collections.return_value = MagicMock(collections=[])
    client.search.return_value = []
    client.scroll.return_value = ([], None)
    client.upsert.return_value = None
    client.delete.return_value = None
    client.count.return_value = MagicMock(count=0)
    client.create_collection.return_value = None

    monkeypatch.setattr("services.rag_pipeline._client", client)
    monkeypatch.setattr("routes.ingest._collection_ready", True)
    return client


@pytest.fixture
def mock_llm(monkeypatch):
    """Replace the Groq chat_completion with a stub returning a JSON skill list."""
    async def _stub(messages, temperature=0.2, max_tokens=1024):
        return '["python", "pytorch", "sql", "docker"]'

    monkeypatch.setattr("services.llm_client.chat_completion", _stub)
    monkeypatch.setattr("routes.jd_analyzer.chat_completion", _stub)
    return _stub


@pytest.fixture
def api_client(mock_embedder, mock_qdrant, mock_llm):
    """
    FastAPI TestClient with all external dependencies mocked.
    Suitable for route-level integration tests.
    """
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
