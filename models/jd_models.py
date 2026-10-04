"""Job-description models (spec §10 & §11).

Phase 0 defines the schema shapes. Parsing/analysis logic is added in Phase 1B.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ExtractionStatus = Literal["SUCCESS", "REQUEST_MANUAL_INPUT", "ERROR"]


class JDExtractionResult(BaseModel):
    """Outcome of attempting to extract a JD from a URL (spec §9)."""

    status: ExtractionStatus
    raw_jd: str = ""
    source: str = ""          # "http", "playwright", or ""
    message: str = ""         # user-facing note on failure/fallback


class JobDescription(BaseModel):
    """Structured representation of a parsed job description (spec §10)."""

    job_title: str = ""
    company: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class JDAnalysis(BaseModel):
    """Prioritized view of what matters for the role (spec §11)."""

    critical_skills: list[str] = Field(default_factory=list)
    important_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    core_responsibilities: list[str] = Field(default_factory=list)
    important_keywords: list[str] = Field(default_factory=list)
    role_focus: list[str] = Field(default_factory=list)
