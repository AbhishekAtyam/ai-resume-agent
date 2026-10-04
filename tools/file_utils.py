"""Safe local storage + file helpers (spec §25, §33).

Responsibilities:
- Sanitize filenames and prevent path traversal.
- Restrict uploads to allowed resume types.
- Persist / load structured profiles and uploaded master resumes.
- Load prompt templates from the prompts/ directory.

All user data lives under `settings.storage_dir`. PII is never logged.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from config.logging_config import get_logger
from config.settings import PROJECT_ROOT, settings
from models.resume_models import MasterProfile

logger = get_logger(__name__)

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".docx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

_SAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------------- #
# Filename / path safety
# --------------------------------------------------------------------------- #
def sanitize_filename(name: str) -> str:
    """Return a safe basename: strip directories, collapse unsafe chars."""
    # Drop any path components an attacker might include.
    base = Path(name).name
    base = _SAFE_CHARS_RE.sub("_", base).strip("._") or "file"
    return base


def _resolve_within(base: Path, *parts: str) -> Path:
    """Join parts under `base` and ensure the result stays inside `base`.

    Guards against path-traversal (e.g. '../../etc/passwd').
    """
    base = base.resolve()
    candidate = base.joinpath(*parts).resolve()
    if base != candidate and base not in candidate.parents:
        raise ValueError(f"Unsafe path outside storage root: {candidate}")
    return candidate


def validate_upload(filename: str, size_bytes: int) -> str:
    """Validate an uploaded file's type and size; return its extension.

    Raises ValueError on invalid type or oversize file.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_RESUME_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed: "
            f"{', '.join(sorted(ALLOWED_RESUME_EXTENSIONS))}."
        )
    if size_bytes <= 0:
        raise ValueError("Uploaded file is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File too large ({size_bytes} bytes). Max {MAX_UPLOAD_BYTES} bytes."
        )
    return ext


# --------------------------------------------------------------------------- #
# Storage locations
# --------------------------------------------------------------------------- #
def user_dir(user_id: str) -> Path:
    """Return (and create) the storage directory for a user."""
    safe_id = sanitize_filename(user_id)
    path = _resolve_within(settings.storage_dir / "users", safe_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_path(user_id: str) -> Path:
    return user_dir(user_id) / "profile.json"


def list_profiles() -> list[str]:
    """Return user_ids that have a saved profile."""
    users_root = settings.storage_dir / "users"
    if not users_root.exists():
        return []
    return sorted(
        p.name for p in users_root.iterdir()
        if p.is_dir() and (p / "profile.json").exists()
    )


def delete_profile(user_id: str) -> bool:
    """Delete a user's stored profile folder (profile.json + master resume).

    Path is resolved under the storage root with the traversal guard. Returns
    True if something was removed.
    """
    safe_id = sanitize_filename(user_id)
    path = _resolve_within(settings.storage_dir / "users", safe_id)
    if path.exists() and path.is_dir():
        shutil.rmtree(path)
        logger.info("Deleted stored profile for user=%s", user_id)
        return True
    return False


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def save_uploaded_resume(user_id: str, filename: str, data: bytes) -> Path:
    """Persist the raw uploaded master resume. Returns the saved path."""
    ext = validate_upload(filename, len(data))
    dest = user_dir(user_id) / f"master_resume{ext}"
    dest.write_bytes(data)
    logger.info("Saved master resume for user=%s (%d bytes)", user_id, len(data))
    return dest


def save_profile(user_id: str, profile: MasterProfile) -> Path:
    """Persist a structured profile as JSON. Returns the saved path."""
    dest = profile_path(user_id)
    dest.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Saved structured profile for user=%s", user_id)
    return dest


def load_profile(user_id: str) -> MasterProfile | None:
    """Load a structured profile if present, else None."""
    path = profile_path(user_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    logger.info("Loaded structured profile for user=%s", user_id)
    return MasterProfile.model_validate(data)


# --------------------------------------------------------------------------- #
# Prompt loading
# --------------------------------------------------------------------------- #
def load_prompt(name: str) -> str:
    """Load a prompt template by name from the prompts/ directory.

    `name` may be given with or without the .txt extension.
    """
    filename = name if name.endswith(".txt") else f"{name}.txt"
    path = _resolve_within(PROJECT_ROOT / "prompts", filename)
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
