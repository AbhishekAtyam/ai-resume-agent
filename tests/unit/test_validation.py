"""Unit tests for Phase 1E: ATS validator, LLM judge, correction, retry loop."""

from __future__ import annotations

from models.jd_models import JobDescription
from models.resume_models import CustomizedResume, MasterProfile
from models.validation_models import LLMJudgeResult, RuleValidationResult


def _good_resume() -> CustomizedResume:
    return CustomizedResume(
        personal={"name": "Jane Doe", "email": "jane@example.com", "phone": "12345"},
        summary="Experienced data engineer.",
        skills=["Python", "SQL", "Spark"],
        experience=[{"title": "Data Engineer", "company": "Acme",
                     "bullets": ["Built pipelines"]}],
        education=[{"degree": "B.Tech", "institution": "VNR", "end_year": "2020"}],
    )


# --- ATS validator (deterministic) ---
def test_ats_pass(tmp_path):
    from agents.ats_validator import validate_ats
    from agents.resume_formatter import format_resume

    resume = _good_resume()
    fmt = format_resume(resume, tmp_path, basename="ok")
    result = validate_ats(resume, fmt)
    assert result.status == "PASS"
    assert result.page_count >= 1


def test_ats_fails_on_missing_email_and_skills():
    from agents.ats_validator import validate_ats

    bad = CustomizedResume(personal={"name": "No Email"}, skills=[],
                           experience=[])
    result = validate_ats(bad, {"page_count": 1, "pdf_path": None})
    assert result.status == "FAIL"
    assert any("email" in e.lower() for e in result.errors)
    assert any("skills" in e.lower() for e in result.errors)
    assert any("experience" in e.lower() for e in result.errors)


def test_ats_fails_on_page_overflow():
    from agents.ats_validator import validate_ats

    result = validate_ats(_good_resume(), {"page_count": 3, "pdf_path": None})
    assert result.status == "FAIL"
    assert any("pages" in e.lower() for e in result.errors)


def test_ats_warns_on_missing_phone():
    from agents.ats_validator import validate_ats

    r = _good_resume()
    r.personal.phone = ""
    result = validate_ats(r, {"page_count": 1, "pdf_path": None})
    assert any("phone" in w.lower() for w in result.warnings)


# --- LLM judge (fake LLM) ---
class _FakeLLM:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        parent = self

        class _S:
            def invoke(self, messages):
                return parent._result

        return _S()


def test_judge_returns_verdict():
    from agents.llm_judge import judge_resume

    verdict = LLMJudgeResult(status="FAIL", issues=["Invented '40%'"],
                             corrections=["Remove the 40% metric"])
    out = judge_resume(_good_resume(), JobDescription(job_title="DE"),
                       MasterProfile(), llm=_FakeLLM(verdict))
    assert out.status == "FAIL"
    assert "40%" in out.issues[0]


# --- Correction agent re-applies the fabrication guard ---
def test_correction_sanitizes_output():
    from agents.correction_agent import correct_resume

    profile = MasterProfile(
        personal={"name": "Jane Doe", "email": "jane@example.com"},
        skills=["Python"],
        experience=[{"title": "Engineer", "company": "Acme", "bullets": ["x"]}],
    )
    # Correction LLM tries to sneak in a fake skill + fake company.
    bad = CustomizedResume(
        personal={"name": "HACK"},
        skills=["Python", "Kubernetes"],
        experience=[{"title": "CTO", "company": "FakeCorp", "bullets": ["y"]}],
    )
    out = correct_resume(
        bad, profile,
        RuleValidationResult(status="FAIL", errors=["x"]),
        LLMJudgeResult(status="FAIL", issues=["y"]),
        confirmed_skills=[], llm=_FakeLLM(bad),
    )
    assert out.personal.name == "Jane Doe"       # fact restored from profile
    assert "Kubernetes" not in out.skills         # fabricated skill removed
    assert {e.company for e in out.experience} == {"Acme"}  # fake company dropped


# --- Retry loop: bounded, no infinite loop ---
def test_loop_stops_at_max_attempts(tmp_path, monkeypatch):
    """Always-failing validation must stop at max_retries+1 attempts."""
    import graph.graph as g
    from config.settings import settings

    monkeypatch.setattr(g, "customize_resume",
                        lambda *a, **k: _good_resume())
    monkeypatch.setattr(g, "correct_resume",
                        lambda *a, **k: _good_resume())
    monkeypatch.setattr(g, "format_resume",
                        lambda *a, **k: {"pdf_path": None, "docx_path": None,
                                         "page_count": 1})
    # Rule passes but judge always fails -> loop should exhaust attempts.
    monkeypatch.setattr(g, "validate_ats",
                        lambda *a, **k: RuleValidationResult(status="PASS"))
    monkeypatch.setattr(g, "judge_resume",
                        lambda *a, **k: LLMJudgeResult(status="FAIL",
                                                       issues=["always bad"]))

    result = g.generate_and_validate(
        MasterProfile(), JobDescription(), None, None, [], tmp_path, "x"
    )
    assert result["status"] == "PASS_WITH_WARNINGS"
    assert len(result["attempts"]) == settings.max_retries + 1  # e.g. 3


def test_loop_passes_first_try(tmp_path, monkeypatch):
    import graph.graph as g

    monkeypatch.setattr(g, "customize_resume", lambda *a, **k: _good_resume())
    monkeypatch.setattr(g, "format_resume",
                        lambda *a, **k: {"pdf_path": None, "docx_path": None,
                                         "page_count": 2})
    monkeypatch.setattr(g, "validate_ats",
                        lambda *a, **k: RuleValidationResult(status="PASS"))
    monkeypatch.setattr(g, "judge_resume",
                        lambda *a, **k: LLMJudgeResult(status="PASS"))

    called = {"n": 0}

    def _should_not_run(*a, **k):
        called["n"] += 1
        return _good_resume()

    monkeypatch.setattr(g, "correct_resume", _should_not_run)

    result = g.generate_and_validate(
        MasterProfile(), JobDescription(), None, None, [], tmp_path, "x"
    )
    assert result["status"] == "PASS"
    assert len(result["attempts"]) == 1
    assert called["n"] == 0  # no correction needed
