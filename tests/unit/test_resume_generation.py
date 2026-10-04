"""Unit tests for resume customization (fabrication guard) + rendering."""

from __future__ import annotations

from models.jd_models import JobDescription
from models.resume_models import CustomizedResume, MasterProfile


def _profile() -> MasterProfile:
    return MasterProfile(
        personal={"name": "Jane Doe", "email": "jane@example.com", "location": "Hyderabad"},
        summary="Engineer.",
        skills=["Python", "SQL"],
        experience=[
            {"title": "Data Engineer", "company": "Acme", "start_date": "2021",
             "end_date": "Present", "bullets": ["Built pipelines"]}
        ],
        projects=[{"name": "Lakehouse", "technologies": ["Spark"], "bullets": ["x"]}],
        education=[{"degree": "B.Tech", "institution": "VNR", "end_year": "2020",
                    "grade": "9.11"}],
        certifications=["AWS DA"],
    )


class _FakeLLM:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        parent = self

        class _S:
            def invoke(self, messages):
                return parent._result

        return _S()


def test_sanitizer_blocks_fabricated_skills_and_roles():
    from agents.resume_customizer import customize_resume

    # LLM tries to add a fake skill, a fake company, and a fake degree.
    fabricated = CustomizedResume(
        personal={"name": "HACKED", "email": "evil@x.com"},
        summary="Tailored summary.",
        skills=["Python", "SQL", "Snowflake", "Kubernetes"],  # last two not allowed
        experience=[
            {"title": "Data Engineer", "company": "Acme", "bullets": ["Rephrased bullet"]},
            {"title": "CTO", "company": "FakeCorp", "bullets": ["Invented role"]},
        ],
        projects=[{"name": "Lakehouse", "bullets": ["new bullet"]},
                  {"name": "Invented Project", "bullets": ["fake"]}],
        education=[{"degree": "PhD", "institution": "Fake Univ"}],
        certifications=["Made up cert"],
    )
    profile = _profile()
    jd = JobDescription(job_title="Data Engineer", required_skills=["Python", "Snowflake"])

    out = customize_resume(
        profile, jd, None, None,
        confirmed_skills=["Snowflake"],  # user confirmed Snowflake -> allowed
        llm=_FakeLLM(fabricated),
    )

    # Personal + education + certs come from the profile, not the LLM.
    assert out.personal.name == "Jane Doe"
    assert out.personal.email == "jane@example.com"
    assert out.education[0].degree == "B.Tech"
    assert out.certifications == ["AWS DA"]

    # Skills: Snowflake allowed (confirmed); Kubernetes dropped (not allowed).
    assert "Snowflake" in out.skills
    assert "Kubernetes" not in out.skills

    # Experience: real Acme role kept with rephrased bullet; fake CTO dropped.
    companies = {e.company for e in out.experience}
    assert companies == {"Acme"}
    assert out.experience[0].bullets == ["Rephrased bullet"]
    assert out.experience[0].start_date == "2021"  # factual date preserved

    # Projects: real one kept; invented one dropped.
    names = {p.name for p in out.projects}
    assert names == {"Lakehouse"}


def test_customize_does_not_mutate_master_profile():
    """Confirmed/runtime skills must NOT leak into the master profile object."""
    from agents.resume_customizer import customize_resume

    profile = _profile()
    original_skills = list(profile.skills)
    original_dump = profile.model_dump()

    out = customize_resume(
        profile,
        JobDescription(job_title="Data Engineer", required_skills=["Snowflake"]),
        None, None,
        confirmed_skills=["Snowflake", "Spark"],
        llm=_FakeLLM(CustomizedResume(
            personal={"name": "Jane Doe"},
            skills=["Python", "SQL", "Snowflake", "Spark"],
            experience=[{"title": "Data Engineer", "company": "Acme",
                         "bullets": ["b"]}],
        )),
    )

    # The generated resume may include confirmed skills...
    assert "Snowflake" in out.skills
    # ...but the master profile must be completely unchanged.
    assert profile.skills == original_skills
    assert "Snowflake" not in profile.skills
    assert profile.model_dump() == original_dump


def test_format_resume_renders_pdf_and_docx(tmp_path):
    from agents.resume_formatter import format_resume

    resume = CustomizedResume(
        personal={"name": "Jane Doe", "email": "jane@example.com",
                  "location": "Hyderabad", "linkedin": "linkedin.com/in/jane"},
        summary="Data engineer with experience building ETL pipelines.",
        skills=["Python", "SQL", "Spark", "Snowflake"],
        experience=[
            {"title": "Data Engineer", "company": "Acme", "location": "Remote",
             "start_date": "2021", "end_date": "Present",
             "bullets": ["Built batch and streaming pipelines", "Optimized SQL models"]}
        ],
        projects=[{"name": "Lakehouse", "technologies": ["Spark", "Python"],
                   "bullets": ["Built a streaming lakehouse"]}],
        education=[{"degree": "B.Tech IT", "institution": "VNR VJIET",
                    "end_year": "2020", "grade": "9.11"}],
        certifications=["AWS Data Analytics"],
        achievements=["Winner, SIH 2021"],
        languages=["English", "Telugu"],
    )

    result = format_resume(resume, tmp_path, basename="test_resume")
    pdf = tmp_path / "test_resume.pdf"
    docx = tmp_path / "test_resume.docx"

    assert pdf.exists() and pdf.stat().st_size > 0
    assert docx.exists() and docx.stat().st_size > 0
    assert result["page_count"] >= 1
    assert result["pdf_path"].endswith("test_resume.pdf")


def test_format_resume_handles_minimal_resume(tmp_path):
    from agents.resume_formatter import format_resume

    minimal = CustomizedResume(personal={"name": "Only Name"})
    result = format_resume(minimal, tmp_path, basename="minimal")
    assert (tmp_path / "minimal.pdf").exists()
    assert result["page_count"] >= 1


def test_page_fit_keeps_within_limit_and_measures_fill(tmp_path):
    """A long resume is snapped to <= max_pages and fill ratio is measurable."""
    from config.settings import settings
    from tools.pdf_utils import last_page_fill_ratio

    from agents.resume_formatter import format_resume

    long_exp = [
        {"title": f"Engineer {i}", "company": f"Company {i}", "start_date": "2020",
         "end_date": "2022", "bullets": [f"Did important work item {j}" for j in range(5)]}
        for i in range(6)
    ]
    big = CustomizedResume(
        personal={"name": "Jane Doe", "email": "jane@example.com"},
        summary="A detailed summary. " * 20,
        skills=["Python", "SQL", "Spark"] * 5,
        experience=long_exp,
    )
    result = format_resume(big, tmp_path, basename="big")
    assert result["page_count"] <= settings.max_pages
    # Fill ratio is a valid fraction.
    ratio = last_page_fill_ratio(result["pdf_path"])
    assert 0.0 <= ratio <= 1.0


def test_fill_ratio_single_short_page(tmp_path):
    from tools.pdf_utils import last_page_fill_ratio, render_pdf
    from agents.resume_formatter import load_formatting

    short = CustomizedResume(personal={"name": "Tiny"}, summary="One line.")
    pdf = tmp_path / "short.pdf"
    render_pdf(short, pdf, load_formatting())
    # A nearly-empty page should report a low fill ratio.
    assert last_page_fill_ratio(pdf) < 0.4
