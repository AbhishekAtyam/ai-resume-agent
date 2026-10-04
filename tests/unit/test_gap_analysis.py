"""Unit tests for the Gap Analysis agent (deterministic fake LLM, no live calls)."""

from __future__ import annotations

import json

from models.jd_models import JDAnalysis, JobDescription
from models.resume_models import GapAnalysis, MasterProfile


class _FakeStructured:
    def __init__(self, result, capture):
        self._result = result
        self._capture = capture

    def invoke(self, messages):
        self._capture["messages"] = messages
        return self._result


class _FakeLLM:
    def __init__(self, result):
        self._result = result
        self.capture: dict = {}

    def with_structured_output(self, schema):
        assert schema is GapAnalysis
        return _FakeStructured(self._result, self.capture)


def _sample_profile() -> MasterProfile:
    return MasterProfile(
        skills=["Python", "SQL", "Spark"],
        experience=[
            {"title": "Data Engineer", "company": "Acme", "bullets": ["Built ETL"]}
        ],
        projects=[{"name": "Lakehouse", "technologies": ["Spark"], "bullets": ["x"]}],
    )


def _sample_jd() -> JobDescription:
    return JobDescription(
        job_title="Data Engineer",
        required_skills=["Python", "SQL", "Snowflake"],
        preferred_skills=["Kafka"],
    )


def test_analyze_gap_returns_model():
    from agents.gap_analyzer import analyze_gap

    expected = GapAnalysis(
        matched_skills=[{"skill": "Python", "status": "matched", "evidence": "Listed"}],
        missing_skills=[
            {"skill": "Snowflake", "status": "missing", "evidence": "No evidence in profile"}
        ],
        relevant_experience=["Data Engineer @ Acme"],
    )
    gap = analyze_gap(_sample_profile(), _sample_jd(), None, llm=_FakeLLM(expected))
    assert gap.matched_skills[0].skill == "Python"
    assert gap.missing_skills[0].status == "missing"
    assert "Data Engineer @ Acme" in gap.relevant_experience


def test_analyze_gap_normalizes_dict():
    from agents.gap_analyzer import analyze_gap

    result = {
        "matched_skills": [],
        "missing_skills": [{"skill": "Kafka", "status": "missing", "evidence": "none"}],
    }
    gap = analyze_gap(_sample_profile(), _sample_jd(), None, llm=_FakeLLM(result))
    assert isinstance(gap, GapAnalysis)
    assert gap.missing_skills[0].skill == "Kafka"


def test_reconcile_demotes_evidenceless_matched_to_missing():
    """A 'matched' skill whose evidence asserts absence must become 'missing'."""
    from agents.gap_analyzer import reconcile_gap

    messy = GapAnalysis(
        matched_skills=[
            {"skill": "Python", "status": "matched", "evidence": "Listed in skills"},
            # Model error: matched but evidence says there's none.
            {"skill": "Snowflake", "status": "matched", "evidence": "No evidence in profile"},
        ],
        missing_skills=[
            # Same skill duplicated in missing.
            {"skill": "Snowflake", "status": "missing", "evidence": "No evidence in profile"},
        ],
    )
    fixed = reconcile_gap(messy)
    matched = {s.skill for s in fixed.matched_skills}
    missing = {s.skill for s in fixed.missing_skills}
    assert "Python" in matched
    assert "Snowflake" not in matched          # demoted
    assert "Snowflake" in missing
    # No duplication across buckets.
    assert len(fixed.missing_skills) == 1


def test_reconcile_keeps_highest_valid_bucket_once():
    from agents.gap_analyzer import reconcile_gap

    messy = GapAnalysis(
        matched_skills=[{"skill": "SQL", "status": "matched", "evidence": "Used in role"}],
        partial_skills=[{"skill": "SQL", "status": "partial", "evidence": "some sql"}],
    )
    fixed = reconcile_gap(messy)
    assert [s.skill for s in fixed.matched_skills] == ["SQL"]
    assert fixed.partial_skills == []


def test_candidate_skills_for_confirmation_excludes_matched_and_dedupes():
    from agents.gap_analyzer import candidate_skills_for_confirmation

    gap = GapAnalysis(
        matched_skills=[{"skill": "Python", "status": "matched", "evidence": "x"}],
        partial_skills=[{"skill": "Kafka", "status": "partial", "evidence": "x"}],
        working_knowledge=[{"skill": "dbt", "status": "working_knowledge", "evidence": "x"}],
        missing_skills=[{"skill": "Snowflake", "status": "missing", "evidence": "none"}],
        keyword_gaps=["Snowflake", "Spark", "Python", "time-series analytics"],
    )
    candidates = candidate_skills_for_confirmation(gap)
    # Matched skill excluded; duplicates (Snowflake, Python) removed.
    assert "Python" not in candidates
    assert candidates.count("Snowflake") == 1
    assert "Kafka" in candidates and "dbt" in candidates
    assert "Spark" in candidates
    assert "time-series analytics" in candidates


def test_has_real_evidence():
    from agents.gap_analyzer import _has_real_evidence

    assert _has_real_evidence("Listed in skills; used in Project X") is True
    assert _has_real_evidence("No evidence in profile") is False
    assert _has_real_evidence("") is False
    assert _has_real_evidence("none") is False


def test_payload_includes_profile_and_job_but_not_fabricated():
    """The matcher is fed real profile + job data (serializable JSON)."""
    from agents.gap_analyzer import _build_payload

    payload = _build_payload(
        _sample_profile(), _sample_jd(), JDAnalysis(critical_skills=["Python"])
    )
    # Round-trips as JSON (LLM input must be serializable).
    text = json.dumps(payload)
    assert "Python" in text
    assert "Snowflake" in text  # job requirement present for classification
    assert payload["profile"]["skills"] == ["Python", "SQL", "Spark"]
    assert payload["analysis"]["critical_skills"] == ["Python"]
