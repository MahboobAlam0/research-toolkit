"""
Route-level integration tests using FastAPI's synchronous TestClient.
All external I/O (Qdrant, Groq, sentence-transformers) is mocked via conftest.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ── Health check ───────────────────────────────────────────────────────────────

def test_health_check(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_returns_docs_link(api_client):
    r = api_client.get("/")
    assert r.status_code == 200
    assert "docs" in r.json()


# ── Paper ingest ───────────────────────────────────────────────────────────────

SAMPLE_PAPER = {
    "title": "Attention Is All You Need",
    "abstract": "We propose a new simple network architecture, the Transformer.",
    "authors": ["Vaswani et al."],
    "url": "https://arxiv.org/abs/1706.03762",
    "source": "arxiv",
    "paper_id": "1706.03762",
}


def test_ingest_paper_returns_ok(api_client, mock_qdrant):
    mock_qdrant.scroll.return_value = ([], None)  # no duplicate
    r = api_client.post("/api/papers/ingest", json=SAMPLE_PAPER)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "doc_id" in data
    assert data["chunks"] >= 1


def test_ingest_duplicate_returns_duplicate_status(api_client, mock_qdrant):
    fake_point = MagicMock()
    fake_point.payload = {"paper_id": SAMPLE_PAPER["paper_id"]}
    mock_qdrant.scroll.return_value = ([fake_point], None)

    r = api_client.post("/api/papers/ingest", json=SAMPLE_PAPER)
    assert r.status_code == 200
    assert r.json()["status"] == "duplicate"


def test_ingest_rejects_invalid_source(api_client):
    bad = {**SAMPLE_PAPER, "source": "wikipedia"}
    r = api_client.post("/api/papers/ingest", json=bad)
    assert r.status_code == 422  # Pydantic validation error


def test_ingest_rejects_missing_title(api_client):
    bad = {k: v for k, v in SAMPLE_PAPER.items() if k != "title"}
    r = api_client.post("/api/papers/ingest", json=bad)
    assert r.status_code == 422


# ── Paper list ─────────────────────────────────────────────────────────────────

def test_list_papers_empty(api_client, mock_qdrant):
    mock_qdrant.scroll.return_value = ([], None)
    r = api_client.get("/api/papers/list")
    assert r.status_code == 200
    assert r.json() == []


def test_list_papers_deduplicates_by_doc_id(api_client, mock_qdrant):
    """Two points with same doc_id but different chunk_idx → one record returned."""
    def make_point(chunk_idx):
        p = MagicMock()
        p.payload = {
            "doc_id": "doc-abc",
            "paper_id": "1706.03762",
            "chunk_idx": chunk_idx,
            "title": "Test Paper",
            "authors": [],
            "url": "https://arxiv.org/abs/1706.03762",
            "source": "arxiv",
            "saved_at": "2025-01-01T00:00:00+00:00",
        }
        return p

    mock_qdrant.scroll.side_effect = [
        ([make_point(0), make_point(1)], None),
        ([], None),
    ]
    r = api_client.get("/api/papers/list")
    assert r.status_code == 200
    assert len(r.json()) == 1


# ── Paper count ────────────────────────────────────────────────────────────────

def test_count_papers_uses_qdrant_count(api_client, mock_qdrant):
    mock_qdrant.count.return_value = MagicMock(count=7)
    r = api_client.get("/api/papers/count")
    assert r.status_code == 200
    assert r.json()["count"] == 7


# ── Paper delete ───────────────────────────────────────────────────────────────

def test_delete_paper_returns_deleted(api_client, mock_qdrant):
    r = api_client.delete("/api/papers/some-doc-id")
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    assert mock_qdrant.delete.called


# ── Semantic search ────────────────────────────────────────────────────────────

def test_semantic_search_empty_results(api_client, mock_qdrant):
    mock_qdrant.search.return_value = []
    r = api_client.get("/api/papers/search", params={"q": "transformers attention"})
    assert r.status_code == 200
    data = r.json()
    assert "query" in data
    assert data["results"] == []


def test_semantic_search_deduplicates_by_paper_id(api_client, mock_qdrant):
    """Multiple chunks from the same paper → only one result returned."""
    def make_hit(score):
        h = MagicMock()
        h.score = score
        h.payload = {
            "paper_id": "same-paper",
            "title": "Shared Paper",
            "url": "https://arxiv.org/abs/1234",
            "source": "arxiv",
            "text": "Some text content here.",
        }
        return h

    mock_qdrant.search.return_value = [make_hit(0.92), make_hit(0.87)]
    r = api_client.get("/api/papers/search", params={"q": "attention"})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1
    assert r.json()["results"][0]["relevance_score"] == 0.92


def test_semantic_search_requires_query(api_client):
    r = api_client.get("/api/papers/search")
    assert r.status_code == 422


# ── Chat / RAG ─────────────────────────────────────────────────────────────────

def test_chat_query_no_papers(api_client, mock_qdrant):
    mock_qdrant.search.return_value = []
    r = api_client.post("/api/chat/query", json={"query": "What is RAG?"})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    # When no papers are saved the RAG pipeline returns a helpful prompt
    assert "library" in data["answer"].lower() or "save" in data["answer"].lower()


def test_chat_query_missing_query_field(api_client):
    r = api_client.post("/api/chat/query", json={})
    assert r.status_code == 422


# ── JD Analyzer ────────────────────────────────────────────────────────────────

def test_jd_analyze_no_resume_returns_400(api_client):
    r = api_client.post("/api/jd/analyze", json={"jd_text": "We need Python and Docker."})
    assert r.status_code == 400


def test_jd_analyze_missing_jd_returns_400(api_client):
    r = api_client.post("/api/jd/analyze", json={"jd_text": "   ", "resume_text": "Python developer"})
    assert r.status_code == 400


def test_jd_analyze_returns_valid_structure(api_client, mock_llm, monkeypatch):
    async def plan_stub(messages, **_):
        return '["Learn Kubernetes", "Build Docker projects"]'

    call_n = {"n": 0}

    async def skill_then_plan(messages, **_):
        call_n["n"] += 1
        if call_n["n"] <= 2:
            return '["python", "pytorch", "sql", "docker"]'
        if call_n["n"] == 3:
            return '["Learn Kubernetes"]'
        return "Good fit overall."

    monkeypatch.setattr("routes.jd_analyzer.chat_completion", skill_then_plan)

    r = api_client.post(
        "/api/jd/analyze",
        json={"jd_text": "Need Python, PyTorch, Docker.", "resume_text": "I know Python and SQL."},
    )
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert 0.0 <= data["score"] <= 1.0
    assert isinstance(data["matched_skills"], list)
    assert isinstance(data["missing_skills"], list)
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["summary"], str)


# ── Stats ──────────────────────────────────────────────────────────────────────

def test_stats_endpoint(api_client, mock_qdrant):
    mock_qdrant.get_collection.return_value = MagicMock(points_count=42)
    r = api_client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "embedding_model" in data
    assert "llm" in data
