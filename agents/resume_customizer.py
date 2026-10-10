"""Resume Customizer agent (spec §15).

Produces a job-tailored CustomizedResume from the master profile, JD analysis,
gap analysis, and user-confirmed skills. A deterministic sanitizer enforces the
no-fabrication rule after the LLM step: facts come from the profile; skills are
restricted to profile skills + confirmed skills.
"""

from __future__ import annotations

import json
import re
from typing import Any

from config.logging_config import get_logger
from llm.factory import get_llm
from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import CustomizedResume, MasterProfile
from tools.file_utils import load_prompt

logger = get_logger(__name__)


def _norm(s: str) -> str:
    """Normalize for matching: lowercase, strip non-alphanumerics."""
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _allowed_skill_set(profile: MasterProfile, confirmed: list[str]) -> dict[str, str]:
    """Map normalized skill -> canonical display name (profile + confirmed)."""
    allowed: dict[str, str] = {}
    for s in list(profile.skills) + list(confirmed or []):
        key = _norm(s)
        if key and key not in allowed:
            allowed[key] = s.strip()
    return allowed


def _sanitize_resume(
    cust: CustomizedResume,
    profile: MasterProfile,
    confirmed: list[str],
) -> CustomizedResume:
    """Enforce factual integrity on the LLM output (deterministic guard)."""
    # 1. Personal + education + certifications + languages/hobbies: facts from profile.
    cust.personal = profile.personal.model_copy(deep=True)
    cust.education = [e.model_copy(deep=True) for e in profile.education]
    cust.certifications = list(profile.certifications)
    cust.languages = list(profile.languages)
    cust.hobbies = list(profile.hobbies)

    # 2. Skills: only allowed + ATOMIC skills (no JD sentences), LLM casing. Core profile
    #    skills come FIRST (in the LLM's relevance order); runtime-confirmed skills go to
    #    the END. clean_skills() enforces atomicity + near-duplicate removal.
    from tools.skills import clean_skills

    allowed = _allowed_skill_set(profile, confirmed)
    profile_norms = {_norm(s) for s in profile.skills}
    seen: set[str] = set()
    core: list[str] = []
    added: list[str] = []
    for s in cust.skills:
        k = _norm(s)
        if k in allowed and k not in seen:
            seen.add(k)
            (core if k in profile_norms else added).append(s.strip())
    for s in confirmed or []:  # ensure every confirmed skill appears, at the end
        k = _norm(s)
        if k and k not in seen:
            seen.add(k)
            added.append(s.strip())
    cust.skills = clean_skills(core + added)

    # 3. Experience: take factual fields from the matching profile entry; keep LLM
    #    bullets. Drop any entry that doesn't match a real profile role.
    unused = list(profile.experience)
    sanitized_exp = []
    for e in cust.experience:
        match = None
        for i, pe in enumerate(unused):
            if _norm(pe.company) == _norm(e.company) or (
                _norm(pe.title) == _norm(e.title) and _norm(pe.title)
            ):
                match = unused.pop(i)
                break
        if match is None:
            continue  # invented role -> drop
        match = match.model_copy(deep=True)
        if e.bullets:  # allow rephrased bullets, keep factual header
            match.bullets = e.bullets
        sanitized_exp.append(match)
    cust.experience = sanitized_exp or [e.model_copy(deep=True) for e in profile.experience]

    # 4. Projects: match by name; keep factual name/link, allow rephrased content.
    unused_p = list(profile.projects)
    sanitized_proj = []
    for pr in cust.projects:
        match = None
        for i, pp in enumerate(unused_p):
            if _norm(pp.name) and _norm(pp.name) == _norm(pr.name):
                match = unused_p.pop(i)
                break
        if match is None:
            continue
        match = match.model_copy(deep=True)
        if pr.bullets:
            match.bullets = pr.bullets
        if pr.description:
            match.description = pr.description
        if pr.technologies:  # keep only clean, atomic technologies
            match.technologies = clean_skills(pr.technologies)
        sanitized_proj.append(match)
    cust.projects = sanitized_proj or [p.model_copy(deep=True) for p in profile.projects]

    # 5. Prose ↔ Skills consistency: if a real (profile/confirmed) skill is named in the
    #    summary or any bullet but got dropped from the Skills list, add it back — so the
    #    resume never mentions a tool it doesn't also list as a skill.
    present = {_norm(s) for s in cust.skills}
    blob = " ".join(
        [cust.summary]
        + [b for e in cust.experience for b in e.bullets]
        + [b for pr in cust.projects for b in pr.bullets]
        + [pr.description for pr in cust.projects]
    ).lower()
    for key, display in allowed.items():
        if key and key not in present and display.lower() in blob:
            cust.skills.append(display)
            present.add(key)
    cust.skills = clean_skills(cust.skills)

    return cust


def customize_resume(
    profile: MasterProfile,
    jd: JobDescription,
    jd_analysis: JDAnalysis | None = None,
    gap: Any | None = None,
    confirmed_skills: list[str] | None = None,
    llm: Any | None = None,
) -> CustomizedResume:
    """Generate a job-tailored, fact-safe CustomizedResume."""
    confirmed_skills = confirmed_skills or []
    logger.info(
        "Resume customization started (job=%s, confirmed_skills=%d)",
        jd.job_title or "unknown",
        len(confirmed_skills),
    )

    # Low temperature -> stable, consistent output run-to-run (less randomness).
    model = llm if llm is not None else get_llm(temperature=0.0)
    structured = model.with_structured_output(CustomizedResume)

    payload = {
        "job": {
            "title": jd.job_title,
            "role_focus": jd_analysis.role_focus if jd_analysis else [],
            "critical_skills": jd_analysis.critical_skills if jd_analysis else [],
            "important_skills": jd_analysis.important_skills if jd_analysis else [],
        },
        "gap": {
            "matched": [s.skill for s in gap.matched_skills] if gap else [],
            "missing": [s.skill for s in gap.missing_skills] if gap else [],
        },
        "profile": profile.model_dump(),
        "confirmed_skills": confirmed_skills,
    }
    messages = [
        ("system", load_prompt("resume_customizer")),
        ("human", json.dumps(payload, ensure_ascii=False)),
    ]
    result = structured.invoke(messages)
    cust = (
        result
        if isinstance(result, CustomizedResume)
        else CustomizedResume.model_validate(result)
    )

    cust = _sanitize_resume(cust, profile, confirmed_skills)
    logger.info(
        "Resume customization complete (skills=%d, experience=%d, projects=%d)",
        len(cust.skills),
        len(cust.experience),
        len(cust.projects),
    )
    return cust
