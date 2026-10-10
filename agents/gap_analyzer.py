"""Gap Analysis agent (spec §14).

Compares the master profile against the structured JD and classifies each job
skill (matched / partial / working_knowledge / missing) with evidence, plus the
most relevant projects/experience and keyword gaps. Classification only — it
never invents experience.
"""

from __future__ import annotations

import json
import re
from typing import Any

from config.logging_config import get_logger
from llm.factory import get_llm
from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import GapAnalysis, MasterProfile, SkillClassification
from tools.file_utils import load_prompt

logger = get_logger(__name__)

# Known equivalent-skill groups so e.g. a JD "Spark" isn't flagged "missing" when
# the profile lists "PySpark". Normalized (alphanumeric, lowercase).
_SYNONYMS = [
    {"spark", "pyspark", "apachespark"},
    {"postgresql", "postgres"},
    {"javascript", "js"}, {"typescript", "ts"},
    {"kubernetes", "k8s"}, {"scikitlearn", "sklearn"},
    {"tensorflow", "tf"}, {"amazonwebservices", "aws"},
    {"googlecloudplatform", "gcp"}, {"microsoftazure", "azure"},
    {"nodejs", "node"}, {"restapi", "rest", "restfulapi"},
    {"cicd", "cicdpipelines"}, {"nlp", "naturallanguageprocessing"},
    {"machinelearning", "ml"}, {"deeplearning", "dl"},
    {"powerbi", "powerbidesktop"}, {"githubactions", "ghactions"},
]


def _normkey(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _variants(norm: str) -> set[str]:
    out = {norm, "py" + norm, "apache" + norm}
    for group in _SYNONYMS:
        if norm in group:
            out |= group
    return out


def _covered_by_profile(skill: str, profile_norms: set[str]) -> bool:
    """True if a JD skill is effectively present in the profile via a variant."""
    sn = _normkey(skill)
    if not sn:
        return False
    variants = _variants(sn)
    for pn in profile_norms:
        if not pn:
            continue
        if pn in variants or sn in _variants(pn):
            return True
        # e.g. profile "pyspark" / "apachespark" covers JD "spark"
        if len(sn) >= 5 and pn.endswith(sn):
            return True
        if len(pn) >= 5 and sn.endswith(pn):
            return True
    return False


def _absorb_covered(gap: GapAnalysis, profile: MasterProfile) -> GapAnalysis:
    """Move 'missing' skills that the profile actually covers (via variants) to matched.

    Prevents false mismatches like Spark vs PySpark.
    """
    profile_norms = {_normkey(s) for s in profile.skills}
    for pr in profile.projects:
        profile_norms |= {_normkey(t) for t in pr.technologies}

    still_missing = []
    for item in gap.missing_skills:
        if _covered_by_profile(item.skill, profile_norms):
            gap.matched_skills.append(SkillClassification(
                skill=item.skill, status="matched",
                evidence="Covered by an equivalent skill in your profile"))
        else:
            still_missing.append(item)
    gap.missing_skills = still_missing
    return gap

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
    # Only offer atomic skills — never full JD requirement sentences.
    from tools.skills import clean_skills

    return clean_skills(out)


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
    gap = _absorb_covered(gap, profile)  # treat skill variants (Spark≈PySpark) as matched
    logger.info(
        "Gap analysis completed (matched=%d, partial=%d, working=%d, missing=%d)",
        len(gap.matched_skills),
        len(gap.partial_skills),
        len(gap.working_knowledge),
        len(gap.missing_skills),
    )
    return gap
