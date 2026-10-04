"""Unit tests for JD parser + analyzer (deterministic fake LLM, no live calls)."""

from __future__ import annotations

from models.jd_models import JDAnalysis, JobDescription


class _FakeStructured:
    def __init__(self, result):
        self._result = result

    def invoke(self, messages):
        assert any(role == "system" for role, _ in messages)
        assert any(role == "human" for role, _ in messages)
        return self._result


class _FakeLLM:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        return _FakeStructured(self._result)


def test_parse_jd_with_model_result():
    from agents.jd_parser import parse_jd

    expected = JobDescription(
        job_title="Data Engineer",
        company="Example Corp",
        required_skills=["Python", "SQL", "Spark"],
        preferred_skills=["Kafka"],
    )
    jd = parse_jd("raw jd text", llm=_FakeLLM(expected))
    assert jd.job_title == "Data Engineer"
    assert jd.required_skills == ["Python", "SQL", "Spark"]


def test_parse_jd_normalizes_dict():
    from agents.jd_parser import parse_jd

    jd = parse_jd("raw", llm=_FakeLLM({"job_title": "ML Engineer"}))
    assert isinstance(jd, JobDescription)
    assert jd.job_title == "ML Engineer"


def test_analyze_jd_with_model_result():
    from agents.jd_analyzer import analyze_jd

    jd = JobDescription(job_title="Data Engineer", required_skills=["Python"])
    expected = JDAnalysis(
        critical_skills=["Python", "SQL"],
        important_skills=["Databricks"],
        role_focus=["ETL", "data pipelines"],
    )
    analysis = analyze_jd(jd, llm=_FakeLLM(expected))
    assert analysis.critical_skills == ["Python", "SQL"]
    assert "ETL" in analysis.role_focus


def test_analyze_jd_normalizes_dict():
    from agents.jd_analyzer import analyze_jd

    jd = JobDescription(job_title="Data Engineer")
    analysis = analyze_jd(jd, llm=_FakeLLM({"role_focus": ["data"]}))
    assert isinstance(analysis, JDAnalysis)
    assert analysis.role_focus == ["data"]
