"""Playwright fallback for JavaScript-rendered JD pages (spec §9, step 4).

Used only when HTTP+BeautifulSoup extraction is insufficient. Robust against the
two common failure modes:
  - `networkidle` never settling (analytics/polling) -> use `domcontentloaded`
    plus a short content-polling wait instead.
  - JD rendered inside an iframe (Greenhouse/Lever/Workday embeds) -> extract
    text from the main frame AND all child frames.

Degrades gracefully if Playwright or its browser is not installed.
"""

from __future__ import annotations

from config.logging_config import get_logger
from tools.web_scraper import extract_jd_text, is_sufficient_jd

logger = get_logger(__name__)

GOTO_TIMEOUT_MS = 45_000       # hard cap for initial navigation
CONTENT_POLL_MS = 1_500        # wait between content checks
MAX_CONTENT_POLLS = 8          # ~12s of polling for late-loading iframes


def merge_extracted_texts(htmls: list[str]) -> str:
    """Extract+clean text from several HTML docs and merge, de-duplicating lines.

    Used to combine the main page with iframe content (where embedded job
    boards render the JD). Pure function — unit-testable without a browser.
    """
    seen: set[str] = set()
    out: list[str] = []
    for html in htmls:
        if not html:
            continue
        for line in extract_jd_text(html).splitlines():
            if line and line not in seen:
                seen.add(line)
                out.append(line)
    return "\n".join(out)


def _collect_all_frame_html(page) -> list[str]:
    """Return HTML from the main page and every child frame (best-effort)."""
    htmls: list[str] = []
    try:
        htmls.append(page.content())
    except Exception:  # noqa: BLE001
        pass
    for frame in page.frames:
        try:
            if frame is page.main_frame:
                continue
            htmls.append(frame.content())
        except Exception:  # noqa: BLE001 - detached/cross-origin frames
            continue
    return htmls


def scrape_jd_playwright(url: str) -> str | None:
    """Render the page with headless Chromium and extract JD text, or None."""
    from config.settings import settings

    if not settings.enable_playwright:
        logger.info("Playwright disabled (ENABLE_PLAYWRIGHT=false); skipping JS render")
        return None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.info("Playwright not installed; skipping JS-render fallback")
        return None

    text = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                # domcontentloaded resolves reliably; we poll for content after.
                page.goto(url, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")

                # Give a short, bounded chance for network to settle (optional).
                try:
                    page.wait_for_load_state("networkidle", timeout=5_000)
                except Exception:  # noqa: BLE001 - fine if it never idles
                    pass

                # Poll until enough text appears (handles late-loading iframes).
                for _ in range(MAX_CONTENT_POLLS):
                    text = merge_extracted_texts(_collect_all_frame_html(page))
                    if is_sufficient_jd(text):
                        break
                    page.wait_for_timeout(CONTENT_POLL_MS)
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 - render failures fall back to manual
        logger.info("Playwright render failed: %s", type(exc).__name__)
        return None

    if is_sufficient_jd(text):
        logger.info("Playwright extraction succeeded (%d chars)", len(text))
        return text

    logger.info(
        "Playwright extraction insufficient: %d chars (JD may need manual paste)",
        len(text),
    )
    return None
