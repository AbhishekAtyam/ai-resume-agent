"""Unit tests for JD extraction tools + input router (no network / no LLM)."""

from __future__ import annotations

SAMPLE_HTML = """
<html><head><title>Job</title><style>.x{}</style></head>
<body>
  <nav>Home About Careers</nav>
  <header>Company logo</header>
  <main>
    <h1>Data Engineer</h1>
    <p>We are hiring a Data Engineer to build ETL pipelines.</p>
    <ul><li>Python</li><li>SQL</li><li>Spark</li></ul>
    <p>Requirements: 3+ years of experience with data pipelines, Airflow, and dbt.
    You will design, build, and maintain scalable data infrastructure on the cloud.</p>
  </main>
  <footer>© 2026 Example Corp</footer>
  <script>console.log('tracking')</script>
</body></html>
"""


def test_extract_jd_text_strips_boilerplate():
    from tools.web_scraper import extract_jd_text

    text = extract_jd_text(SAMPLE_HTML)
    assert "Data Engineer" in text
    assert "ETL pipelines" in text
    # Boilerplate removed.
    assert "tracking" not in text
    assert "Home About Careers" not in text
    assert "© 2026" not in text


def test_is_sufficient_jd():
    from tools.web_scraper import is_sufficient_jd

    assert is_sufficient_jd("x" * 250) is True
    assert is_sufficient_jd("too short") is False
    assert is_sufficient_jd("") is False


def test_scrape_jd_returns_text_when_sufficient(monkeypatch):
    import tools.web_scraper as ws

    monkeypatch.setattr(ws, "fetch_url", lambda url: SAMPLE_HTML)
    text = ws.scrape_jd("https://example.com/job")
    assert text is not None
    assert "Data Engineer" in text


def test_scrape_jd_returns_none_on_fetch_error(monkeypatch):
    import tools.web_scraper as ws

    def boom(url):
        raise RuntimeError("blocked")

    monkeypatch.setattr(ws, "fetch_url", boom)
    assert ws.scrape_jd("https://example.com/job") is None


def test_scrape_jd_returns_none_when_insufficient(monkeypatch):
    import tools.web_scraper as ws

    monkeypatch.setattr(ws, "fetch_url", lambda url: "<html><body>Hi</body></html>")
    assert ws.scrape_jd("https://example.com/job") is None


# --- Playwright text merging (iframe support), pure function ---
def test_merge_extracted_texts_dedupes_and_combines():
    from tools.playwright_scraper import merge_extracted_texts

    main_html = "<html><body><main><p>Shared line</p><p>Main only</p></main></body></html>"
    iframe_html = (
        "<html><body><main><p>Shared line</p>"
        "<p>Job: build ETL pipelines in Python and SQL.</p></main></body></html>"
    )
    merged = merge_extracted_texts([main_html, iframe_html])
    assert "Main only" in merged
    assert "build ETL pipelines" in merged
    # De-duplicated across frames.
    assert merged.count("Shared line") == 1


def test_merge_extracted_texts_handles_empty():
    from tools.playwright_scraper import merge_extracted_texts

    assert merge_extracted_texts([]) == ""
    assert merge_extracted_texts(["", None]) == ""


# --- Input router ---
def test_route_input():
    from graph.routers import route_input

    assert route_input(None, "Some pasted JD text") == "parse"
    assert route_input("https://x.com/job", None) == "extract"
    assert route_input("https://x.com/job", "pasted wins") == "parse"
    assert route_input(None, None) == "error"
    assert route_input("", "   ") == "error"


# --- Extractor orchestration (HTTP -> Playwright -> manual) ---
def test_extract_jd_success_http(monkeypatch):
    import agents.jd_extractor as ex

    monkeypatch.setattr(ex, "scrape_jd", lambda url: "x" * 300)
    result = ex.extract_jd("https://example.com/job")
    assert result.status == "SUCCESS"
    assert result.source == "http"


def test_extract_jd_falls_back_to_playwright(monkeypatch):
    import agents.jd_extractor as ex

    monkeypatch.setattr(ex, "scrape_jd", lambda url: None)
    monkeypatch.setattr(ex, "scrape_jd_playwright", lambda url: "y" * 300)
    result = ex.extract_jd("https://example.com/job")
    assert result.status == "SUCCESS"
    assert result.source == "playwright"


def test_extract_jd_requests_manual_when_all_fail(monkeypatch):
    import agents.jd_extractor as ex

    monkeypatch.setattr(ex, "scrape_jd", lambda url: None)
    monkeypatch.setattr(ex, "scrape_jd_playwright", lambda url: None)
    result = ex.extract_jd("https://example.com/job")
    assert result.status == "REQUEST_MANUAL_INPUT"
    assert "paste" in result.message.lower()


def test_extract_jd_empty_url():
    from agents.jd_extractor import extract_jd

    assert extract_jd("").status == "ERROR"
