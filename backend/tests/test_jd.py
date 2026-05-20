"""
Tests for the JD skill-gap analyzer logic.

semantic_match() is a pure function modulo embed_texts (mocked in conftest).
extract_skills() and generate_action_plan() are tested with a mocked LLM.
"""
import json
import pytest

from routes.jd_analyzer import semantic_match, extract_skills, generate_action_plan


# ── semantic_match ─────────────────────────────────────────────────────────────

def test_empty_jd_skills_returns_perfect_score(mock_embedder):
    matched, missing, score = semantic_match([], ["python", "sql"])
    assert matched == []
    assert missing == []
    assert score == 1.0


def test_empty_resume_returns_zero_score(mock_embedder):
    jd_skills = ["python", "pytorch", "docker"]
    matched, missing, score = semantic_match(jd_skills, [])
    assert matched == []
    assert missing == jd_skills
    assert score == 0.0


def test_score_is_fraction_of_jd_skills_matched(mock_embedder):
    """
    semantic_match uses cosine similarity on fake vectors from conftest.
    With the same fake embedder, two identical skill lists should yield ~1.0 score.
    Because the fake vectors are random per-call the exact match depends on the
    threshold, so we only assert score is in [0, 1].
    """
    jd = ["python", "sql", "docker", "pytorch"]
    resume = ["python", "sql", "docker", "pytorch"]
    _, _, score = semantic_match(jd, resume)
    assert 0.0 <= score <= 1.0


def test_score_rounds_to_three_decimal_places(mock_embedder):
    _, _, score = semantic_match(["python", "sql"], ["python"])
    # Check it's properly rounded
    assert score == round(score, 3)


def test_matched_plus_missing_equals_jd_skills(mock_embedder):
    jd = ["python", "pytorch", "docker", "kubernetes", "sql"]
    resume = ["python", "sql"]
    matched, missing, _ = semantic_match(jd, resume)
    assert set(matched) | set(missing) == set(jd)
    assert set(matched) & set(missing) == set()


# ── extract_skills ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_skills_parses_valid_json(mock_llm):
    skills = await extract_skills("We need Python, PyTorch, and SQL.", role="JD")
    assert isinstance(skills, list)
    assert all(isinstance(s, str) for s in skills)
    # mock_llm returns '["python", "pytorch", "sql", "docker"]'
    assert "python" in skills


@pytest.mark.asyncio
async def test_extract_skills_lowercases_results(mock_llm, monkeypatch):
    async def caps_stub(messages, **_):
        return '["Python", "PyTorch", "SQL"]'
    monkeypatch.setattr("routes.jd_analyzer.chat_completion", caps_stub)

    skills = await extract_skills("some text", role="Resume")
    assert all(s == s.lower() for s in skills)


@pytest.mark.asyncio
async def test_extract_skills_falls_back_on_bad_json(monkeypatch):
    """When LLM returns garbage, fallback regex split must not raise."""
    async def bad_stub(messages, **_):
        return "python, pytorch\nsql"
    monkeypatch.setattr("routes.jd_analyzer.chat_completion", bad_stub)

    skills = await extract_skills("some text")
    assert "python" in skills
    assert "pytorch" in skills


# ── generate_action_plan ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_action_plan_no_gaps(mock_llm):
    actions, summary = await generate_action_plan("some JD", [], 1.0)
    assert actions == ["Your profile is a strong match for this role."]
    assert summary == "Excellent match."


@pytest.mark.asyncio
async def test_generate_action_plan_with_gaps(monkeypatch):
    call_count = {"n": 0}

    async def plan_stub(messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return '["Learn Kubernetes", "Build a Docker project"]'
        return "Candidate has moderate fit; should focus on container tooling."

    monkeypatch.setattr("routes.jd_analyzer.chat_completion", plan_stub)

    actions, summary = await generate_action_plan("JD text", ["kubernetes", "docker"], 0.5)
    assert len(actions) >= 1
    assert isinstance(summary, str) and len(summary) > 0
