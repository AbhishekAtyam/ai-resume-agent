"""Gap Analysis agent (spec §14).

Compares the master profile against the structured JD and classifies each job
skill (matched / partial / working_knowledge / missing) with evidence, plus the
most relevant projects/experience and keyword gaps. Classification only — it
never invents experience.
"""

from __future__ import annotations

import json
from typing import Any

from config.logging_config import get_logger
from llm.factory import get_llm
from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import GapAnalysis, MasterProfile, SkillClassification
from tools.file_utils import load_prompt

logger = get_logger(__name__)

# Bucket priority (highest claim first). Deterministic reconciliation uses this.
_PRIORITY = ["matched", "partial", "working_knowledge", "missing"]

# Phrases that indicate the "evidence" actually asserts there is no evidence.
_NO_EVIDENCE_MARKERS = (
    "no evidence", "not found", "not mentioned", "no mention", "absent",
    "none", "n/a", "not present", "not in profile", "does not",
)


def _has_real_evidence(evidence: str) -> bool:
    """True only if evidence is non-empty and doesn't assert absence."""
    e = (evidence or "").strip().lower()
    if not e:
        return False
    return not any(marker in e for marker in _NO_EVIDENCE_MARKERS)


def reconcile_gap(gap: GapAnalysis) -> GapAnalysis:
    """Enforce mutually-exclusive buckets and demote evidence-less claims.

    Deterministic guard against the LLM: a skill must appear in exactly one
    bucket, and any non-"missing" skill whose evidence asserts absence (or is
    empty) is demoted to "missing". When a skill appears in several buckets we
    keep the highest-priority *valid* one. This prevents false "matched" skills.
    """
    claimed = {
        "matched": gap.matched_skills,
        "partial": gap.partial_skills,
        "working_knowledge": gap.working_knowledge,
        "missing": gap.missing_skills,
    }

    # skill(lower) -> (priority_index, effective_status, original_item)
    best: dict[str, tuple[int, str, SkillClassification]] = {}
    for status in _PRIORITY:
        for item in claimed[status]:
            key = item.skill.strip().lower()
            if not key:
                continue
            effective = status
            if status != "missing" and not _has_real_evidence(item.evidence):
                effective = "missing"  # demote unsupported claim
            idx = _PRIORITY.index(effective)
            if key not in best or idx < best[key][0]:
                best[key] = (idx, effective, item)

    out: dict[str, list[SkillClassification]] = {s: [] for s in _PRIORITY}
    for _, (_, effective, item) in sorted(best.items()):
        evidence = item.evidence
        if effective == "missing" and not _has_real_evidence(evidence):
            evidence = "No evidence in profile"
        out[effective].append(
            SkillClassification(skill=item.skill, status=effective, evidence=evidence)
        )

    return GapAnalysis(
        matched_skills=out["matched"],
        partial_skills=out["partial"],
        working_knowledge=out["working_knowledge"],
        missing_skills=out["missing"],
        relevant_projects=gap.relevant_projects,
        relevant_experience=gap.relevant_experience,
        keyword_gaps=gap.keyword_gaps,
    )


def candidate_skills_for_confirmation(gap: GapAnalysis) -> list[str]:
    """Skills the user may want to confirm they actually have (HITL input).

    Union of partial + working_knowledge + missing skills and keyword gaps,
    excluding anything already MATCHED. Order-preserving, de-duplicated
    (case-insensitive). These are offered to the user as checkboxes; only
    user-confirmed ones may be added to the generated resume.
    """
    matched = {s.skill.strip().lower() for s in gap.matched_skills}
    seen: set[str] = set()
    out: list[str] = []

    def _add(name: str) -> None:
        key = name.strip().lower()
        if key and key not in matched and key not in seen:
            seen.add(key)
            out.append(name.strip())

    for s in gap.partial_skills + gap.working_knowledge + gap.missing_skills:
        _add(s.skill)
    for kw in gap.keyword_gaps:
        _add(kw)
    return out


def _build_payload(
    profile: MasterProfile,
    jd: JobDescription,
    jd_analysis: JDAnalysis | None,
) -> dict:
    """Assemble a compact, factual input for the matcher (no invented data)."""
    return {
        "job": {
            "title": jd.job_title,
            "required_skills": jd.required_skills,
            "preferred_skills": jd.preferred_skills,
            "tools_and_technologies": jd.tools_and_technologies,
            "keywords": jd.keywords,
        },
        "analysis": {
            "critical_skills": jd_analysis.critical_skills if jd_analysis else [],
            "important_skills": jd_analysis.important_skills if jd_analysis else [],
        },
        "profile": {
            "skills": profile.skills,
            "experience": [
                {
                    "title": e.title,
                    "company": e.company,
                    "bullets": e.bullets,
                }
                for e in profile.experience
            ],
            "projects": [
                {
                    "name": p.name,
                    "technologies": p.technologies,
                    "bullets": p.bullets,
                }
                for p in profile.projects
            ],
            "certifications": profile.certifications,
        },
    }


def analyze_gap(
    profile: MasterProfile,
    jd: JobDescription,
    jd_analysis: JDAnalysis | None = None,
    llm: Any | None = None,
) -> GapAnalysis:
    """Produce a GapAnalysis comparing the profile to the job."""
    logger.info("Gap analysis started (job=%s)", jd.job_title or "unknown")

    model = llm if llm is not None else get_llm()
    structured = model.with_structured_output(GapAnalysis)

    payload = _build_payload(profile, jd, jd_analysis)
    messages = [
        ("system", load_prompt("gap_analysis")),
        ("human", json.dumps(payload, ensure_ascii=False)),
    ]
    result = structured.invoke(messages)

    gap = result if isinstance(result, GapAnalysis) else GapAnalysis.model_validate(result)
    gap = reconcile_gap(gap)  # deterministic consistency guard
    logger.info(
        "Gap analysis completed (matched=%d, partial=%d, working=%d, missing=%d)",
        len(gap.matched_skills),
        len(gap.partial_skills),
        len(gap.working_knowledge),
        len(gap.missing_skills),
    )
    return gap
