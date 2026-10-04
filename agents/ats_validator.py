"""Deterministic ATS validator (spec §18).

Pure Python rule checks (no LLM). Verifies structural/ATS-oriented properties of
the generated resume and its rendered PDF. Returns a RuleValidationResult with
hard errors (FAIL) and soft warnings.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from config.logging_config import get_logger
from config.settings import settings
from models.resume_models import CustomizedResume
from models.validation_models import RuleValidationResult

logger = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
# Characters that often indicate encoding/rendering problems in ATS parsers.
_BAD_CHARS = ("�", "\x00")
# Low threshold: this only detects image-only/unparseable PDFs, not short content.
_MIN_EXTRACTABLE_CHARS = 50
_STUFFING_THRESHOLD = 12  # a single term repeated more than this => likely stuffing


def _pdf_text(pdf_path: str | None) -> str | None:
    """Extract text from the rendered PDF to confirm ATS extractability."""
    if not pdf_path or not Path(pdf_path).exists():
        return None
    try:
        from tools.resume_parser import extract_text_from_pdf

        return extract_text_from_pdf(pdf_path)
    except Exception as exc:  # noqa: BLE001
        logger.info("Could not extract text from generated PDF: %s", exc)
        return None


def validate_ats(resume: CustomizedResume, fmt_result: dict) -> RuleValidationResult:
    """Run deterministic ATS checks against the resume + its rendered PDF."""
    errors: list[str] = []
    warnings: list[str] = []
    page_count = int(fmt_result.get("page_count", 0))
    p = resume.personal

    # --- Contact information ---
    if not p.name.strip():
        errors.append("Missing candidate name.")
    if not p.email.strip():
        errors.append("Missing email address.")
    elif not _EMAIL_RE.match(p.email.strip()):
        errors.append(f"Email address looks invalid: {p.email}")
    if not p.phone.strip():
        warnings.append("Missing phone number.")

    # --- Standard sections ---
    if not resume.summary.strip():
        warnings.append("Missing professional summary.")
    if not resume.skills:
        errors.append("Skills section is empty.")
    elif len(resume.skills) < 3:
        warnings.append("Very few skills listed (fewer than 3).")
    if not resume.experience:
        errors.append("Experience section is empty.")
    if not resume.education:
        warnings.append("Education section is empty.")

    # --- Empty entries (deterministic structural hygiene) ---
    for i, e in enumerate(resume.experience, 1):
        if not (e.title or e.company):
            errors.append(f"Experience entry #{i} has no title or company.")
        if not e.bullets:
            warnings.append(
                f"Experience '{e.title or e.company or i}' has no bullet points."
            )

    # --- Page count ---
    if page_count > settings.max_pages:
        errors.append(
            f"Resume is {page_count} pages (limit {settings.max_pages})."
        )
    elif page_count == 0:
        warnings.append("Could not determine page count.")

    # --- Text extractability (ATS must be able to read the PDF) ---
    text = _pdf_text(fmt_result.get("pdf_path"))
    if text is not None:
        if len(text) < _MIN_EXTRACTABLE_CHARS:
            errors.append(
                "Rendered PDF text is not sufficiently extractable "
                f"({len(text)} chars) — ATS may fail to parse it."
            )
        if any(bad in text for bad in _BAD_CHARS):
            warnings.append("Rendered PDF contains malformed characters.")

        # --- Keyword stuffing ---
        tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z+#.]{2,}", text)]
        common = {
            "the", "and", "for", "with", "using", "data", "that", "from", "this",
        }
        counts = Counter(t for t in tokens if t not in common)
        if counts:
            term, n = counts.most_common(1)[0]
            if n > _STUFFING_THRESHOLD:
                warnings.append(
                    f"Possible keyword stuffing: '{term}' appears {n} times."
                )

    status = "FAIL" if errors else "PASS"
    logger.info(
        "ATS validation %s (errors=%d, warnings=%d, pages=%d)",
        status, len(errors), len(warnings), page_count,
    )
    return RuleValidationResult(
        status=status, errors=errors, warnings=warnings, page_count=page_count
    )
