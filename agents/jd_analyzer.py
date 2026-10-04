"""JD Analyzer agent (spec §11).

Determines what matters most for the role, producing a prioritized JDAnalysis.
"""

from __future__ import annotations

from typing import Any

from config.logging_config import get_logger
from llm.factory import get_llm
from models.jd_models import JDAnalysis, JobDescription
from tools.file_utils import load_prompt

logger = get_logger(__name__)


def analyze_jd(jd: JobDescription, llm: Any | None = None) -> JDAnalysis:
    """Analyze a structured JobDescription into a prioritized JDAnalysis."""
    logger.info("JD analysis started (title=%s)", jd.job_title or "unknown")

    model = llm if llm is not None else get_llm()
    structured = model.with_structured_output(JDAnalysis)

    messages = [
        ("system", load_prompt("jd_analyzer")),
        ("human", jd.model_dump_json(indent=2)),
    ]
    result = structured.invoke(messages)

    analysis = (
        result if isinstance(result, JDAnalysis) else JDAnalysis.model_validate(result)
    )
    logger.info(
        "JD analysis completed (critical=%d, important=%d, focus=%d)",
        len(analysis.critical_skills),
        len(analysis.important_skills),
        len(analysis.role_focus),
    )
    return analysis
