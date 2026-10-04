"""Centralized application settings.

All configuration is read from environment variables (via a local .env file)
with safe defaults. Nothing that belongs in config is hard-coded elsewhere
(see CLAUDE.md working rules).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = the directory that contains this config/ package's parent.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application-wide settings, overridable via environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM configuration (provider-agnostic; see llm/factory.py) ---
    # "auto" picks the first available provider in order: ollama -> gemini -> groq.
    # Set a specific provider name to force it.
    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    ollama_model: str = Field(default="qwen3:8b", alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    # qwen3 and similar "thinking" models emit long reasoning traces that make
    # structured output 40x+ slower. Off by default; set LLM_REASONING=true to enable.
    llm_reasoning: bool = Field(default=False, alias="LLM_REASONING")
    # Optional Ollama tuning (None = use model defaults).
    llm_num_ctx: int | None = Field(default=None, alias="LLM_NUM_CTX")
    llm_num_predict: int | None = Field(default=None, alias="LLM_NUM_PREDICT")
    # Cap the characters sent to the LLM for a single JD (scraped pages can be huge).
    max_jd_chars: int = Field(default=12000, alias="MAX_JD_CHARS")

    # --- Gemini (hosted LLM; free key from Google AI Studio; see DEPLOY.md) ---
    gemini_model: str = Field(default="gemini-3.8-flash", alias="GEMINI_MODEL")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")

    # --- Groq (hosted LLM; free key from console.groq.com; see DEPLOY.md) ---
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    # Playwright is heavy and unavailable on most free hosts. Set ENABLE_PLAYWRIGHT=false
    # on the server to skip JS-render scraping (HTTP + manual paste still work).
    enable_playwright: bool = Field(default=True, alias="ENABLE_PLAYWRIGHT")

    # --- Resume generation constraints ---
    max_pages: int = Field(default=2, alias="MAX_PAGES")
    max_retries: int = Field(default=2, alias="MAX_RETRIES")

    # --- Storage / outputs ---
    storage_dir: Path = Field(default=PROJECT_ROOT / "storage", alias="STORAGE_DIR")
    outputs_dir: Path = Field(default=PROJECT_ROOT / "outputs", alias="OUTPUTS_DIR")
    formatting_config: Path = Field(
        default=PROJECT_ROOT / "config" / "formatting.yaml",
        alias="FORMATTING_CONFIG",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


# Convenience module-level singleton.
settings = get_settings()
