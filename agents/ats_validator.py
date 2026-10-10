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


_WEIGHT = {"error": 2, "warning": 1, "info": 1}


def validate_ats(resume: CustomizedResume, fmt_result: dict) -> RuleValidationResult:
    """Run deterministic ATS checks and return per-rule results + an ATS score."""
    page_count = int(fmt_result.get("page_count", 0))
    p = resume.personal
    checks: list[dict] = []

    def add(key, label, passed, severity, ok_detail, bad_detail):
        checks.append({
            "key": key, "label": label, "passed": bool(passed),
            "severity": severity, "detail": ok_detail if passed else bad_detail,
        })

    # --- Contact information ---
    add("name", "Contact name", bool(p.name.strip()), "error",
        "Candidate name present", "Missing candidate name")
    email_ok = bool(p.email.strip()) and bool(_EMAIL_RE.match(p.email.strip()))
    add("email", "Email address", email_ok, "error",
        "Valid email present", "Missing or invalid email address")
    add("phone", "Phone number", bool(p.phone.strip()), "warning",
        "Phone number present", "No phone number")

    # --- Standard sections ---
    add("summary", "Professional summary", bool(resume.summary.strip()), "warning",
        "Summary present", "No professional summary")
    add("skills", "Skills section", bool(resume.skills), "error",
        f"{len(resume.skills)} skills listed", "Skills section is empty")
    add("skills_count", "Enough skills (3+)", len(resume.skills) >= 3, "warning",
        "Healthy number of skills", "Fewer than 3 skills listed")
    add("experience", "Work experience", bool(resume.experience), "error",
        f"{len(resume.experience)} role(s) listed", "Experience section is empty")
    exp_labeled = all((e.title or e.company) for e in resume.experience)
    add("exp_labeled", "Experience entries labelled", exp_labeled, "error",
        "Every role has a title/company", "A role is missing title and company")
    exp_bullets = all(e.bullets for e in resume.experience)
    add("exp_bullets", "Experience has bullet points", exp_bullets, "warning",
        "Every role has bullet points", "A role has no bullet points")
    add("education", "Education section", bool(resume.education), "warning",
        "Education present", "No education section")

    # --- Content quality (experience + project bullets) ---
    all_bullets = [b.strip() for e in resume.experience for b in e.bullets if b.strip()]
    all_bullets += [b.strip() for pr in resume.projects for b in pr.bullets if b.strip()]

    norm_bullets = [re.sub(r"\s+", " ", b.lower()) for b in all_bullets]
    dupes = [b for b, c in Counter(norm_bullets).items() if c > 1]
    add("dupe_bullets", "No duplicate bullet points", not dupes, "warning",
        "No repeated bullets", f"{len(dupes)} duplicated bullet(s) found")

    firsts = [b.split()[0].lower() for b in all_bullets if b.split()]
    top_opener, opener_n = Counter(firsts).most_common(1)[0] if firsts else ("", 0)
    repeated_openers = len(firsts) >= 4 and opener_n >= max(3, round(0.5 * len(firsts)))
    add("varied_openers", "Varied bullet openings", not repeated_openers, "warning",
        "Bullets start with varied action verbs",
        f"Many bullets start with '{top_opener}' — vary the verbs")

    has_numbers = any(re.search(r"\d", b) for b in all_bullets)
    add("quantified", "Quantified achievements", has_numbers or not all_bullets, "warning",
        "Includes measurable results",
        "No quantified results — add numbers/impact where possible")

    dates_ok = (all(e.start_date.strip() and e.end_date.strip()
                    for e in resume.experience) if resume.experience else True)
    add("exp_dates", "Experience has dates", dates_ok, "warning",
        "All roles have start/end dates", "A role is missing start/end dates")

    long_ok = all(len(b.split()) <= 45 for b in all_bullets)
    add("bullet_len", "Concise bullet points", long_ok, "warning",
        "Bullets are concise", "Some bullets exceed ~45 words — tighten them")

    first_person = any(re.search(r"\b(i|me|my|myself)\b", b.lower()) for b in all_bullets)
    add("no_first_person", "Professional voice (no 'I/my')", not first_person, "warning",
        "Third-person professional voice", "Avoid first-person pronouns (I, me, my)")

    if resume.summary.strip():
        sw = len(resume.summary.split())
        add("summary_len", "Summary length", 12 <= sw <= 90, "info",
            "Summary length looks good", f"Summary is {sw} words (aim for ~15–60)")

    # --- Skills quality (atomic, focused, unique, substantiated) ---
    non_atomic = [s for s in resume.skills if len(s.split()) > 6]
    add("skills_atomic", "Skills are concise terms", not non_atomic, "warning",
        "All skills are short, atomic terms",
        f"{len(non_atomic)} skill(s) read like sentences, not skills")

    add("skills_focused", "Focused skills list", len(resume.skills) <= 30, "warning",
        "Skills list is focused",
        f"{len(resume.skills)} skills listed — trim to the most relevant ~20")

    skill_norms = [re.sub(r"[^a-z0-9]+", "", s.lower()) for s in resume.skills]
    has_dupe_skills = len(skill_norms) != len(set(skill_norms))
    add("skills_unique", "No duplicate skills", not has_dupe_skills, "warning",
        "No duplicate skills", "Duplicate skills present — remove repeats")

    if resume.skills:
        body_text = " ".join(
            [resume.summary]
            + [b for e in resume.experience for b in e.bullets]
            + [b for pr in resume.projects for b in pr.bullets]
            + [pr.description for pr in resume.projects]
        ).lower()
        present = sum(1 for s in resume.skills if s.lower() in body_text)
        ratio = present / len(resume.skills)
        add("skills_substantiated", "Skills backed by experience", ratio >= 0.4,
            "warning", f"{round(ratio * 100)}% of skills appear in your experience",
            f"Only {round(ratio * 100)}% of listed skills appear in experience/projects "
            "(looks like keyword stuffing)")

    # --- Page count ---
    if page_count == 0:
        checks.append({"key": "pages", "label": f"Within {settings.max_pages}-page limit",
                       "passed": False, "severity": "warning",
                       "detail": "Page count unavailable"})
    else:
        within = page_count <= settings.max_pages
        add("pages", f"Within {settings.max_pages}-page limit", within, "error",
            f"{page_count} page(s)",
            f"{page_count} pages (limit {settings.max_pages})")

    # --- PDF-derived checks (only when the rendered text is available) ---
    text = _pdf_text(fmt_result.get("pdf_path"))
    if text is not None:
        add("extractable", "PDF text is machine-readable",
            len(text) >= _MIN_EXTRACTABLE_CHARS, "error",
            "Selectable text layer detected",
            "PDF text not extractable (image-only?) — ATS may fail to parse it")
        add("chars", "No malformed characters",
            not any(bad in text for bad in _BAD_CHARS), "warning",
            "Clean character encoding", "Contains malformed characters")

        tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z+#.]{2,}", text)]
        common = {"the", "and", "for", "with", "using", "data", "that", "from", "this"}
        counts = Counter(t for t in tokens if t not in common)
        term, n = counts.most_common(1)[0] if counts else ("", 0)
        add("stuffing", "No keyword stuffing", n <= _STUFFING_THRESHOLD, "warning",
            "No excessive keyword repetition",
            f"'{term}' appears {n} times (possible stuffing)")

    # --- Derive errors/warnings + status + weighted score ---
    errors = [c["detail"] for c in checks if not c["passed"] and c["severity"] == "error"]
    warnings = [c["detail"] for c in checks
                if not c["passed"] and c["severity"] == "warning"]
    status = "FAIL" if errors else "PASS"
    total = sum(_WEIGHT[c["severity"]] for c in checks)
    got = sum(_WEIGHT[c["severity"]] for c in checks if c["passed"])
    score = round(100 * got / total) if total else 100

    logger.info(
        "ATS validation %s (score=%d, errors=%d, warnings=%d, pages=%d)",
        status, score, len(errors), len(warnings), page_count,
    )
    return RuleValidationResult(
        status=status, errors=errors, warnings=warnings, page_count=page_count,
        checks=checks, score=score,
    )
