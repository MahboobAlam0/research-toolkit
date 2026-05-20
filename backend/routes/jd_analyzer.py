# ─── backend/routes/jd_analyzer.py ───────────────────────────────────────────
"""
JD Skill-Gap Analyzer.

POST /api/jd/analyze

Algorithm:
  1. Extract skills from JD using LLM → structured JSON list
  2. Extract skills from resume using LLM → structured JSON list
  3. Compare: cosine similarity on embedded skill sets + exact matching
  4. Compute match score, gaps, and action plan via LLM
"""
import json
import logging
import os
import re
from fastapi import APIRouter, HTTPException
from models.schemas import JDRequest, JDResponse
from services.embedder import embed_texts, cosine_similarity
from services.llm_client import chat_completion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jd", tags=["jd"])

# Default resume to use when none is provided (loaded from env or default placeholder)
DEFAULT_RESUME = os.getenv("DEFAULT_RESUME", "")


# ── Skill extraction ───────────────────────────────────────────────────────────

async def extract_skills(text: str, role: str = "JD") -> list[str]:
    """
    Use LLM to extract a flat list of technical and domain skills from text.
    Returns a list of lowercase skill strings.
    """
    prompt = f"""Extract ALL technical skills, tools, frameworks, programming languages,
domain knowledge areas, and methodologies from the following {role} text.

Return ONLY a JSON array of strings. No preamble, no markdown, no explanation.
Example: ["python", "pytorch", "transformer models", "sql", "docker"]

{role} text:
\"\"\"
{text[:3000]}
\"\"\"
"""
    response = await chat_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=400,
    )

    # Safely parse JSON
    try:
        # Strip possible code fences
        clean = re.sub(r"```(?:json)?|```", "", response).strip()
        skills = json.loads(clean)
        return [s.lower().strip() for s in skills if isinstance(s, str)]
    except Exception:
        logger.warning("Skill extraction JSON parse failed. Raw: %s", response[:200])
        # Fallback: split by comma / newline
        return [s.strip().lower() for s in re.split(r"[,\n]", response) if s.strip()]


# ── Semantic matching ──────────────────────────────────────────────────────────

def semantic_match(
    jd_skills: list[str],
    resume_skills: list[str],
    threshold: float = 0.80,
) -> tuple[list[str], list[str], float]:
    """
    Match JD skills against resume skills using embedding cosine similarity.

    Returns:
        (matched_skills, missing_skills, score)
    """
    if not jd_skills:
        return [], [], 1.0

    if not resume_skills:
        return [], jd_skills, 0.0

    # Embed all skills in one batch call
    all_texts = jd_skills + resume_skills
    all_vecs  = embed_texts(all_texts)
    jd_vecs   = all_vecs[: len(jd_skills)]
    res_vecs  = all_vecs[len(jd_skills):]

    matched, missing = [], []
    for jd_skill, jd_vec in zip(jd_skills, jd_vecs):
        best_score = max(cosine_similarity(jd_vec, rv) for rv in res_vecs)
        if best_score >= threshold:
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    score = len(matched) / len(jd_skills) if jd_skills else 1.0
    return matched, missing, round(score, 3)


# ── Action plan generation ─────────────────────────────────────────────────────

async def generate_action_plan(
    jd_text: str,
    missing_skills: list[str],
    score: float,
) -> tuple[list[str], str]:
    """Generate a concrete action plan for the skill gaps."""
    if not missing_skills:
        return ["Your profile is a strong match for this role."], "Excellent match."

    missing_str = ", ".join(missing_skills[:15])
    prompt = f"""A candidate is applying for a role. Their match score is {int(score * 100)}%.
They are missing these skills: {missing_str}

Write 4-5 SHORT, concrete, actionable suggestions to bridge the gap.
Focus on the most impactful gaps first.
Return ONLY a JSON array of strings. No markdown, no preamble.

Example:
["Build a project using X to demonstrate hands-on experience",
 "Complete Coursera's Y specialization (6 weeks)",
 "Contribute to open-source Z project",
 "Add A, B, C to resume by working on side projects"]
"""
    response = await chat_completion(
        [{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=400,
    )

    try:
        clean   = re.sub(r"```(?:json)?|```", "", response).strip()
        actions = json.loads(clean)
    except Exception:
        actions = [s.strip() for s in response.split("\n") if s.strip()][:5]

    summary_prompt = f"""In one sentence, summarise the candidate's fit for this role.
Match score: {int(score * 100)}%. Missing skills: {missing_str}.
Be direct and constructive."""

    summary = await chat_completion(
        [{"role": "user", "content": summary_prompt}],
        temperature=0.2,
        max_tokens=80,
    )

    return actions, summary.strip()


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=JDResponse)
async def analyze_jd(req: JDRequest):
    """Analyze skill gap between a job description and a resume."""
    if not req.jd_text.strip():
        raise HTTPException(status_code=400, detail="JD text is required.")

    resume = req.resume_text or DEFAULT_RESUME
    if not resume.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "No resume provided. Paste your resume in the extension, "
                "or set DEFAULT_RESUME in your .env file."
            ),
        )

    try:
        # Extract skills from both sides
        jd_skills, resume_skills = await _parallel_extract(req.jd_text, resume)

        # Semantic matching
        matched, missing, score = semantic_match(jd_skills, resume_skills)

        # Action plan
        suggestions, summary = await generate_action_plan(req.jd_text, missing, score)

    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("JD analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis error: {e}")

    return JDResponse(
        score=score,
        matched_skills=matched[:20],
        missing_skills=missing[:20],
        suggestions=suggestions,
        summary=summary,
    )


async def _parallel_extract(jd_text: str, resume_text: str):
    """Run JD and resume extraction concurrently."""
    import asyncio
    jd_skills, resume_skills = await asyncio.gather(
        extract_skills(jd_text, "Job Description"),
        extract_skills(resume_text, "Resume"),
    )
    return jd_skills, resume_skills
