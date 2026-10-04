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

    assert settings.llm_provider == "auto"
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
    monkeypatch.setattr(factory.settings, "llm_provider", "ollama")

    llm = factory.get_llm()
    assert isinstance(llm, FakeChatOllama)
    assert captured["model"] == "qwen3:8b"


def test_llm_factory_builds_gemini(monkeypatch):
    """get_llm() builds a ChatGoogleGenerativeAI when provider=gemini."""
    import sys
    import types

    import llm.factory as factory

    captured = {}

    class FakeGemini:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_mod = types.ModuleType("langchain_google_genai")
    fake_mod.ChatGoogleGenerativeAI = FakeGemini
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_mod)
    monkeypatch.setattr(factory.settings, "llm_provider", "gemini")
    monkeypatch.setattr(factory.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(factory.settings, "gemini_model", "gemini-2.0-flash")

    llm = factory.get_llm()
    assert isinstance(llm, FakeGemini)
    assert captured["model"] == "gemini-2.0-flash"
    assert "reasoning" not in captured


def test_resolve_provider_prefers_available(monkeypatch):
    """auto picks ollama -> gemini -> groq by availability."""
    import llm.factory as factory

    monkeypatch.setattr(factory.settings, "llm_provider", "auto")
    monkeypatch.setattr(factory, "_resolved_provider", None)
    # Ollama down, gemini has a key, groq has a key -> gemini wins.
    monkeypatch.setattr(factory, "_provider_ready",
                        lambda p: {"ollama": False, "gemini": True, "groq": True}[p])
    assert factory.resolve_provider(force=True) == "gemini"

    monkeypatch.setattr(factory, "_resolved_provider", None)
    # Ollama up -> ollama wins regardless of keys.
    monkeypatch.setattr(factory, "_provider_ready",
                        lambda p: {"ollama": True, "gemini": True, "groq": True}[p])
    assert factory.resolve_provider(force=True) == "ollama"


def test_llm_factory_builds_groq(monkeypatch):
    """get_llm() builds a ChatGroq when provider=groq (no network)."""
    import sys
    import types

    import llm.factory as factory

    captured = {}

    class FakeChatGroq:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_mod = types.ModuleType("langchain_groq")
    fake_mod.ChatGroq = FakeChatGroq
    monkeypatch.setitem(sys.modules, "langchain_groq", fake_mod)
    monkeypatch.setattr(factory.settings, "llm_provider", "groq")
    monkeypatch.setattr(factory.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(factory.settings, "groq_model", "llama-3.3-70b-versatile")

    llm = factory.get_llm()
    assert isinstance(llm, FakeChatGroq)
    assert captured["model"] == "llama-3.3-70b-versatile"
    # Ollama-only params must NOT be forwarded to Groq.
    assert "reasoning" not in captured and "num_ctx" not in captured


def test_llm_available_is_provider_aware(monkeypatch):
    import llm.factory as factory

    monkeypatch.setattr(factory.settings, "llm_provider", "groq")
    monkeypatch.setattr(factory.settings, "groq_api_key", "")
    assert factory.llm_available() is False
    monkeypatch.setattr(factory.settings, "groq_api_key", "key")
    assert factory.llm_available() is True


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
