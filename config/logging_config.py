"""Structured logging setup with PII redaction.

Per the spec (§24) we must never log full resumes, emails, or phone numbers.
`get_logger()` returns a configured logger; `redact()` helps callers scrub
sensitive strings before logging.
"""

from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import PROJECT_ROOT, settings

_CONFIGURED = False

# Persistent log file (rotated). Contains PII-redacted application logs.
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "app.log"

# Patterns for lightweight PII redaction in log messages.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")


def redact(text: str) -> str:
    """Mask emails and phone numbers in a free-text string."""
    if not text:
        return text
    text = _EMAIL_RE.sub("[email-redacted]", text)
    text = _PHONE_RE.sub("[phone-redacted]", text)
    return text


class _RedactingFormatter(logging.Formatter):
    """Formatter that scrubs PII from the log *message* only.

    Redaction is applied to the rendered message (not the timestamp/level
    metadata) so structured fields like the asctime are never mangled.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact(record.getMessage())
        record.args = ()
        return super().format(record)


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    formatter = _RedactingFormatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stream_handler)

    # Persistent rotating file log (5 files x 1MB). Best-effort: never let a
    # logging-setup failure crash the app.
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass

    root.setLevel(settings.log_level.upper())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger with the shared configuration applied."""
    _configure_root()
    return logging.getLogger(name)


def tail_log(lines: int = 40) -> str:
    """Return the last `lines` lines of the persistent log file (for the UI)."""
    if not LOG_FILE.exists():
        return "(no logs yet)"
    try:
        content = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:  # noqa: BLE001
        return f"(could not read log: {exc})"
    return "\n".join(content[-lines:]) if content else "(log is empty)"
