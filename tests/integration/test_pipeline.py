"""End-to-end pipeline integration tests using a deterministic mock LLM.

These exercise the real agents + deterministic rendering/validation/orchestration
together (no live Ollama). Only the LLM outputs are mocked, per-schema.
"""

from __future__ import annotations

import pytest

from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import CustomizedResume, GapAnalysis, MasterProfile
from models.validation_models import LLMJudgeResult


# --------------------------------------------------------------------------- #
# A flexible mock LLM that returns schema-appropriate fixtures.
# --------------------------------------------------------------------------- #
class _Bound:
    def __init__(self, parent, schema):
        self.p, self.schema = parent, schema

    def invoke(self, messages):
        s = self.schema
        if s is CustomizedResume:
            return self.p.resume
        if s is LLMJudgeResult:
            idx = min(self.p._ji, len(self.p.judge) - 1)
            self.p._ji += 1
            return self.p.judge[idx]
        if s is JobDescription:
            return self.p.jd
        if s is JDAnalysis:
            return self.p.analysis
        if s is GapAnalysis:
            return self.p.gap
        if s is MasterProfile:
            return self.p.profile_struct
        raise AssertionError(f"Unexpected schema: {s}")


class FakeLLM:
    def __init__(self, *, resume=None, jd=None, analysis=None, gap=None,
                 profile_struct=None, judge=None):
        self.resume = resume
        self.jd = jd
        self.analysis = analysis
        self.gap = gap
        self.profile_struct = profile_struct
        self.judge = judge or [LLMJudgeResult(status="PASS")]
        self._ji = 0

    def with_structured_output(self, schema):
        return _Bound(self, schema)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _profile() -> MasterProfile:
    return MasterProfile(
        personal={"name": "Jane Doe", "email": "jane@example.com", "phone": "12345",
                  "location": "Hyderabad"},
        summary="Data engineer with ETL experience.",
        skills=["Python", "SQL", "Spark"],
        experience=[{"title": "Data Engineer", "company": "Acme", "start_date": "2021",
                     "end_date": "Present", "bullets": ["Built ETL pipelines",
                                                        "Optimized SQL models"]}],
        projects=[{"name": "Lakehouse", "technologies": ["Spark"],
                   "bullets": ["Streaming pipeline"]}],
        education=[{"degree": "B.Tech", "institution": "VNR", "end_year": "2020",
                    "grade": "9.1"}],
        certifications=["AWS DA"],
    )


def _resume_from(profile: MasterProfile) -> CustomizedResume:
    """A CustomizedResume consistent with the profile (survives the sanitizer)."""
    return CustomizedResume(
        personal=profile.personal.model_dump(),
        summary="Tailored data engineer summary.",
        skills=["Python", "SQL", "Spark"],
        experience=[e.model_dump() for e in profile.experience],
        projects=[p.model_dump() for p in profile.projects],
        education=[e.model_dump() for e in profile.education],
        certifications=list(profile.certifications),
    )


def _jd() -> JobDescription:
    return JobDescription(job_title="Data Engineer", company="BigCo",
                          required_skills=["Python", "SQL", "Snowflake"])


@pytest.fixture
def ctx():
    profile = _profile()
    return {
        "profile": profile,
        "jd": _jd(),
        "analysis": JDAnalysis(critical_skills=["Python", "SQL"], role_focus=["ETL"]),
        "gap": GapAnalysis(),
        "resume": _resume_from(profile),
    }


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_full_generation_passes_first_try(tmp_path, ctx):
    from graph.graph import generate_and_validate

    llm = FakeLLM(resume=ctx["resume"], judge=[LLMJudgeResult(status="PASS")])
    result = generate_and_validate(
        ctx["profile"], ctx["jd"], ctx["analysis"], ctx["gap"],
        confirmed_skills=["Snowflake"], out_dir=tmp_path, basename="r", llm=llm,
    )
    assert result["status"] == "PASS"
    assert len(result["attempts"]) == 1
    assert (tmp_path / "r.pdf").exists() and (tmp_path / "r.docx").exists()
    assert 1 <= result["page_count"] <= 2
    # Confirmed skill allowed; nothing fabricated beyond profile + confirmed.
    allowed = {s.lower() for s in ctx["profile"].skills} | {"snowflake"}
    assert all(s.lower() in allowed for s in result["resume"].skills)


def test_generation_recovers_via_correction(tmp_path, ctx):
    from graph.graph import generate_and_validate

    # Judge fails once (unsupported claim) then passes after correction.
    llm = FakeLLM(
        resume=ctx["resume"],
        judge=[LLMJudgeResult(status="FAIL", issues=["Invented metric"],
                              corrections=["Remove it"]),
               LLMJudgeResult(status="PASS")],
    )
    result = generate_and_validate(
        ctx["profile"], ctx["jd"], ctx["analysis"], ctx["gap"],
        confirmed_skills=[], out_dir=tmp_path, basename="r", llm=llm,
    )
    assert result["status"] == "PASS"
    assert len(result["attempts"]) == 2  # one correction round


def test_generation_exhausts_retries_without_infinite_loop(tmp_path, ctx):
    from config.settings import settings
    from graph.graph import generate_and_validate

    llm = FakeLLM(resume=ctx["resume"],
                  judge=[LLMJudgeResult(status="FAIL", issues=["bad"])])  # always fails
    result = generate_and_validate(
        ctx["profile"], ctx["jd"], ctx["analysis"], ctx["gap"],
        confirmed_skills=[], out_dir=tmp_path, basename="r", llm=llm,
    )
    assert result["status"] == "PASS_WITH_WARNINGS"
    assert len(result["attempts"]) == settings.max_retries + 1


def test_jd_processing_chain(ctx):
    """parse -> analyze -> gap using the real agents with mocked LLM outputs."""
    from agents.gap_analyzer import analyze_gap
    from agents.jd_analyzer import analyze_jd
    from agents.jd_parser import parse_jd

    llm = FakeLLM(jd=ctx["jd"], analysis=ctx["analysis"],
                  gap=GapAnalysis(
                      matched_skills=[{"skill": "Python", "status": "matched",
                                       "evidence": "listed"}],
                      missing_skills=[{"skill": "Snowflake", "status": "missing",
                                       "evidence": "No evidence in profile"}]))
    jd = parse_jd("raw jd text", llm=llm)
    analysis = analyze_jd(jd, llm=llm)
    gap = analyze_gap(ctx["profile"], jd, analysis, llm=llm)

    assert jd.job_title == "Data Engineer"
    assert "Python" in analysis.critical_skills
    assert {s.skill for s in gap.matched_skills} == {"Python"}
    assert {s.skill for s in gap.missing_skills} == {"Snowflake"}
