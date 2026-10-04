"""Generation + validation orchestration (spec §20, §22).

Implements the bounded generate -> format -> rule_validate -> llm_validate ->
(correct -> repeat) loop. The retry count is capped by settings.max_retries, so
there are at most (max_retries + 1) total attempts — never an infinite loop.

This is a deterministic Python orchestration (functions map 1:1 onto the planned
LangGraph nodes); a full StateGraph wiring can replace it later without changing
the agent logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.ats_validator import validate_ats
from agents.correction_agent import correct_resume
from agents.llm_judge import judge_resume
from agents.resume_customizer import customize_resume
from agents.resume_formatter import format_resume
from config.logging_config import get_logger
from config.settings import settings
from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import CustomizedResume, GapAnalysis, MasterProfile

logger = get_logger(__name__)


def generate_and_validate(
    profile: MasterProfile,
    jd: JobDescription,
    jd_analysis: JDAnalysis | None,
    gap: GapAnalysis | None,
    confirmed_skills: list[str] | None,
    out_dir: str | Path,
    basename: str = "resume",
    llm: Any | None = None,
    progress: Any | None = None,
) -> dict:
    """Run the generate/validate/correct loop and return the best result.

    Returns a dict with: resume, pdf_path, docx_path, page_count, rule, llm,
    attempts (list of per-attempt summaries), status
    ("PASS" or "PASS_WITH_WARNINGS").

    `progress` is an optional callable(message:str) for live UI updates.
    """
    confirmed_skills = confirmed_skills or []
    max_attempts = settings.max_retries + 1
    attempts: list[dict] = []

    def _emit(msg: str) -> None:
        if progress:
            try:
                progress(msg)
            except Exception:  # noqa: BLE001 - UI callback must never break the loop
                pass

    logger.info("Resume generation attempt 1")
    _emit("Customizing resume to the job…")
    resume = customize_resume(
        profile, jd, jd_analysis, gap, confirmed_skills=confirmed_skills, llm=llm
    )

    fmt_result: dict = {}
    rule = None
    verdict = None
    final_status = "PASS_WITH_WARNINGS"

    for attempt in range(1, max_attempts + 1):
        _emit(f"Attempt {attempt}: rendering PDF/DOCX & fitting pages…")
        fmt_result = format_resume(resume, out_dir, basename=basename)
        _emit(f"Attempt {attempt}: running ATS rule checks…")
        rule = validate_ats(resume, fmt_result)
        _emit(f"Attempt {attempt}: LLM judge reviewing for unsupported claims…")
        verdict = judge_resume(
            resume, jd, profile, jd_analysis, confirmed_skills, llm=llm
        )

        attempts.append({
            "attempt": attempt,
            "rule_status": rule.status,
            "llm_status": verdict.status,
            "page_count": rule.page_count,
            "errors": list(rule.errors),
            "issues": list(verdict.issues),
        })
        logger.info(
            "Attempt %d: rule=%s, llm=%s, pages=%d",
            attempt, rule.status, verdict.status, rule.page_count,
        )

        if rule.status == "PASS" and verdict.status == "PASS":
            final_status = "PASS"
            logger.info("Validation passed on attempt %d", attempt)
            break

        if attempt >= max_attempts:
            final_status = "PASS_WITH_WARNINGS"
            logger.warning(
                "Max attempts (%d) reached; returning best result with warnings",
                max_attempts,
            )
            break

        logger.info("Validation found issues; regenerating (attempt %d)", attempt + 1)
        _emit(f"Found issues — applying corrections (attempt {attempt + 1})…")
        resume = correct_resume(
            resume, profile, rule, verdict,
            confirmed_skills=confirmed_skills, llm=llm,
        )

    return {
        "resume": resume,
        "pdf_path": fmt_result.get("pdf_path"),
        "docx_path": fmt_result.get("docx_path"),
        "page_count": fmt_result.get("page_count", 0),
        "rule": rule,
        "llm": verdict,
        "attempts": attempts,
        "status": final_status,
    }
