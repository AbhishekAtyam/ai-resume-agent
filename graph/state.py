"""Centralized LangGraph state (spec §21).

Keep the state serializable: store file *paths/references*, never large binary
blobs. Graph nodes are wired up in later phases.
"""

from __future__ import annotations

from typing import TypedDict


class ResumeState(TypedDict, total=False):
    """Shared state threaded through the LangGraph resume workflow."""

    # Identity
    user_id: str
    profile_id: str

    # Raw inputs (one of these is provided by the user)
    job_url: str | None
    pasted_jd: str | None

    # JD processing
    raw_jd: str
    structured_jd: dict
    jd_analysis: dict

    # Profile + matching
    master_profile: dict
    gap_analysis: dict

    # Generation
    customized_resume: dict
    resume_docx_path: str | None
    resume_pdf_path: str | None

    # Validation
    rule_validation: dict
    llm_validation: dict

    # Control flow
    retry_count: int
    status: str
    errors: list[str]
