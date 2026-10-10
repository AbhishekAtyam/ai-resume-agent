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

    # Job-fit: how well the resume covers the role's HARD skills, measured against the
    # whole resume (skills + confirmed + summary + bullets) — not just the Skills list.
    fit_score, missing_critical = job_fit_coverage(jd, jd_analysis, resume, confirmed_skills)
    structural = rule.score if rule is not None else 0
    overall = round(0.5 * structural + 0.5 * fit_score) if fit_score is not None \
        else structural

    return {
        "resume": resume,
        "pdf_path": fmt_result.get("pdf_path"),
        "docx_path": fmt_result.get("docx_path"),
        "page_count": fmt_result.get("page_count", 0),
        "rule": rule,
        "llm": verdict,
        "attempts": attempts,
        "status": final_status,
        "structural_score": structural,
        "fit_score": fit_score,
        "missing_critical": missing_critical,
        "overall_score": overall,
    }


_FIT_STOP = {"of", "to", "and", "the", "for", "with", "in", "a", "an", "or", "on",
             "skills", "experience", "ability", "knowledge"}


def _resume_text(resume) -> str:
    parts = [resume.summary]
    parts += [b for e in resume.experience for b in e.bullets]
    parts += [b for p in resume.projects for b in p.bullets]
    parts += [p.description for p in resume.projects]
    parts += [t for p in resume.projects for t in p.technologies]
    return " ".join(parts).lower()


def _in_text(skill: str, text: str) -> bool:
    """Lenient: the skill (or all its content words) appears somewhere in the resume."""
    s = skill.lower().strip()
    if s and s in text:
        return True
    import re as _re

    words = [w for w in _re.split(r"[^a-z0-9+#]+", s) if len(w) > 2 and w not in _FIT_STOP]
    return bool(words) and all(w in text for w in words)


def job_fit_coverage(jd, jd_analysis, resume, confirmed_skills):
    """Return (fit_percent, missing_skills) over the role's hard skills.

    Denominator = required_skills + tools_and_technologies (atomic), falling back to
    the analysis' critical skills. A skill counts as covered if a variant is in the
    resume's Skills/confirmed list OR it appears anywhere in the resume text.
    """
    from agents.gap_analyzer import _covered_by_profile, _normkey
    from tools.skills import clean_skills

    denom = clean_skills(list(jd.required_skills) + list(jd.tools_and_technologies)) \
        if jd else []
    if not denom and jd_analysis:
        denom = clean_skills(jd_analysis.critical_skills)
    if not denom:
        return None, []

    norms = {_normkey(s) for s in resume.skills}
    norms |= {_normkey(s) for s in (confirmed_skills or [])}
    text = _resume_text(resume)

    missing = [d for d in denom
               if not (_covered_by_profile(d, norms) or _in_text(d, text))]
    fit = round(100 * (len(denom) - len(missing)) / len(denom))
    return fit, missing
