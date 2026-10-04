"""Correction agent (spec §20).

Takes the current resume plus rule + judge feedback and produces a corrected
CustomizedResume. The same deterministic sanitizer used by the customizer is
re-applied so corrections can never reintroduce fabricated facts.
"""

from __future__ import annotations

import json
from typing import Any

from agents.resume_customizer import _sanitize_resume
from config.logging_config import get_logger
from llm.factory import get_llm
from models.resume_models import CustomizedResume, MasterProfile
from models.validation_models import LLMJudgeResult, RuleValidationResult
from tools.file_utils import load_prompt

logger = get_logger(__name__)


def correct_resume(
    resume: CustomizedResume,
    profile: MasterProfile,
    rule: RuleValidationResult,
    judge: LLMJudgeResult,
    confirmed_skills: list[str] | None = None,
    llm: Any | None = None,
) -> CustomizedResume:
    """Produce a corrected resume addressing rule + judge feedback."""
    confirmed_skills = confirmed_skills or []
    logger.info(
        "Correction started (rule_errors=%d, judge_issues=%d)",
        len(rule.errors), len(judge.issues),
    )

    # Low temperature -> deterministic, consistent corrections.
    model = llm if llm is not None else get_llm(temperature=0.0)
    structured = model.with_structured_output(CustomizedResume)

    payload = {
        "profile": profile.model_dump(),
        "confirmed_skills": confirmed_skills,
        "resume": resume.model_dump(),
        "rule_errors": rule.errors,
        "rule_warnings": rule.warnings,
        "judge_issues": judge.issues,
        "judge_corrections": judge.corrections,
    }
    messages = [
        ("system", load_prompt("correction_agent")),
        ("human", json.dumps(payload, ensure_ascii=False)),
    ]
    result = structured.invoke(messages)
    corrected = (
        result if isinstance(result, CustomizedResume)
        else CustomizedResume.model_validate(result)
    )

    # Re-apply the fabrication guard so corrections stay factual.
    corrected = _sanitize_resume(corrected, profile, confirmed_skills)
    logger.info("Correction complete")
    return corrected
