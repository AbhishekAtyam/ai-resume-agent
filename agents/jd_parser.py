"""JD Parser agent (spec §10).

Converts raw JD text into a structured JobDescription using LLM structured output.
"""

from __future__ import annotations

from typing import Any

from config.logging_config import get_logger
from config.settings import settings
from llm.factory import get_llm
from models.jd_models import JobDescription
from tools.file_utils import load_prompt

logger = get_logger(__name__)


def parse_jd(raw_jd: str, llm: Any | None = None) -> JobDescription:
    """Parse raw JD text into a structured JobDescription."""
    text = (raw_jd or "")[: settings.max_jd_chars]
    if len(raw_jd or "") > settings.max_jd_chars:
        logger.info("JD truncated to %d chars for parsing", settings.max_jd_chars)
    logger.info("JD parsing started (%d chars)", len(text))

    model = llm if llm is not None else get_llm()
    structured = model.with_structured_output(JobDescription)

    messages = [
        ("system", load_prompt("jd_parser")),
        ("human", text),
    ]
    result = structured.invoke(messages)

    jd = result if isinstance(result, JobDescription) else JobDescription.model_validate(result)
    logger.info(
        "JD parsing successful (required=%d, preferred=%d, tools=%d)",
        len(jd.required_skills),
        len(jd.preferred_skills),
        len(jd.tools_and_technologies),
    )
    return jd
