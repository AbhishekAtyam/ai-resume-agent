"""Single source of LLM initialization (spec §32, Rules 9 & 10).

`get_llm()` returns a LangChain chat model based on configuration. Phase 0
wires the Ollama provider; other providers (e.g. OpenAI) can be added here
without touching any agent/node logic.
"""

from __future__ import annotations

from typing import Any

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Auto-selection preference order.
PROVIDER_ORDER = ("ollama", "gemini", "groq")

# Cache the auto-resolved provider for this process (the ollama ping is the only
# slow check; explicit providers bypass the cache).
_resolved_provider: str | None = None


def _provider_ready(provider: str) -> bool:
    """True if the given provider can actually be used right now."""
    if provider == "ollama":
        try:
            import requests

            resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:  # noqa: BLE001 - unreachable server is the expected failure
            return False
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "groq":
        return bool(settings.groq_api_key)
    return False


def resolve_provider(force: bool = False) -> str:
    """Return the provider to use.

    If LLM_PROVIDER is a specific name, use it (no caching). If it is "auto" (the
    default), pick the first available provider in PROVIDER_ORDER and cache it.
    """
    configured = (settings.llm_provider or "auto").lower()
    if configured != "auto":
        return configured

    global _resolved_provider
    if _resolved_provider and not force:
        return _resolved_provider

    for provider in PROVIDER_ORDER:
        if _provider_ready(provider):
            _resolved_provider = provider
            logger.info("Auto-selected LLM provider: %s", provider)
            return provider

    _resolved_provider = "ollama"  # nothing available; use() will raise a clear error
    logger.info("No LLM provider available; defaulting to ollama")
    return _resolved_provider


def active_provider() -> str:
    """The provider currently in effect (for display)."""
    return resolve_provider()


def llm_available() -> bool:
    """Whether the currently-selected provider is actually usable (UI health)."""
    return _provider_ready(resolve_provider())


# Backwards-compatible alias.
def ollama_available() -> bool:
    return llm_available()


def get_llm(temperature: float | None = None, **kwargs: Any):
    """Return a configured LangChain chat model for the active provider.

    Args:
        temperature: Optional override for sampling temperature.
        **kwargs: Extra provider-specific keyword arguments.
    """
    provider = resolve_provider()
    temp = settings.llm_temperature if temperature is None else temperature

    if provider == "ollama":
        # Imported lazily so the dependency is only required when used.
        from langchain_ollama import ChatOllama

        logger.info(
            "Initializing Ollama LLM (model=%s, reasoning=%s)",
            settings.ollama_model,
            settings.llm_reasoning,
        )
        # Only pass optional tuning params when explicitly configured.
        extra: dict[str, Any] = {}
        if settings.llm_num_ctx is not None:
            extra["num_ctx"] = settings.llm_num_ctx
        if settings.llm_num_predict is not None:
            extra["num_predict"] = settings.llm_num_predict

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=temp,
            reasoning=settings.llm_reasoning,
            **extra,
            **kwargs,
        )

    if provider == "gemini":
        # Hosted LLM; free key from Google AI Studio (see DEPLOY.md). Lazy import.
        from langchain_google_genai import ChatGoogleGenerativeAI

        logger.info("Initializing Gemini LLM (model=%s)", settings.gemini_model)
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temp,
            **kwargs,  # Ollama-only params (reasoning/num_ctx) are not passed
        )

    if provider == "groq":
        # Hosted LLM for free cloud deployment (see DEPLOY.md). Lazy import.
        from langchain_groq import ChatGroq

        logger.info("Initializing Groq LLM (model=%s)", settings.groq_model)
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temp,
            **kwargs,  # Ollama-only params (reasoning/num_ctx) are not passed
        )

    # Add other providers here. Keeping the switch centralized means agent code
    # never changes when the provider changes.
    raise ValueError(
        f"Unsupported LLM provider '{provider}'. "
        "Supported: 'ollama', 'gemini', 'groq' (or 'auto')."
    )
