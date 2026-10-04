"""PDF rendering (ReportLab) + page counting (PyMuPDF).

Renders a CustomizedResume into a professional, strictly black-and-white,
ATS-friendly single-column PDF. Python controls all layout; the output template
is identical every run. Driven by config/formatting.yaml.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from config.logging_config import get_logger
from models.resume_models import CustomizedResume

logger = get_logger(__name__)

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"


def _esc(text: str) -> str:
    return escape(text or "")


def _styles(fmt: dict) -> dict[str, ParagraphStyle]:
    font = fmt.get("font", {})
    body = font.get("body_size", 10)
    heading = font.get("heading_size", 12)
    name = font.get("name_size", 16)

    # spacing_scale lets the page-fitter stretch/compress vertical whitespace to
    # snap the resume to a clean 1 or 2 pages. Leading is scaled gently so line
    # spacing never looks distorted.
    s = fmt.get("spacing_scale", 1.0)
    lead_s = 1 + (s - 1) * 0.6

    def gap(x: float) -> float:
        return round(x * s, 1)

    def lead(size: int) -> float:
        return round((size + 2) * lead_s, 1)

    return {
        "name": ParagraphStyle(
            "name", fontName=FONT_BOLD, fontSize=name, leading=name + 2,
            alignment=TA_CENTER, textColor=black, spaceAfter=gap(2),
        ),
        "contact": ParagraphStyle(
            "contact", fontName=FONT, fontSize=body - 1, leading=body,
            alignment=TA_CENTER, textColor=black, spaceAfter=gap(6),
        ),
        "heading": ParagraphStyle(
            "heading", fontName=FONT_BOLD, fontSize=heading, leading=heading + 2,
            alignment=TA_LEFT, textColor=black, spaceBefore=gap(8), spaceAfter=gap(2),
        ),
        "entry_title": ParagraphStyle(
            "entry_title", fontName=FONT_BOLD, fontSize=body, leading=lead(body),
            alignment=TA_LEFT, textColor=black, spaceBefore=gap(4),
        ),
        "entry_meta": ParagraphStyle(
            "entry_meta", fontName=FONT_ITALIC, fontSize=body - 1, leading=body,
            alignment=TA_LEFT, textColor=black, spaceAfter=gap(1),
        ),
        "body": ParagraphStyle(
            "body", fontName=FONT, fontSize=body, leading=lead(body),
            alignment=TA_LEFT, textColor=black,
        ),
        "summary": ParagraphStyle(
            "summary", fontName=FONT, fontSize=body, leading=lead(body),
            alignment=TA_JUSTIFY, textColor=black,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName=FONT, fontSize=body, leading=lead(body),
            alignment=TA_LEFT, textColor=black, spaceAfter=gap(1),
        ),
    }


def _section_heading(title: str, styles: dict) -> list:
    return [
        Paragraph(_esc(title.upper()), styles["heading"]),
        HRFlowable(width="100%", thickness=0.6, color=black,
                   spaceBefore=1, spaceAfter=4),
    ]


def _bullets(items: list[str], styles: dict) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(_esc(b), styles["bullet"]), leftIndent=10)
         for b in items if b],
        bulletType="bullet", bulletChar="•", leftIndent=12, bulletFontSize=8,
    )


def _contact_line(p) -> str:
    parts = [p.email, p.phone, p.location, p.linkedin, p.github, p.portfolio]
    return "  |  ".join(_esc(x) for x in parts if x)


def _build_story(resume: CustomizedResume, fmt: dict) -> list:
    styles = _styles(fmt)
    story: list = []

    # Header
    if resume.personal.name:
        story.append(Paragraph(_esc(resume.personal.name), styles["name"]))
    contact = _contact_line(resume.personal)
    if contact:
        story.append(Paragraph(contact, styles["contact"]))

    order = fmt.get("section_order", [
        "summary", "skills", "experience", "projects", "education",
        "certifications",
    ])
    # Always append optional enrichment sections after the configured order.
    for extra in ("achievements", "languages", "hobbies"):
        if extra not in order:
            order.append(extra)

    for section in order:
        if section == "summary" and resume.summary:
            story += _section_heading("Summary", styles)
            story.append(Paragraph(_esc(resume.summary), styles["summary"]))

        elif section == "skills" and resume.skills:
            story += _section_heading("Skills", styles)
            story.append(Paragraph(_esc(", ".join(resume.skills)), styles["body"]))

        elif section == "experience" and resume.experience:
            story += _section_heading("Experience", styles)
            for e in resume.experience:
                title = ", ".join(x for x in [e.title, e.company] if x)
                story.append(Paragraph(_esc(title), styles["entry_title"]))
                meta = " | ".join(
                    x for x in [e.location,
                                " - ".join(d for d in [e.start_date, e.end_date] if d)]
                    if x
                )
                if meta:
                    story.append(Paragraph(_esc(meta), styles["entry_meta"]))
                if e.bullets:
                    story.append(_bullets(e.bullets, styles))

        elif section == "projects" and resume.projects:
            story += _section_heading("Projects", styles)
            for pr in resume.projects:
                story.append(Paragraph(_esc(pr.name), styles["entry_title"]))
                sub = []
                if pr.technologies:
                    sub.append("Technologies: " + ", ".join(pr.technologies))
                if pr.link:
                    sub.append(pr.link)
                if sub:
                    story.append(Paragraph(_esc(" | ".join(sub)), styles["entry_meta"]))
                if pr.description:
                    story.append(Paragraph(_esc(pr.description), styles["body"]))
                if pr.bullets:
                    story.append(_bullets(pr.bullets, styles))

        elif section == "education" and resume.education:
            story += _section_heading("Education", styles)
            for ed in resume.education:
                line = ", ".join(x for x in [ed.degree, ed.institution] if x)
                story.append(Paragraph(_esc(line), styles["entry_title"]))
                years = " - ".join(d for d in [ed.start_year, ed.end_year] if d)
                meta = " | ".join(
                    x for x in [years, (f"Grade: {ed.grade}" if ed.grade else "")]
                    if x
                )
                if meta:
                    story.append(Paragraph(_esc(meta), styles["entry_meta"]))

        elif section == "certifications" and resume.certifications:
            story += _section_heading("Certifications", styles)
            story.append(_bullets(resume.certifications, styles))

        elif section == "achievements" and resume.achievements:
            story += _section_heading("Achievements", styles)
            story.append(_bullets(resume.achievements, styles))

        elif section == "languages" and resume.languages:
            story += _section_heading("Languages", styles)
            story.append(Paragraph(_esc(", ".join(resume.languages)), styles["body"]))

        elif section == "hobbies" and resume.hobbies:
            story += _section_heading("Hobbies", styles)
            story.append(Paragraph(_esc(", ".join(resume.hobbies)), styles["body"]))

    return story


def render_pdf(resume: CustomizedResume, out_path: str | Path, fmt: dict) -> Path:
    """Render the resume to a black-and-white, single-column, ATS-friendly PDF."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    margins = fmt.get("margins", {})
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        topMargin=margins.get("top", 0.5) * inch,
        bottomMargin=margins.get("bottom", 0.5) * inch,
        leftMargin=margins.get("left", 0.6) * inch,
        rightMargin=margins.get("right", 0.6) * inch,
        title="Resume",
    )
    doc.build(_build_story(resume, fmt))
    logger.info("PDF rendered: %s", out_path.name)
    return out_path


def count_pdf_pages(path: str | Path) -> int:
    """Return the number of pages in a PDF (PyMuPDF)."""
    import pymupdf

    with pymupdf.open(str(path)) as doc:
        return doc.page_count


def last_page_fill_ratio(path: str | Path) -> float:
    """Fraction (0..1) of the last page's height occupied by content.

    Used by the page-fitter to decide whether to stretch content to fill a clean
    two-page layout. Measures the bottom edge of the lowest text block.
    """
    import pymupdf

    with pymupdf.open(str(path)) as doc:
        page = doc[-1]
        height = page.rect.height or 1.0
        blocks = page.get_text("blocks")
        if not blocks:
            return 0.0
        max_bottom = max(b[3] for b in blocks)  # (x0, y0, x1, y1, text, ...)
        return min(max_bottom / height, 1.0)
