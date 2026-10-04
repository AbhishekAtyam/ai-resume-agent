"""Master Profile Agent (spec §5, §12, §13).

Turns raw resume text into a structured, validated `MasterProfile` using the LLM
via structured output. The profile is the immutable source of truth; this agent
only extracts — it never fabricates.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from config.logging_config import get_logger
from llm.factory import get_llm
from models.resume_models import MasterProfile
from tools.file_utils import load_prompt
from tools.resume_parser import extract_text

logger = get_logger(__name__)


def normalize_location(location: str) -> str:
    """Tidy a location string: collapse whitespace, fix comma spacing, trim.

    Turns "Hyderabad," -> "Hyderabad" and "Hyderabad ,India" -> "Hyderabad, India".
    """
    if not location:
        return ""
    cleaned = re.sub(r"\s*,\s*", ", ", location)      # normalize comma spacing
    cleaned = re.sub(r"\s+", " ", cleaned).strip()     # collapse whitespace
    cleaned = cleaned.strip(",").strip()               # drop leading/trailing commas
    return cleaned


def _normalize_profile(profile: MasterProfile) -> MasterProfile:
    """Light deterministic cleanup after LLM extraction (no content invention)."""
    profile.personal.location = normalize_location(profile.personal.location)
    return profile


def check_profile_completeness(profile: MasterProfile) -> list[str]:
    """Return human-readable labels for recommended fields that are empty.

    These are prompts for the user to complete once, accurately — not hard
    errors. Truly optional fields (links, hobbies, languages) are not listed.
    """
    missing: list[str] = []
    p = profile.personal
    if not p.name.strip():
        missing.append("Name")
    if not p.email.strip():
        missing.append("Email")
    if not p.phone.strip():
        missing.append("Phone")
    if not p.location.strip():
        missing.append("Location")
    if not profile.skills:
        missing.append("Skills")

    if not profile.experience:
        missing.append("At least one work experience")
    else:
        for i, e in enumerate(profile.experience, start=1):
            label = e.title or e.company or f"entry #{i}"
            if not e.start_date.strip() or not e.end_date.strip():
                missing.append(f"Start/end dates for experience: {label}")

    if not profile.education:
        missing.append("At least one education entry")
    else:
        for i, e in enumerate(profile.education, start=1):
            label = e.degree or e.institution or f"entry #{i}"
            if not e.end_year.strip():
                missing.append(f"Completion year for education: {label}")
            if not e.grade.strip():
                missing.append(f"Grade/CGPA for education: {label}")

    return missing


def structure_resume_text(resume_text: str, llm: Any | None = None) -> MasterProfile:
    """Convert raw resume text into a structured MasterProfile via the LLM.

    Args:
        resume_text: Plain text extracted from the resume.
        llm: Optional pre-built chat model (injectable for testing). When None,
             the central factory builds one.
    """
    logger.info("Structuring resume text into MasterProfile (%d chars)", len(resume_text))

    model = llm if llm is not None else get_llm()
    structured = model.with_structured_output(MasterProfile)

    system_prompt = load_prompt("profile_parser")
    messages = [
        ("system", system_prompt),
        ("human", resume_text),
    ]

    result = structured.invoke(messages)

    # with_structured_output may return a model instance or a dict depending on
    # the provider path; normalize to MasterProfile.
    if isinstance(result, MasterProfile):
        profile = result
    else:
        profile = MasterProfile.model_validate(result)

    profile = _normalize_profile(profile)

    logger.info(
        "Structured profile produced (skills=%d, experience=%d, projects=%d)",
        len(profile.skills),
        len(profile.experience),
        len(profile.projects),
    )
    return profile


def build_profile_from_file(path: str | Path, llm: Any | None = None) -> MasterProfile:
    """Extract text from a resume file and structure it into a MasterProfile."""
    text = extract_text(path)
    return structure_resume_text(text, llm=llm)
