"""Validation models (spec §18 & §19).

Deterministic ATS rule results and LLM-judge semantic results. Logic is added
in Phase 1E; Phase 0 defines the shapes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RuleValidationResult(BaseModel):
    """Deterministic ATS rule-check result (spec §18)."""

    status: Literal["PASS", "FAIL"] = "PASS"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    page_count: int = 0


class LLMJudgeResult(BaseModel):
    """Semantic quality judgement (spec §19).

    Issues and corrections matter more than a numeric score.
    """

    status: Literal["PASS", "FAIL"] = "PASS"
    issues: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
