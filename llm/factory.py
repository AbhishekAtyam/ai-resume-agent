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


def ollama_available() -> bool:
    """Best-effort check that the local Ollama server is reachable.

    Returns True for non-ollama providers (nothing to check here).
    """
    if settings.llm_provider.lower() != "ollama":
        return True
    try:
        import requests

        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=2)
        return resp.status_code == 200
    except Exception:  # noqa: BLE001 - unreachable server is the expected failure
        return False


def get_llm(temperature: float | None = None, **kwargs: Any):
    """Return a configured LangChain chat model for the active provider.

    Args:
        temperature: Optional override for sampling temperature.
        **kwargs: Extra provider-specific keyword arguments.
    """
    provider = settings.llm_provider.lower()
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

    # TODO (future): add "openai" and other providers here. Keeping the switch
    # centralized means agent code never changes when the provider changes.
    raise ValueError(
        f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. "
        "Supported providers: 'ollama'."
    )
