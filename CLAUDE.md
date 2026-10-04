# CLAUDE.md — AI Resume Agent (Project Constitution)

This file governs ALL work in this repo. Read it at the start of every session and
**do not drift from this plan**. If something here conflicts with a new instruction,
pause and confirm with the user before proceeding.

---

## 0. Working rules (HARD CONSTRAINTS — never violate)

1. **Approval before new files/dirs.** Do NOT create any file or directory that is not
   already in the Canonical Folder Structure (§6) without asking the user first.
2. **Stay on this plan.** Follow the phase order `0 → 1A → 1B → 1C → 1D → 1E → 1F → 1G`.
   Do not jump ahead, redesign, or add scope without approval.
3. **Log everything.** Every node/agent/tool logs start, key steps, and success/failure
   via `config.logging_config.get_logger`. NEVER log full resumes, emails, or phone
   numbers (use `redact()`).
4. **Test after every feature and every phase.** Write/run tests, run the app, verify
   the phase acceptance criteria, then update the Progress Log (§8) and report status
   before moving on.
5. **Never fabricate resume facts.** The master profile is the source of truth (§2).
6. **LLM never controls PDF layout.** LLM → structured JSON → Python renderer only.
7. **No LLM call where deterministic Python suffices.**
8. **Nothing hard-coded** that belongs in `config/` (`.env` / `settings.py` /
   `formatting.yaml`). Never hard-code the Ollama model.
9. **Structured output** (Pydantic) for every LLM response that affects app state.
10. **No infinite loops.** Correction/retry is capped (`MAX_RETRIES=2` → max 3 attempts).

---

## 1. Product goal

Transform `MASTER PROFILE + JOB DESCRIPTION → JOB-SPECIFIC RESUME` while preserving
factual accuracy. Output is a **max two-page** ATS-friendly PDF (+ editable DOCX).
Phase 1 runs fully locally with zero paid API cost; architecture stays extensible to
cloud LLMs, DBs, auth, multi-user, and job discovery (Phase 2).

---

## 2. Source-of-truth rule

The master profile is immutable source data. Agents MAY select, reorder, rewrite,
condense, highlight, and re-summarize existing content. Agents MUST NOT invent
companies, titles, dates, degrees, certifications, projects, responsibilities, years of
experience, achievements, or unconfirmed skills.

JD skills absent from the profile are **classified**, never fabricated:
`MATCHED · PARTIAL · WORKING_KNOWLEDGE · MISSING`.

---

## 3. Confirmed decisions

- **Rendering:** from one resume JSON, render **PDF via ReportLab** (precise 2-page
  measurement) **and DOCX via python-docx**. No LibreOffice / MS Word / external binary.
- **Python:** 3.11 (installed via Homebrew), venv at `.venv`.
- **LLM:** Ollama, default `qwen3:8b`, via the central `llm/factory.py:get_llm()`.
- **Constraints:** `MAX_PAGES=2`, `MAX_RETRIES=2`.
- **Storage:** local files + (later) SQLite for metadata. No Postgres/vector DB.
- **Scope discipline:** no Docker/K8s/Redis/Kafka/microservices/complex auth in Phase 1.

---

## 4. Agents / nodes (logical components)

LLM for reasoning + Python for deterministic work + LangGraph for orchestration.

1. **Input Router** — URL vs pasted JD vs error (deterministic).
2. **JD Extraction** — requests+BeautifulSoup → Playwright fallback → manual-input
   fallback. Scraping is never mandatory.
3. **JD Parser** — raw JD → `JobDescription` (structured LLM output).
4. **JD Analyzer** — prioritize critical/important/preferred skills, role focus → `JDAnalysis`.
5. **Master Profile Agent** — resume (PDF/DOCX) → `MasterProfile`; user reviews/edits.
6. **Gap Analysis** — JD vs profile → `GapAnalysis` with evidence; no unsupported skills.
7. **Resume Customizer** — profile + analyses → `CustomizedResume` (no fabrication).
8. **Resume Formatter** — JSON → Python renderer → DOCX + PDF (config-driven layout).
9. **ATS Validator (deterministic)** — `RuleValidationResult` (sections, contact, page
   count, extractability, etc.). Primarily Python.
10. **LLM Judge** — semantic quality → `LLMJudgeResult` (issues + corrections > score).
11. **Correction Agent** — apply judge corrections, re-format, re-validate (bounded).

---

## 5. LangGraph workflow

```
START → route_input → extract_jd → parse_jd → analyze_jd → load_profile
      → gap_analysis → customize_resume → format_resume → rule_validate
      → llm_validate → check_validation
check_validation: PASS → finalize → END
                 FAIL & retries < MAX → correction → format_resume → rule_validate → llm_validate
                 FAIL & retries >= MAX → finalize_with_warnings → END
```

State lives in `graph/state.py:ResumeState` (serializable; store paths, not blobs).

---

## 5b. Resume formatting rules (user-mandated — apply to ALL rendering)

- **Black & white ONLY.** No colors anywhere (text, rules, headings all black on white).
- **ATS-safe single-column** layout. No text boxes, images, icons, or multi-column
  body. Standard headings: SUMMARY, SKILLS, EXPERIENCE, PROJECTS, EDUCATION,
  CERTIFICATIONS, (ACHIEVEMENTS, LANGUAGES, HOBBIES if present).
- **One professional template, identical every run** — Python controls all layout
  (alignment, justification, spacing, font sizes) from `config/formatting.yaml`. The LLM
  never controls layout.
- One sans-serif family: **Helvetica** (PDF) ≈ **Arial** (DOCX). Sizes: name 16, heading
  12, body 10 (configurable).
- Centered name + contact header; UPPERCASE section headings each followed by a thin
  **black** horizontal rule; justified summary; left-aligned bullets ("• "); entry dates
  on their own line (no right-align tables).
- Max 2 pages (enforced in Phase 1E). Consistent spacing via config.
- Fabrication guard in generation: personal/education/certifications copied verbatim from
  profile; skills limited to profile skills + user-confirmed skills; experience/project
  factual fields (company/title/dates) taken from profile, only bullets may be rephrased.

## 6. Canonical folder structure (single source of truth for layout)

```
Resume_Project/
├── app.py                     # Streamlit entry point
├── requirements.txt
├── README.md
├── CLAUDE.md                  # this file
├── .env.example  /  .env      # .env is gitignored
├── .gitignore
├── pytest.ini
├── config/   settings.py · logging_config.py · formatting.yaml · __init__.py
├── llm/      factory.py · __init__.py
├── graph/    state.py · __init__.py          # graph.py · routers.py added later
├── models/   jd_models.py · resume_models.py · validation_models.py · __init__.py
├── agents/   (jd_extractor, jd_parser, jd_analyzer, profile_agent, gap_analyzer,
│              resume_customizer, resume_formatter, ats_validator, llm_judge,
│              correction_agent) — added per phase
├── tools/    (web_scraper, playwright_scraper, resume_parser, docx_generator,
│              pdf_utils, file_utils) — added per phase
├── prompts/  (jd_parser.txt, jd_analyzer.txt, profile_parser.txt, gap_analysis.txt,
│              resume_customizer.txt, llm_judge.txt, correction_agent.txt) — added per phase
├── ui/       theme.py (neon CSS) · flow.py (animated workflow graph — the live UI) ·
│              components.py (header, neon_loader) · pipeline.py (legacy hero, unused)
├── .streamlit/ config.toml                   # dark theme base for native widgets
├── storage/  users/ · applications/          # gitignored (PII)
├── outputs/  resumes/                        # gitignored
├── logs/     app.log (rotating)              # gitignored; PII-redacted app logs
└── tests/    unit/ · integration/
```

**Adding a file listed above as "added per phase" is expected** — but still announce it
in your status before creating it. Any file/dir NOT implied by this tree requires
explicit approval first (Rule 1).

---

## 7. Phase roadmap + acceptance criteria

- **Phase 0 — Setup:** structure, config, logging, Pydantic + state foundations, LLM
  factory, bare Streamlit app, pytest. ✅ *Done — see §8.*
- **Phase 1A — Profile mgmt:** upload PDF/DOCX → parse → LLM structure → `MasterProfile`
  → user review/edit → save/load. *Accept:* structured profile produced, editable,
  persisted.
- **Phase 1B — JD processing:** paste + URL (BeautifulSoup → Playwright → manual
  fallback), `JobDescription`, JD analyzer. *Accept:* both inputs work; failed
  extraction falls back to manual.
- **Phase 1C — Matching:** gap analysis, skill classification, relevant projects/exp,
  keyword gaps. *Accept:* no unsupported experience generated.
- **Phase 1D — Generation:** summary/skill/exp/project customization, bullet rewriting,
  resume JSON → DOCX + PDF. *Accept:* professional, readable resume rendered.
- **Phase 1E — Validation:** page count, ATS rules, LLM judge, correction + retry loop.
  *Accept:* max 3 total attempts, no infinite loop.
- **Phase 1F — Streamlit UI:** profile mgmt, JD input, progress, validation report,
  PDF/DOCX download.
- **Phase 1G — Testing & hardening:** unit + integration tests, error handling, logging,
  input validation, security checks, docs.

**Definition of Done (Phase 1):** see spec §37 (full checklist).

---

## 7b. Confirmed-skills / master-profile isolation (user-mandated invariant)

- The master profile is persisted ONLY in `storage/users/<id>/profile.json` and changed
  ONLY via the step-1 "Save profile" button. Nothing else writes it.
- Runtime HITL "confirmed skills" are **job-scoped and temporary**: held in
  `session_state["confirmed_skills"]`, used by the customizer for the CURRENT resume only,
  and NEVER written back to the profile. Generation agents only READ the profile
  (verified by `test_customize_does_not_mutate_master_profile`).
- On a new JD/company, `_reset_job_state()` clears all job-scoped keys
  (`_JOB_SCOPED_KEYS`: structured_jd, jd_analysis, gap_analysis, confirmed_skills,
  gen_result, gen_resume, skill_confirm_editor) so each company starts fresh from the
  base master profile — previous companies' confirmed skills never carry over.

## 8. Progress Log (update at the end of every phase)

- [x] **Phase 0 — Setup** (runnable skeleton)
  - Folder structure, `config/` (settings + logging + formatting.yaml), `llm/factory.py`,
    `graph/state.py`, `models/` stubs, `app.py` skeleton, `tests/unit/test_smoke.py`,
    requirements, `.gitignore`, `.env.example`, README, this CLAUDE.md.
  - Verified: `pytest` green, `streamlit run app.py` launches.
- [x] **Phase 1A — Profile management**
  - `tools/file_utils.py` (sanitize filename, path-traversal guard, upload validation,
    profile save/load, prompt loader), `tools/resume_parser.py` (PDF via PyMuPDF +
    DOCX via python-docx, content-length validation), `prompts/profile_parser.txt`
    (extract-only, no-fabrication), `agents/profile_agent.py` (`structure_resume_text`
    / `build_profile_from_file` via `with_structured_output(MasterProfile)`),
    `app.py` upload→structure→review/edit→save UI.
  - Fixed: PII redactor was mangling log timestamps → now redacts message body only.
  - Refinements (from manual testing): split education `year` → `start_year`/`end_year`
    + `grade` (CGPA/% bug); added optional `linkedin`/`github`/`portfolio`,
    `achievements`/`languages`/`hobbies`, experience `location` + "Present" support,
    project `link`; `normalize_location()` strips stray commas; `check_profile_completeness()`
    prompts the user to fill recommended-but-empty fields once; UI groups optional
    sections in an expander.
  - Verified: 22 tests pass; live `qwen3:8b` correctly routes CGPA→grade, pulls links /
    achievements / languages / hobbies, uses "Present", and flags missing fields;
    `streamlit run app.py` boots (HTTP 200).
- [x] **Phase 1B — JD processing**
  - `tools/web_scraper.py` (requests fetch + BeautifulSoup boilerplate strip +
    `is_sufficient_jd` quality gate), `tools/playwright_scraper.py` (headless Chromium
    fallback, degrades gracefully if unavailable), `agents/jd_extractor.py` (HTTP →
    Playwright → `REQUEST_MANUAL_INPUT`), `graph/routers.py` (`route_input`: paste wins
    over URL), `agents/jd_parser.py` → `JobDescription`, `agents/jd_analyzer.py` →
    `JDAnalysis`, prompts `jd_parser.txt` / `jd_analyzer.txt`, `models.JDExtractionResult`.
  - `app.py`: JD section (URL with scrape+fallback / paste), raw JD view, parse+analyze,
    structured JD + role-analysis display. Playwright `chromium` installed.
  - Verified: 36 tests pass; live HTTP scrape succeeded over network; live `qwen3:8b`
    parse+analyze produced correct required/preferred/critical skills + role focus;
    app boots (HTTP 200).
  - Minor known quirks (acceptable): job_title can capture the full header line;
    skill adjectives like "Strong" may be retained — can tighten prompts later.
  - PERF FIX: qwen3 "thinking" made structured output ~40x slower (parse took 263s!).
    Added `LLM_REASONING` (default **false**) → now ~6s/call; also `MAX_JD_CHARS=12000`
    truncation + optional `LLM_NUM_CTX`/`LLM_NUM_PREDICT`. Applies to ALL LLM calls
    (profile structuring is faster too).
  - Observability add-ons: persistent **rotating file logs** at `logs/app.log`
    (`config/logging_config.py`, PII-redacted, `tail_log()` helper); scraper now logs
    HTTP status / char-count-vs-threshold so the log shows *where* extraction failed;
    UI shows **elapsed time** per step (extract/parse/analyze/structure), a sidebar
    "📜 Recent logs" viewer, and a "Why did extraction fail?" expander on fallback.
    New `logs/` dir added to canonical structure + `.gitignore`.
  - PLAYWRIGHT FIX: `networkidle` wait never settled on analytics-heavy pages (30s
    timeout) and iframe-embedded JDs (Greenhouse/Lever/Workday) were missed. Now uses
    `domcontentloaded` + bounded content-polling + extracts text from ALL frames
    (`merge_extracted_texts`). Real Greenhouse page: 30s-timeout-fail → 9s success,
    8.4k chars.
- [x] **Phase 1C — Matching (Gap Analysis)**
  - `agents/gap_analyzer.py` (`analyze_gap` → `GapAnalysis`; `_build_payload` feeds real
    profile+JD only), `prompts/gap_analysis.txt` (classify matched/partial/
    working_knowledge/missing with evidence, under-claim rule, no fabrication).
  - Deterministic guard `reconcile_gap()`: enforces mutually-exclusive buckets and
    demotes any evidence-less non-missing claim to "missing" (fixes LLM putting a skill
    in "matched" with "No evidence" + duplicate buckets). `_has_real_evidence` detects
    absence phrases.
  - `app.py`: "Fit / Gap Analysis" section (needs profile + parsed JD) with
    matched/partial/working/missing tables + evidence, relevant exp/projects, keyword
    gaps, timing.
  - Verified: 44 tests pass; live run correctly keeps Snowflake in MISSING only (not
    fabricated as matched), no cross-bucket duplicates; app boots (HTTP 200).
  - HITL skill confirmation (user request): `candidate_skills_for_confirmation(gap)`
    lists not-matched skills + keyword gaps (excl. matched, deduped); `app.py` shows
    them as a **checkbox table** + free-text add. Ticked skills → `session_state
    ["confirmed_skills"]`, to be used by the Phase 1D customizer (added to Skills +
    woven into relevant projects where truthful). Unticked = never added. 45 tests pass.
  - **Phase 1D must consume `confirmed_skills`**: treat matched profile skills +
    user-confirmed skills as the allowed set; confirmed skills may appear in Skills and
    in experience/project bullets ONLY where truthful — still no fabricated facts.
- [x] **Phase 1D — Resume generation**
  - `agents/resume_customizer.py` (`customize_resume` → `CustomizedResume`;
    `_sanitize_resume` fabrication guard: personal/education/certs verbatim from profile,
    skills limited to profile+confirmed, experience/project factual fields matched to
    profile, only bullets rephrased), `prompts/resume_customizer.txt`.
  - `tools/pdf_utils.py` (ReportLab B&W single-column template + `count_pdf_pages`),
    `tools/docx_generator.py` (python-docx mirror, Arial, black, heading rules via oxml),
    `agents/resume_formatter.py` (renders BOTH from one JSON; `load_formatting()` reads
    `formatting.yaml`).
  - `app.py`: "Generate Resume" section — customize + render, page-count check vs
    `MAX_PAGES`, PDF/DOCX download buttons, inline PDF preview, uses confirmed skills.
  - Switched `fitz` → `pymupdf` import (deprecation).
  - Verified: 48 tests pass; live full pipeline produced a professional 1-page B&W resume
    (centered header, uppercase headings + black rules, justified summary, confirmed
    skills woven into Skills + Uber projects, employment facts preserved); app boots.
  - PAGE-FIT (user request: no 1.5-page look): verbose customizer (LENGTH TARGET ~2 full
    pages, truthful detail only) + deterministic `_fit_pdf` in formatter using
    `spacing_scale` (gentle leading + gap scaling in `pdf_utils._styles`) and
    `last_page_fill_ratio()` (PyMuPDF). Snaps to a clean 1 page or a full 2 pages
    (fill ≥~0.88), compresses if >2. Verified live: small profile → clean 1 page (81%),
    richer profile → full 2 pages (86%). 50 tests pass.
  - KNOWN (for Phase 1E judge): customizer can still introduce an unsupported metric in a
    bullet (e.g. "reducing manual effort by 40%" when profile had no number). The LLM
    judge must flag/strip invented numbers/claims; sanitizer only guards facts, not bullet
    phrasing.
- [x] **Phase 1E — Validation**
  - `agents/ats_validator.py` (`validate_ats` → `RuleValidationResult`: contact/email,
    sections, empty-entry hygiene, page count ≤ MAX_PAGES, PDF text extractability
    [threshold 50 = image-only detection], keyword stuffing).
  - `agents/llm_judge.py` + `prompts/llm_judge.txt` (factual-consistency judge: FAILs only
    on genuine fabrication — invented numbers/employers/titles/dates/degrees/certs or
    skills not in profile+confirmed; explicitly ALLOWS rephrasing + confirmed skills
    anywhere, to avoid false positives).
  - `agents/correction_agent.py` + `prompts/correction_agent.txt` (fixes issues; re-applies
    `_sanitize_resume` fabrication guard).
  - `graph/graph.py` `generate_and_validate`: bounded loop customize→format→rule→judge→
    (correct→repeat), ≤ MAX_RETRIES+1 attempts (=3), returns resume+paths+rule+llm+
    attempts+status (PASS | PASS_WITH_WARNINGS). Functions map to LangGraph nodes;
    monkeypatchable for tests.
  - `app.py`: "Generate & validate" + `_validation_report` (ATS checks, semantic issues/
    corrections, attempts table).
  - Verified: 58 tests pass (incl. loop-stops-at-max + passes-first-try, correction
    sanitizes, ATS pass/fail cases). Live: judge caught fabricated "40%" on attempt 1 →
    correction → attempt 2 PASS, no fabricated numbers; no infinite loop.
- [x] **Phase 1F — Streamlit UI (live animated workflow graph)**
  - Redesigned per user feedback: NO sidebar, NO multi-page nav, NO decorative hero. A
    single **animated node/edge pipeline graph** (`ui/flow.py`) IS the interface — nodes
    Profile→Job→Parse→Analyze→Match→Confirm→Customize→Format→Validate→Resume. Nodes are
    idle(grey)/active(pulsing cyan, incoming edge flowing)/done(green); human node
    (Confirm) pink; Validate shows a spin during the correction loop.
  - **Stage machine** (`ss.stage`: profile→job→confirm→output) auto-advances. Chains
    re-render the graph into a placeholder BETWEEN real agent calls (`_run_jd_chain`,
    `_run_generate_chain`) so the user watches it move node→node live. Only pauses for
    real input: choose/upload profile, provide JD, confirm skills. One click runs
    parse+analyze+match; confirm runs customize+format+validate(+loop).
  - `ui/theme.py` neon CSS; `.streamlit/config.toml` dark base; `neon_loader` for single
    ops; `progress` callback on `generate_and_validate` drives Validate-node animation.
  - Verified: 59 tests pass; app boots (HTTP 200), no errors.
  - Follow-up: added a **live activity panel** (`ui/flow.render_activity` + `STEP_DESC`)
    below the graph that updates in lockstep with the nodes during both chains — shows the
    current sub-step (neon spinner + description) and ✓ finished steps with short result
    notes (e.g. "Parsed JD — N required skills", "Matched — N matched, M missing"), incl.
    the "applying corrections (attempt N)" line during the judge loop. `status_ph`
    threaded main → _job_panel/_confirm_panel → chains. 59 tests pass, app boots.
- [x] **Phase 1G — Testing & hardening**
  - Integration tests `tests/integration/test_pipeline.py` with a flexible per-schema mock
    `FakeLLM`: full generate→validate PASS first try; recovery via one correction round;
    retries exhaust → PASS_WITH_WARNINGS (no infinite loop); JD parse→analyze→match chain.
  - Hardening: `llm/factory.ollama_available()` health check; `app._friendly_error()` turns
    connection errors into "start `ollama serve`" guidance (used in all action except
    blocks); 🟢/🔴 LLM health shown in Engine & logs panel.
  - README rewritten (setup, run, config, architecture, security, troubleshooting, phase
    status). Security/privacy already enforced (upload validation, path-traversal guard,
    PII-redacted logs, gitignored data/.env).
  - Verified: **63 tests pass** (unit + integration); app boots (HTTP 200).
  - **Phase 1 COMPLETE** — all Definition-of-Done items (spec §37) met.
  - UI polish (user feedback "looks not good/messy"): refined `ui/theme.py` to a calm,
    professional dark SaaS theme (deep slate bg, single indigo accent, less glow, clear
    type/spacing, bordered-container cards); graph moved onto a dotted "workflow canvas"
    with cleaner nodes; brand header + "Step N of 4" pill; each stage wrapped in
    `st.container(border=True)`. Animations kept. 63 tests pass, app boots.
  - Dark/Light toggle: `ui/theme.inject_theme(mode)` drives everything (incl. graph) via
    CSS variables (`_ROOT_DARK`/`_ROOT_LIGHT`); toggle in header stores `ss['theme']`.
  - Customizer factuality + consistency: confirmed skills go to Skills (+summary general
    familiarity) and are NOT asserted into specific past roles/projects unless the profile
    text supports it (prompt updated). Lowered temperature to 0.0 for customize + correction
    → stable output run-to-run. (Sanitizer already blocks any non-profile/non-confirmed
    skill — no random skills possible.)
  - Bug fixes: (1) uploaded profiles are now **auto-saved** to `profile.json` right after
    structuring (and on Continue) — previously only the raw PDF was saved unless the user
    clicked "Save changes", so new profiles didn't appear in the load dropdown
    (`list_profiles` needs profile.json). (2) Output step now offers **🔁 another job /
    👤 new-or-load-another-profile / ✏️ edit profile**, so the user can return to step 1.
    Removed dead `top_nav`/`STEPS` from `ui/components.py`; removed unused `user_dir`
    import; iframe border uses theme var. Compile-checked all modules; 63 tests pass.
  - UX pass 2: persistent **top bar** (brand · 🟢/🔴 LLM health · 🏠 Home · theme toggle);
    **clickable breadcrumb** nav (`ui/components.breadcrumb`, jump to any reachable step,
    current = primary, unreachable disabled) replacing the static step pill;
    **delete profile** (`tools/file_utils.delete_profile`, traversal-safe rmtree) with a
    two-step confirm in the picker; **profile summary card** + **output result card** with
    PASS/WARN **badge** (`status_badge`); **st.toast** feedback (save/delete/generate) via a
    `ss["_toast"]` queue drained in main; footer. Stop button intentionally skipped
    (synchronous Streamlit). 65 tests pass (added `test_delete_profile` + traversal test).
  - UX pass 3 (polish for sharing): removed Home button + toggle help "?"; refined brand
    (crisp SVG doc logo + shorter tagline "Tailor your resume to any job — ATS-ready,
    private, 100% local"); toned primary to professional indigo (#4f46e5→#6366f1, softer
    glow); hid Streamlit chrome (Deploy/toolbar/status) for a clean product look. Top bar
    now: brand · LLM health · theme toggle. 65 tests pass, boots clean.

---

## 9. Commands

```bash
python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
streamlit run app.py        # run the app
pytest                      # run tests
```
