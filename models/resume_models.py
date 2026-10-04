"""Profile and resume models (spec §12 & §14).

The MasterProfile is the immutable source of truth. The CustomizedResume is a
separate, generated artifact derived from it — never a mutation of the profile.
Phase 0 defines shapes; generation logic arrives in Phases 1A/1C/1D.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PersonalInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    # Optional professional links — pulled if present, user may leave blank.
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""           # optional
    start_date: str = ""
    end_date: str = ""           # use "Present" for current roles
    bullets: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    link: str = ""              # optional
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str = ""
    institution: str = ""
    start_year: str = ""        # optional
    end_year: str = ""          # graduation/completion year
    grade: str = ""             # CGPA or percentage (e.g. "9.11" or "96.8%")


class MasterProfile(BaseModel):
    """Structured master resume — treated as immutable source data (spec §12)."""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    # Optional enrichment sections — used to fill a short resume toward 2 pages.
    achievements: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)


SkillStatus = Literal["matched", "partial", "working_knowledge", "missing"]


class SkillClassification(BaseModel):
    """A single skill classified against the master profile (spec §3 & §14)."""

    skill: str
    status: SkillStatus
    evidence: str = ""


class GapAnalysis(BaseModel):
    """JD-vs-profile comparison output (spec §14)."""

    matched_skills: list[SkillClassification] = Field(default_factory=list)
    partial_skills: list[SkillClassification] = Field(default_factory=list)
    working_knowledge: list[SkillClassification] = Field(default_factory=list)
    missing_skills: list[SkillClassification] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)
    relevant_experience: list[str] = Field(default_factory=list)
    keyword_gaps: list[str] = Field(default_factory=list)


class CustomizedResume(BaseModel):
    """Generated, job-specific resume (spec §15). Separate from MasterProfile."""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
