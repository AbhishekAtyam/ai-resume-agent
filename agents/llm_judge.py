"""LLM Judge agent (spec §19).

Evaluates semantic quality and, most importantly, factual consistency of the
generated resume against the source profile (detecting unsupported claims and
invented numbers). Returns issues + corrections, not just a score.
"""

from __future__ import annotations

import json
from typing import Any

from config.logging_config import get_logger
from llm.factory import get_llm
from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import CustomizedResume, MasterProfile
from models.validation_models import LLMJudgeResult
from tools.file_utils import load_prompt

logger = get_logger(__name__)


def judge_resume(
    resume: CustomizedResume,
    jd: JobDescription,
    profile: MasterProfile,
    jd_analysis: JDAnalysis | None = None,
    confirmed_skills: list[str] | None = None,
    llm: Any | None = None,
) -> LLMJudgeResult:
    """Judge the generated resume for factual consistency + role relevance."""
    logger.info("LLM judge started (job=%s)", jd.job_title or "unknown")

    model = llm if llm is not None else get_llm()
    structured = model.with_structured_output(LLMJudgeResult)

    payload = {
        "job": {
            "title": jd.job_title,
            "critical_skills": jd_analysis.critical_skills if jd_analysis else [],
            "important_skills": jd_analysis.important_skills if jd_analysis else [],
            "role_focus": jd_analysis.role_focus if jd_analysis else [],
        },
        "profile": profile.model_dump(),
        "confirmed_skills": confirmed_skills or [],
        "resume": resume.model_dump(),
    }
    messages = [
        ("system", load_prompt("llm_judge")),
        ("human", json.dumps(payload, ensure_ascii=False)),
    ]
    result = structured.invoke(messages)

    verdict = (
        result if isinstance(result, LLMJudgeResult)
        else LLMJudgeResult.model_validate(result)
    )
    logger.info(
        "LLM judge %s (issues=%d, corrections=%d)",
        verdict.status, len(verdict.issues), len(verdict.corrections),
    )
    return verdict
