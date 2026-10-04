# 📄 AI Resume Agent

> Turn your **master profile** + a **job description** into a job-specific, **ATS-friendly**,
> **max two-page** resume (PDF + editable DOCX) — powered by a **local** LLM. Zero paid APIs,
> your data never leaves your machine.

**New here? See [SETUP.md](SETUP.md) for step-by-step clone-and-run instructions.**

---

## ✨ What it does

You maintain **one** master resume. Every job wants something different. This app reads a
job description, compares it against your profile, and produces a **tailored** resume —
emphasizing the relevant skills, experience, and projects — then validates it and fixes
issues automatically.

> **Core principle — nothing fabricated.** Your master profile is the single source of
> truth. The agent **selects, reorders, and rewrites existing facts** but never invents
> experience, employers, dates, degrees, or skills. Skills not on your resume are added
> **only when you explicitly confirm them** (human-in-the-loop).

---

## 🧩 Features

**Workflow & UX**
- A **live animated pipeline graph** — nodes light up and edges flow as each real step runs.
- Clickable **breadcrumb navigation**, a live **activity panel**, and **dark / light** themes.
- Clean, shareable, professional UI (single page, no clutter).

**Profile management**
- Upload a master resume (**PDF/DOCX**) → auto-structured into an editable profile.
- Create, load, edit, and **delete** multiple saved profiles (stored locally).

**Job description ingestion**
- **Paste** a JD or provide a **URL** (HTTP + BeautifulSoup, with a **Playwright** fallback
  for JS/iframe-embedded boards), and a graceful **manual-paste** fallback.

**Tailoring & integrity**
- **Gap analysis** with evidence (matched / partial / working-knowledge / missing).
- **Human-in-the-loop** skill confirmation — add skills you truly have, per job (never
  written back to your master profile).
- Deterministic **fabrication guard**: facts come from your profile; skills limited to
  profile + confirmed.

**Rendering & validation**
- **Deterministic, black-&-white, single-column, ATS-safe** rendering (Python controls
  every pixel; the LLM only emits JSON). Snaps to a clean **1 or full 2 pages**.
- Validation: deterministic **ATS rule checks** + an **LLM judge** that catches unsupported
  claims / invented numbers, with a **bounded self-correction loop** (max 3 attempts).

---

## 🔬 How it works

```
Profile → Job Desc → Parse → Analyze → Match → Confirm → Customize → Format → Validate → Resume
```

- **LLM for reasoning + Python for deterministic work.** Every agent takes an injectable
  LLM (so tests run with no live model), and all LLM output is validated with Pydantic.
- **The LLM never controls layout.** It outputs structured JSON; Python (ReportLab for PDF,
  python-docx for DOCX) renders the exact, repeatable template.

---

## 🛠️ Tech stack

Python 3.11 · Streamlit (UI) · Ollama (local LLM, default `qwen3:8b`) · LangChain /
LangGraph-style orchestration · Pydantic · BeautifulSoup + Playwright (scraping) ·
PyMuPDF · ReportLab · python-docx · Pytest.

---

## 🚀 Quick start

> Full details (prerequisites, OS-specific steps, troubleshooting) → **[SETUP.md](SETUP.md)**.

```bash
git clone <your-repo-url>
cd <repo-folder>
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# In another terminal: start the local LLM
ollama serve
ollama pull qwen3:8b

# Run the app
streamlit run app.py        # http://localhost:8501
```

---

## ☁️ Deploy for free

The app is a single Streamlit service (no separate frontend/backend). The LLM is
auto-selected: **Ollama → Gemini → Groq** (first available). For a free public demo, deploy
on **Streamlit Community Cloud** with a free **Gemini** key (`GEMINI_API_KEY`) — the cloud
app has no Ollama so it uses Gemini automatically. Full step-by-step: **[DEPLOY.md](DEPLOY.md)**.
(Running locally keeps everything 100% private via Ollama.)

## 📁 Project structure

```
app.py                 # Streamlit entry point (the UI + flow)
agents/                # jd_extractor, jd_parser, jd_analyzer, profile_agent,
                       # gap_analyzer, resume_customizer, resume_formatter,
                       # ats_validator, llm_judge, correction_agent
graph/                 # orchestration (generate→validate→correct loop) + routers
tools/                 # web_scraper, playwright_scraper, resume_parser,
                       # pdf_utils (ReportLab), docx_generator (python-docx), file_utils
models/                # Pydantic schemas (jd / resume / validation)
llm/                   # provider-agnostic factory (get_llm)
config/                # settings, formatting.yaml, structured logging (PII-redacted)
ui/                    # theme, animated flow graph, components
prompts/               # LLM prompts (one file per agent)
storage/  outputs/  logs/   # local data & artifacts (git-ignored)
tests/                 # unit + integration (no live LLM required)
```

---

## ⚙️ Configuration (`.env`, optional)

| Key | Default | Purpose |
|-----|---------|---------|
| `OLLAMA_MODEL` | `qwen3:8b` | local model |
| `LLM_REASONING` | `false` | keep off → ~40× faster structured output |
| `MAX_PAGES` | `2` | hard page limit |
| `MAX_RETRIES` | `2` | correction retries (→ max 3 attempts) |
| `MAX_JD_CHARS` | `12000` | cap JD text sent to the LLM |

Resume layout (fonts, sizes, margins, section order) → `config/formatting.yaml`.

---

## 🔒 Security & privacy

- Runs **fully locally** — no resume data is sent to any external service.
- Uploads validated (type/size); filenames sanitized; path-traversal blocked.
- Logs are **PII-redacted** and git-ignored; `storage/`, `outputs/`, `logs/`, and `.env`
  are git-ignored.

---

## ✅ Testing

```bash
source .venv/bin/activate
pytest
```

Unit + integration tests run with a mocked LLM — **no Ollama needed** for the test suite.

---

## 🗺️ Status & roadmap

**Phase 1 complete** — profile management, JD processing, gap analysis + human-in-the-loop,
tailored generation (PDF/DOCX), validation + self-correction, and a polished animated UI.

**Next up:** stronger URL/JD fetching, and (future) automatic **job discovery**.

---

## 📜 License

Add your preferred license here (e.g. MIT) before publishing.
