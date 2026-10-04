"""Phase 0 smoke tests (spec §34).

Deterministic, no live LLM calls. Verifies the skeleton is wired correctly:
config loads, state/models import, the LLM factory builds for ollama, and the
formatting config parses.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_settings_load():
    from config.settings import settings

    assert settings.llm_provider == "ollama"
    assert settings.max_pages == 2
    assert settings.max_retries == 2


def test_state_imports():
    from graph.state import ResumeState

    # TypedDict instances are plain dicts at runtime.
    state: ResumeState = {"status": "init", "retry_count": 0}
    assert state["status"] == "init"


def test_models_import_and_defaults():
    from models.jd_models import JDAnalysis, JobDescription
    from models.resume_models import CustomizedResume, GapAnalysis, MasterProfile
    from models.validation_models import LLMJudgeResult, RuleValidationResult

    assert JobDescription().required_skills == []
    assert JDAnalysis().role_focus == []
    assert MasterProfile().skills == []
    assert GapAnalysis().matched_skills == []
    assert CustomizedResume().summary == ""
    assert RuleValidationResult().status == "PASS"
    assert LLMJudgeResult().status == "PASS"


def test_llm_factory_builds(monkeypatch):
    """get_llm() returns a ChatOllama without making a network call."""
    import llm.factory as factory

    captured = {}

    class FakeChatOllama:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    # Patch the lazily-imported symbol by injecting a fake module.
    import sys
    import types

    fake_mod = types.ModuleType("langchain_ollama")
    fake_mod.ChatOllama = FakeChatOllama
    monkeypatch.setitem(sys.modules, "langchain_ollama", fake_mod)

    llm = factory.get_llm()
    assert isinstance(llm, FakeChatOllama)
    assert captured["model"] == "qwen3:8b"


def test_llm_factory_rejects_unknown_provider(monkeypatch):
    import llm.factory as factory

    monkeypatch.setattr(factory.settings, "llm_provider", "nope")
    try:
        factory.get_llm()
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_formatting_yaml_parses():
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "formatting.yaml"
    data = yaml.safe_load(cfg_path.read_text())
    assert data["page_limit"] == 2
    assert "font" in data and "margins" in data


def test_redaction():
    from config.logging_config import redact

    masked = redact("Contact me at jane@example.com or +1 415 555 2671")
    assert "jane@example.com" not in masked
    assert "555" not in masked
