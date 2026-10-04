"""HTTP + BeautifulSoup job-description scraping (spec §9, steps 1-3).

Deterministic: fetch a URL, strip boilerplate, extract readable text, and judge
whether enough JD content was found. No LLM here.
"""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from config.logging_config import get_logger

logger = get_logger(__name__)

# Minimum characters for extracted text to be considered a usable JD.
MIN_JD_CHARS = 200
REQUEST_TIMEOUT = 15  # seconds

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Tags whose content is almost never part of a job description.
_BOILERPLATE_TAGS = [
    "script", "style", "noscript", "header", "footer", "nav", "form", "aside",
    "svg", "button",
]


def is_sufficient_jd(text: str) -> bool:
    """Content-quality gate: enough text to be a real JD."""
    return bool(text) and len(text.strip()) >= MIN_JD_CHARS


def extract_jd_text(html: str) -> str:
    """Strip boilerplate from HTML and return cleaned, readable text."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_BOILERPLATE_TAGS):
        tag.decompose()

    # Prefer semantic content containers when present.
    container = soup.find("main") or soup.find("article") or soup.body or soup
    text = container.get_text(separator="\n")

    # Collapse whitespace and drop blank lines.
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def fetch_url(url: str) -> str:
    """Fetch a URL over HTTP and return its HTML (raises on HTTP error)."""
    logger.info("Fetching JD URL over HTTP")
    resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def scrape_jd(url: str) -> str | None:
    """Return extracted JD text if HTTP+BS yields sufficient content, else None.

    Logs the precise failure reason (HTTP status / char count vs threshold) so
    the persistent log explains *where* extraction failed.
    """
    try:
        html = fetch_url(url)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        logger.info(
            "HTTP fetch blocked/failed: status %s (site likely blocks scrapers)",
            status,
        )
        return None
    except requests.Timeout:
        logger.info("HTTP fetch timed out after %ss", REQUEST_TIMEOUT)
        return None
    except Exception as exc:  # noqa: BLE001 - network errors are expected/handled
        logger.info("HTTP fetch failed: %s", type(exc).__name__)
        return None

    text = extract_jd_text(html)
    if is_sufficient_jd(text):
        logger.info("HTTP+BeautifulSoup extraction succeeded (%d chars)", len(text))
        return text

    logger.info(
        "HTTP+BeautifulSoup extraction insufficient: %d chars < %d threshold "
        "(page likely renders the JD via JavaScript)",
        len(text),
        MIN_JD_CHARS,
    )
    return None
