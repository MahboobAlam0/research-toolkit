# ─── backend/models/schemas.py ────────────────────────────────────────────────
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

_SOURCE_PATTERN = r"^(arxiv|pubmed|semantic_scholar)$"


class PaperIngest(BaseModel):
    title:    str        = Field(..., min_length=1, max_length=500)
    abstract: str        = Field(..., min_length=1, max_length=12000)
    authors:  List[str]  = Field(default=[], max_length=100)
    url:      str        = Field(..., max_length=2000)
    source:   str        = Field(..., pattern=_SOURCE_PATTERN)
    paper_id: str        = Field(..., min_length=1, max_length=200)


class PaperRecord(BaseModel):
    id:       str
    title:    str
    authors:  List[str]
    url:      str
    source:   str
    paper_id: str
    saved_at: str


class ChatMessage(BaseModel):
    role:    str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatQuery(BaseModel):
    query:   str              = Field(..., min_length=1, max_length=1000)
    history: List[ChatMessage] = Field(default=[])
    top_k:   int              = Field(default=5, ge=1, le=20)


class SourceRef(BaseModel):
    title: str
    url:   str
    score: float


class ChatResponse(BaseModel):
    answer:  str
    sources: List[SourceRef] = []


class JDRequest(BaseModel):
    jd_text:     str           = Field(..., min_length=10, max_length=6000)
    resume_text: Optional[str] = Field(default=None, max_length=6000)


class JDResponse(BaseModel):
    score:          float       # 0.0 – 1.0
    matched_skills: List[str]
    missing_skills: List[str]
    suggestions:    List[str]
    summary:        str
