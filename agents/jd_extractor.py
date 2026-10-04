"""JD Extraction agent (spec §9).

Orchestrates the extraction strategy:
  1. HTTP + BeautifulSoup  -> quality check
  2. Playwright fallback   -> quality check
  3. REQUEST_MANUAL_INPUT  (scraping is never mandatory)

Returns a structured JDExtractionResult; the UI/graph decides what to do next.
"""

from __future__ import annotations

from config.logging_config import get_logger
from models.jd_models import JDExtractionResult
from tools.playwright_scraper import scrape_jd_playwright
from tools.web_scraper import scrape_jd

logger = get_logger(__name__)

_MANUAL_MESSAGE = (
    "We could not reliably extract the job description from this page. "
    "Please copy the complete job description and paste it below."
)


def extract_jd(job_url: str) -> JDExtractionResult:
    """Attempt HTTP then Playwright extraction; else request manual input."""
    url = (job_url or "").strip()
    if not url:
        return JDExtractionResult(
            status="ERROR", message="No job URL provided."
        )

    logger.info("JD extraction started")

    # Step 1-3: HTTP + BeautifulSoup
    text = scrape_jd(url)
    if text:
        logger.info("JD extraction successful via HTTP")
        return JDExtractionResult(status="SUCCESS", raw_jd=text, source="http")

    # Step 4-5: Playwright fallback for JS-rendered pages
    logger.info("Falling back to Playwright")
    text = scrape_jd_playwright(url)
    if text:
        logger.info("JD extraction successful via Playwright")
        return JDExtractionResult(status="SUCCESS", raw_jd=text, source="playwright")

    # Both failed — ask the user to paste the JD.
    logger.info("JD extraction failed; requesting manual input")
    return JDExtractionResult(
        status="REQUEST_MANUAL_INPUT", message=_MANUAL_MESSAGE
    )
