"""Resume Formatter agent (spec §16).

Turns a CustomizedResume (JSON) into rendered artifacts. The LLM never controls
layout; Python does. Renders BOTH a PDF (ReportLab, precise page control) and a
DOCX (python-docx) from the same data, then counts PDF pages.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from config.logging_config import get_logger
from config.settings import settings
from models.resume_models import CustomizedResume
from tools.docx_generator import render_docx
from tools.pdf_utils import count_pdf_pages, last_page_fill_ratio, render_pdf

logger = get_logger(__name__)

# A last page should be at least this full to look "complete".
_FULL_THRESHOLD = 0.88
# Below this, even max stretching can't make a tidy 2-pager -> prefer one page.
_TOO_THIN = 0.55


@lru_cache(maxsize=1)
def load_formatting() -> dict:
    """Load config/formatting.yaml once (cached)."""
    path = Path(settings.formatting_config)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _fit_pdf(resume: CustomizedResume, pdf_path: Path, base_fmt: dict) -> dict:
    """Render the PDF and snap it to a clean 1 or 2 pages via spacing scale.

    Strategy (content stays fixed; only vertical whitespace flexes):
    - 1 page already -> keep.
    - 2 pages but last page underfilled -> increase spacing to fill it, without
      spilling to a 3rd page. If content is too thin to ever fill 2 pages nicely,
      compress to a clean single page instead.
    - More than max_pages -> compress to fit.
    Returns the chosen fmt (with spacing_scale) actually rendered to pdf_path.
    """
    max_pages = settings.max_pages

    def render_measure(scale: float) -> tuple[dict, int, float]:
        fmt = {**base_fmt, "spacing_scale": round(scale, 3)}
        render_pdf(resume, pdf_path, fmt)
        return fmt, count_pdf_pages(pdf_path), last_page_fill_ratio(pdf_path)

    fmt, pages, fill = render_measure(1.0)

    if pages == 1 or (pages == max_pages and fill >= _FULL_THRESHOLD):
        return fmt  # already clean

    if pages <= max_pages:
        # Try to fill the last page by stretching spacing (stay within max_pages).
        best = (fmt, pages, fill, 1.0)
        scale = 1.0
        for _ in range(8):
            scale += 0.2
            f2, p2, fl2 = render_measure(scale)
            if p2 > max_pages:
                break  # overshoot; discard
            best = (f2, p2, fl2, scale)
            if fl2 >= 0.9:
                break
        f_best, _, fill_best, _ = best
        if fill_best >= _TOO_THIN:
            render_pdf(resume, pdf_path, f_best)  # re-render the winning layout
            logger.info("Page-fit: filled to %.0f%% of last page", fill_best * 100)
            return f_best
        # Too thin for a tidy multi-pager -> compress to a single clean page.
        scale = 1.0
        for _ in range(8):
            scale -= 0.12
            if scale < 0.55:
                break
            f3, p3, _ = render_measure(scale)
            if p3 == 1:
                logger.info("Page-fit: compressed to a single page")
                return f3
        render_pdf(resume, pdf_path, f_best)
        return f_best

    # pages > max_pages -> compress toward the limit.
    scale = 1.0
    for _ in range(8):
        scale -= 0.12
        if scale < 0.5:
            break
        f4, p4, _ = render_measure(scale)
        if p4 <= max_pages:
            logger.info("Page-fit: compressed to %d pages", p4)
            return f4
    return fmt  # couldn't fit; validation phase will flag it


def format_resume(
    resume: CustomizedResume,
    out_dir: str | Path,
    basename: str = "resume",
    fmt: dict | None = None,
    fit_pages: bool = True,
) -> dict:
    """Render PDF + DOCX and return their paths and the PDF page count.

    When fit_pages is True, the PDF is snapped to a clean 1 or 2 pages.
    """
    base_fmt = fmt or load_formatting()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / f"{basename}.pdf"
    docx_path = out_dir / f"{basename}.docx"

    chosen_fmt = _fit_pdf(resume, pdf_path, base_fmt) if fit_pages else base_fmt
    if not fit_pages:
        render_pdf(resume, pdf_path, chosen_fmt)
    render_docx(resume, docx_path, chosen_fmt)
    page_count = count_pdf_pages(pdf_path)

    logger.info("Resume formatted (pages=%d)", page_count)
    return {
        "pdf_path": str(pdf_path),
        "docx_path": str(docx_path),
        "page_count": page_count,
    }
