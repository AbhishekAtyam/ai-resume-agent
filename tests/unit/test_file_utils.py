"""Unit tests for tools/file_utils.py (safety + persistence)."""

from __future__ import annotations

import pytest

from models.resume_models import MasterProfile


@pytest.fixture
def storage_tmp(tmp_path, monkeypatch):
    """Point storage at a temp dir so tests never touch real user data."""
    from config.settings import settings

    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    return tmp_path


def test_sanitize_filename_strips_paths():
    from tools.file_utils import sanitize_filename

    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("my resume (final).pdf") == "my_resume_final_.pdf"
    assert sanitize_filename("") == "file"


def test_validate_upload_rejects_bad_types():
    from tools.file_utils import validate_upload

    assert validate_upload("resume.pdf", 500) == ".pdf"
    assert validate_upload("resume.docx", 500) == ".docx"
    with pytest.raises(ValueError):
        validate_upload("resume.exe", 500)
    with pytest.raises(ValueError):
        validate_upload("resume.pdf", 0)


def test_path_traversal_blocked(storage_tmp):
    from tools.file_utils import user_dir

    # A traversal attempt in the user_id is sanitized, not escaped.
    path = user_dir("../../evil")
    assert "evil" in path.name
    assert str(storage_tmp) in str(path.resolve())


def test_save_and_load_profile_roundtrip(storage_tmp):
    from tools.file_utils import list_profiles, load_profile, save_profile

    profile = MasterProfile(
        summary="Data engineer",
        skills=["Python", "SQL"],
    )
    save_profile("user_001", profile)

    assert "user_001" in list_profiles()
    loaded = load_profile("user_001")
    assert loaded is not None
    assert loaded.summary == "Data engineer"
    assert loaded.skills == ["Python", "SQL"]


def test_load_missing_profile_returns_none(storage_tmp):
    from tools.file_utils import load_profile

    assert load_profile("nobody") is None


def test_save_uploaded_resume_validates(storage_tmp):
    from tools.file_utils import save_uploaded_resume

    path = save_uploaded_resume("user_001", "master.pdf", b"%PDF-1.4 fake")
    assert path.exists()
    assert path.name == "master_resume.pdf"

    with pytest.raises(ValueError):
        save_uploaded_resume("user_001", "bad.txt", b"hello")


def test_delete_profile(storage_tmp):
    from tools.file_utils import (
        delete_profile,
        list_profiles,
        save_profile,
        save_uploaded_resume,
    )

    save_profile("user_x", MasterProfile(summary="x"))
    save_uploaded_resume("user_x", "r.pdf", b"%PDF-1.4 data")
    assert "user_x" in list_profiles()

    assert delete_profile("user_x") is True
    assert "user_x" not in list_profiles()
    # Deleting a non-existent profile is a safe no-op.
    assert delete_profile("nobody") is False


def test_delete_profile_path_traversal_safe(storage_tmp):
    """A malicious user_id can't escape the storage root."""
    from tools.file_utils import delete_profile

    # Sanitized to a harmless name; nothing outside storage is touched.
    assert delete_profile("../../etc") is False


def test_load_prompt():
    from tools.file_utils import load_prompt

    text = load_prompt("profile_parser")
    assert "ROLE" in text
    # Works with and without extension.
    assert load_prompt("profile_parser.txt") == text
