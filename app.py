"""Streamlit entry point for the AI Resume Agent.

A single animated workflow-graph UI. The graph at the top reflects REAL pipeline
state; nodes light up and edges flow as each step runs. The flow auto-advances
through parse → analyze → match and customize → format → validate, pausing only
for genuine input: choose a profile, provide the JD, and confirm skills.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import streamlit as st

from agents.gap_analyzer import analyze_gap, candidate_skills_for_confirmation
from agents.jd_analyzer import analyze_jd
from agents.jd_extractor import extract_jd
from agents.jd_parser import parse_jd
from agents.profile_agent import build_profile_from_file, check_profile_completeness
from config.logging_config import get_logger, tail_log
from config.settings import settings
from graph.graph import generate_and_validate
from graph.routers import route_input
from llm.factory import active_provider, llm_available
from models.resume_models import MasterProfile
from tools.file_utils import (
    delete_profile,
    list_profiles,
    load_profile,
    sanitize_filename,
    save_profile,
    save_uploaded_resume,
)
from tools.resume_parser import ResumeParsingError
from ui.components import breadcrumb, header, neon_loader, section_header, status_badge
from ui.flow import STEP_DESC, render_activity, render_flow, resting_states
from ui.theme import inject_theme

logger = get_logger(__name__)

# Per-job state (never the master profile) cleared when starting a new job.
_JOB_SCOPED_KEYS = (
    "structured_jd", "jd_analysis", "gap_analysis", "confirmed_skills",
    "confirm_done", "gen_result", "gen_resume", "skill_confirm_editor",
)


def _reset_job_state() -> None:
    for key in _JOB_SCOPED_KEYS:
        st.session_state.pop(key, None)


def _lines_to_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.splitlines() if item.strip()]


def _friendly_error(exc: Exception) -> str:
    """Turn low-level errors into actionable user messages."""
    s = str(exc).lower()
    if any(k in s for k in ("connection", "refused", "timed out", "timeout",
                            "11434", "max retries", "connecterror")):
        return (f"{exc}\n\n**Is the local LLM running?** Start it with `ollama serve` "
                f"and make sure the model `{settings.ollama_model}` is pulled "
                f"(`ollama pull {settings.ollama_model}`).")
    return str(exc)


def _skill_rows(items) -> list[dict]:
    return [{"skill": s.skill, "evidence": s.evidence} for s in items]


# --------------------------------------------------------------------------- #
# Animated chains (re-render the graph between real agent calls)
# --------------------------------------------------------------------------- #
def _run_jd_chain(graph_ph, status_ph) -> None:
    """Parse → Analyze → Match, animating the graph + activity panel as each runs."""
    ss = st.session_state
    profile, raw = ss["profile"], ss["raw_jd"]
    done = {"profile", "job"}
    log: list[str] = []  # finished-step labels for the activity card

    render_flow(graph_ph, done, "parse")
    render_activity(status_ph, log, STEP_DESC["parse"], title="Processing job description")
    time.sleep(0.2)
    jd = parse_jd(raw); ss["structured_jd"] = jd; done.add("parse")
    log.append(f"Parsed JD — {len(jd.required_skills)} required skill(s), "
               f"role: {jd.job_title or 'n/a'}")

    render_flow(graph_ph, done, "analyze")
    render_activity(status_ph, log, STEP_DESC["analyze"], title="Processing job description")
    time.sleep(0.2)
    analysis = analyze_jd(jd); ss["jd_analysis"] = analysis; done.add("analyze")
    log.append(f"Analyzed role — {len(analysis.critical_skills)} critical skill(s)")

    render_flow(graph_ph, done, "gap")
    render_activity(status_ph, log, STEP_DESC["gap"], title="Processing job description")
    time.sleep(0.2)
    gap = analyze_gap(profile, jd, analysis); ss["gap_analysis"] = gap; done.add("gap")
    log.append(f"Matched profile — {len(gap.matched_skills)} matched, "
               f"{len(gap.missing_skills)} missing")

    render_flow(graph_ph, done, "confirm")
    render_activity(status_ph, log, "Ready for your skill confirmation…",
                    title="Processing job description")
    time.sleep(0.2)


def _run_generate_chain(graph_ph, status_ph) -> None:
    """Customize → Format → Validate (+loop), animating graph + activity panel."""
    ss = st.session_state
    jd = ss["structured_jd"]
    user = ss.get("profile_user", "user")
    company = jd.company or "company"
    basename = sanitize_filename(f"{user}_{company}_{jd.job_title or 'role'}")
    out_dir = Path(settings.outputs_dir) / "resumes"

    state = {"done": {"profile", "job", "parse", "analyze", "gap", "confirm"},
             "active": "customize"}
    log: list[str] = []

    # Finished-step labels keyed by node, appended as the pipeline advances.
    done_label = {
        "customize": "Customized resume to the job",
        "format": "Rendered PDF & DOCX (page-fitted)",
        "validate": "Validated (ATS + LLM judge)",
    }

    def _advance(node: str) -> None:
        """Mark the previous active node done (once) before switching to `node`."""
        prev = state["active"]
        if prev != node and prev in done_label and prev not in state["done"]:
            state["done"].add(prev)
            log.append(done_label[prev])

    def cb(msg: str) -> None:
        m = msg.lower()
        loop = False
        current = STEP_DESC["customize"]
        if "customiz" in m:
            _advance("customize"); state["active"] = "customize"
            current = STEP_DESC["customize"]
        elif "rendering" in m:
            _advance("format"); state["active"] = "format"
            current = STEP_DESC["format"]
        elif "ats" in m:
            _advance("validate"); state["active"] = "validate"
            current = STEP_DESC["validate"]
        elif "judge" in m:
            state["active"] = "validate"; loop = True
            current = STEP_DESC["validate"]
        elif "correction" in m:
            state["active"] = "validate"; loop = True
            current = msg  # includes the attempt number
        render_flow(graph_ph, state["done"], state["active"], loop=loop)
        render_activity(status_ph, log, current, title="Generating your resume")

    result = generate_and_validate(
        ss["profile"], jd, ss.get("jd_analysis"), ss.get("gap_analysis"),
        ss.get("confirmed_skills", []), out_dir, basename=basename, progress=cb,
    )
    state["done"].update(["customize", "format", "validate", "output"])
    render_flow(graph_ph, state["done"], "output")
    render_activity(
        status_ph,
        log + ["Validated (ATS + LLM judge)"],
        current=None,
        note=f"Done — status: {result['status']}, {result['page_count']} page(s).",
        title="Resume ready",
    )
    ss["gen_result"] = result
    ss["gen_resume"] = result["resume"]


# --------------------------------------------------------------------------- #
# Profile editor
# --------------------------------------------------------------------------- #
def _profile_editor(profile: MasterProfile) -> MasterProfile:
    st.markdown("#### Personal")
    c1, c2 = st.columns(2)
    name = c1.text_input("Name", profile.personal.name)
    email = c2.text_input("Email", profile.personal.email)
    phone = c1.text_input("Phone", profile.personal.phone)
    location = c2.text_input("Location", profile.personal.location)

    summary = st.text_area("Professional summary", profile.summary, height=110)
    skills = _lines_to_list(
        st.text_area("Skills (one per line)", "\n".join(profile.skills), height=110))

    st.caption('Edit as JSON. Use "Present" for a current role; put CGPA/% in `grade`.')
    exp_raw = st.text_area("experience (JSON)",
        json.dumps([e.model_dump() for e in profile.experience], indent=2), height=180)
    proj_raw = st.text_area("projects (JSON)",
        json.dumps([p.model_dump() for p in profile.projects], indent=2), height=160)
    edu_raw = st.text_area("education (JSON)",
        json.dumps([e.model_dump() for e in profile.education], indent=2), height=140)

    with st.expander("Optional (links, certifications, achievements, languages, hobbies)"):
        lc1, lc2, lc3 = st.columns(3)
        linkedin = lc1.text_input("LinkedIn", profile.personal.linkedin)
        github = lc2.text_input("GitHub", profile.personal.github)
        portfolio = lc3.text_input("Portfolio", profile.personal.portfolio)
        certifications = _lines_to_list(st.text_area(
            "certifications (one per line)", "\n".join(profile.certifications), height=70))
        achievements = _lines_to_list(st.text_area(
            "achievements (one per line)", "\n".join(profile.achievements), height=70))
        ac1, ac2 = st.columns(2)
        languages = _lines_to_list(ac1.text_area(
            "languages", "\n".join(profile.languages), height=70))
        hobbies = _lines_to_list(ac2.text_area(
            "hobbies", "\n".join(profile.hobbies), height=70))

    return MasterProfile(
        personal={"name": name, "email": email, "phone": phone, "location": location,
                  "linkedin": linkedin, "github": github, "portfolio": portfolio},
        summary=summary, skills=skills,
        experience=json.loads(exp_raw or "[]"),
        projects=json.loads(proj_raw or "[]"),
        education=json.loads(edu_raw or "[]"),
        certifications=certifications, achievements=achievements,
        languages=languages, hobbies=hobbies,
    )


# --------------------------------------------------------------------------- #
# Stage panels
# --------------------------------------------------------------------------- #
def _profile_panel(graph_ph) -> None:
    ss = st.session_state

    if ss.get("profile") is None:
        section_header("① Start — choose your profile",
                       "Use a saved profile or upload your master resume once.")
        existing = list_profiles()
        options = ["Existing profile", "New upload"] if existing else ["New upload"]
        src = st.radio("Profile source", options, horizontal=True)

        if src == "Existing profile":
            chosen = st.selectbox("Select a saved profile", existing)
            lc, dc = st.columns([1, 1])
            if lc.button("Load profile ▶", type="primary", use_container_width=True):
                render_flow(graph_ph, set(), "profile")
                with neon_loader("Loading profile…"):
                    ss["profile"] = load_profile(chosen)
                    ss["profile_user"] = chosen
                st.rerun()
            if dc.button("🗑 Delete", use_container_width=True):
                ss["confirm_delete"] = chosen
                st.rerun()

            # Two-step delete confirmation.
            if ss.get("confirm_delete"):
                target = ss["confirm_delete"]
                st.warning(f"Delete profile **{target}**? This removes its saved data "
                           "permanently.")
                yc, nc = st.columns([1, 1])
                if yc.button("Confirm delete", type="primary", use_container_width=True):
                    delete_profile(target)
                    if ss.get("profile_user") == target:
                        ss.pop("profile", None); ss.pop("profile_user", None)
                    ss.pop("confirm_delete", None)
                    ss["_toast"] = f"🗑 Deleted profile '{target}'"
                    st.rerun()
                if nc.button("Cancel", use_container_width=True):
                    ss.pop("confirm_delete", None)
                    st.rerun()
        else:
            user_id = st.text_input("Profile name / User ID",
                                    value=ss.get("profile_user", "user_001"))
            up = st.file_uploader("Upload master resume (PDF/DOCX)", type=["pdf", "docx"])
            if up is not None and st.button("Structure resume ▶", type="primary"):
                try:
                    path = save_uploaded_resume(user_id, up.name, up.getvalue())
                    render_flow(graph_ph, set(), "profile")
                    with neon_loader("Structuring your resume…",
                                     "Local LLM — nothing leaves your machine"):
                        ss["profile"] = build_profile_from_file(path)
                        ss["profile_user"] = user_id
                        # Persist immediately so the profile is saved & selectable
                        # later even if the user doesn't click "Save changes".
                        save_profile(user_id, ss["profile"])
                    st.rerun()
                except ResumeParsingError as exc:
                    st.error(f"Could not parse resume: {exc}")
                except Exception as exc:  # noqa: BLE001
                    logger.error("Profile structuring failed: %s", exc)
                    st.error(_friendly_error(exc))
        return

    # Profile exists -> summary card + review/edit, then continue.
    section_header("① Profile ready", "Review & edit, then continue to the job description.")

    p = ss["profile"]
    meta = " · ".join(x for x in [p.personal.email, p.personal.phone,
                                  p.personal.location] if x) or "—"
    st.markdown(
        f'<div class="scard"><div class="nm">{p.personal.name or "Unnamed profile"}</div>'
        f'<div class="meta">{meta}</div>'
        f'<div class="chips">'
        f'<span class="chip"><b>{len(p.skills)}</b> skills</span>'
        f'<span class="chip"><b>{len(p.experience)}</b> experience</span>'
        f'<span class="chip"><b>{len(p.projects)}</b> projects</span>'
        f'<span class="chip"><b>{len(p.education)}</b> education</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    missing = check_profile_completeness(p)
    if missing:
        st.warning("Recommended fields:\n\n" + "\n".join(f"- {m}" for m in missing))
    with st.expander("Review / edit profile", expanded=bool(missing)):
        try:
            edited = _profile_editor(p)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
            edited = None
        if edited is not None and st.button("💾 Save changes"):
            save_profile(ss["profile_user"], edited)
            ss["profile"] = edited
            st.toast("💾 Profile saved")

    c1, c2 = st.columns([1, 1])
    if c1.button("Continue to Job Description ▶", type="primary"):
        save_profile(ss["profile_user"], ss["profile"])  # persist any saved edits
        ss["stage"] = "job"; st.rerun()
    if c2.button("Use a different profile"):
        ss.pop("profile", None); ss.pop("profile_user", None)
        _reset_job_state()
        st.rerun()


def _job_panel(graph_ph, status_ph) -> None:
    ss = st.session_state
    section_header("② Job Description",
                   "Paste the JD (most reliable) or give a URL. We'll parse, analyze "
                   "and match automatically.")
    method = st.radio("Input method", ["Paste Job Description", "Job URL"], horizontal=True)

    def _continue_with_jd() -> None:
        try:
            _run_jd_chain(graph_ph, status_ph)
            ss["stage"] = "confirm"
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            logger.error("JD processing failed: %s", exc)
            st.error(_friendly_error(exc))

    if method == "Job URL":
        url = st.text_input("Job URL", placeholder="https://...")
        if st.button("Fetch, parse & match ▶", type="primary"):
            if route_input(url, None) != "extract":
                st.error("Please enter a valid job URL.")
            else:
                render_flow(graph_ph, {"profile"}, "job")
                with neon_loader("Fetching job description…",
                                 "Direct fetch, then a headless browser if needed"):
                    result = extract_jd(url)
                if result.status == "SUCCESS":
                    if result.raw_jd != ss.get("raw_jd"):
                        _reset_job_state()
                    ss["raw_jd"] = result.raw_jd
                    _continue_with_jd()
                else:
                    ss.pop("raw_jd", None)
                    st.warning(result.message)
                    with st.expander("Why did extraction fail?"):
                        st.markdown(
                            "Both methods returned too little text (sites block bots, "
                            "or render via JS). Pasting the JD is reliable. Logs:")
                        st.code(tail_log(20), language="text")
    else:
        pasted = st.text_area("Paste the complete job description", height=240,
                              value=ss.get("raw_jd", ""))
        if st.button("Parse & match ▶", type="primary"):
            if route_input(None, pasted) != "parse":
                st.error("Please paste the job description text.")
            else:
                if pasted.strip() != ss.get("raw_jd"):
                    _reset_job_state()
                ss["raw_jd"] = pasted.strip()
                _continue_with_jd()

    if st.button("◀ Back to profile"):
        ss["stage"] = "profile"; st.rerun()


def _confirm_panel(graph_ph, status_ph) -> None:
    ss = st.session_state
    gap = ss.get("gap_analysis")
    if gap is None:
        ss["stage"] = "job"; st.rerun()
        return

    section_header("③ Fit & skill confirmation (human-in-the-loop)",
                   "Review the match, then tick skills you truly have. Generation is "
                   "automatic after you confirm.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Matched", len(gap.matched_skills))
    c2.metric("🟡 Partial", len(gap.partial_skills))
    c3.metric("🔵 Working", len(gap.working_knowledge))
    c4.metric("❌ Missing", len(gap.missing_skills))
    with st.expander("Fit details"):
        if gap.matched_skills:
            st.markdown("**Matched**")
            st.dataframe(_skill_rows(gap.matched_skills), use_container_width=True)
        if gap.missing_skills:
            st.markdown("**Missing (never fabricated)**")
            st.dataframe(_skill_rows(gap.missing_skills), use_container_width=True)
        st.markdown("**Relevant experience**"); st.write(gap.relevant_experience or "—")
        st.markdown("**Relevant projects**"); st.write(gap.relevant_projects or "—")

    candidates = candidate_skills_for_confirmation(gap)
    edited = []
    if candidates:
        st.markdown("#### Skills you actually have")
        st.caption("ℹ️ Temporary for THIS job only — your master profile is unchanged.")
        already = set(ss.get("confirmed_skills", []))
        rows = [{"I have this": (c in already), "skill": c} for c in candidates]
        edited = st.data_editor(
            rows, hide_index=True, use_container_width=True,
            column_config={
                "I have this": st.column_config.CheckboxColumn("I have this", width="small"),
                "skill": st.column_config.TextColumn("Skill", disabled=True),
            }, key="skill_confirm_editor")
    else:
        st.info("No extra skills to confirm — ready to generate.")
    extra = st.text_input("Add other skills you have (comma-separated)")

    label = "Confirm & generate ▶" if candidates else "Generate resume ▶"
    cc1, cc2 = st.columns([1, 1])
    if cc1.button(label, type="primary"):
        confirmed = [r["skill"] for r in edited if r.get("I have this")]
        confirmed += [x.strip() for x in extra.split(",") if x.strip()]
        ss["confirmed_skills"] = sorted(set(confirmed))
        ss["confirm_done"] = True
        try:
            _run_generate_chain(graph_ph, status_ph)
            ss["_toast"] = (f"✅ Resume ready — {ss['gen_result']['status']} "
                            f"({ss['gen_result']['page_count']} page(s))")
            ss["stage"] = "output"
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            logger.error("Generation failed: %s", exc)
            st.error(_friendly_error(exc))
    if cc2.button("◀ Back to job"):
        ss["stage"] = "job"; st.rerun()


def _validation_report(result: dict) -> None:
    status = result["status"]
    rule, verdict = result.get("rule"), result.get("llm")
    if status == "PASS":
        st.success("✅ Validation PASSED — ATS structural + semantic checks clear.")
    else:
        st.warning(f"⚠️ Best result WITH WARNINGS after {len(result['attempts'])} attempts.")
    with st.expander("📋 Validation report", expanded=(status != "PASS")):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**ATS structural checks**")
            if rule is not None:
                st.write(f"Status: `{rule.status}` · Pages: {rule.page_count}")
                for e in rule.errors:
                    st.markdown(f"- ❌ {e}")
                for w in rule.warnings:
                    st.markdown(f"- ⚠️ {w}")
                if not rule.errors and not rule.warnings:
                    st.caption("No structural issues.")
        with c2:
            st.markdown("**Semantic checks (LLM judge)**")
            if verdict is not None:
                st.write(f"Status: `{verdict.status}`")
                for i in verdict.issues:
                    st.markdown(f"- ⚠️ {i}")
                for c in verdict.corrections:
                    st.markdown(f"- 🔧 {c}")
                if not verdict.issues:
                    st.caption("No unsupported claims found.")
        st.markdown("**Attempts**")
        st.dataframe(result["attempts"], use_container_width=True)


def _output_panel(graph_ph) -> None:
    ss = st.session_state
    result = ss.get("gen_result")
    if not result:
        ss["stage"] = "confirm"; st.rerun()
        return

    section_header("④ Your tailored resume", "Validated, ATS-safe, max two pages.")

    jd = ss.get("structured_jd")
    role = (jd.job_title if jd else "") or "Role"
    company = (jd.company if jd else "") or "—"
    st.markdown(
        f'<div class="scard"><div class="rtitle">{role} &nbsp;{status_badge(result["status"])}'
        f'</div><div class="rmeta">Company: {company} &nbsp;·&nbsp; '
        f'{result["page_count"]} page(s)</div></div>',
        unsafe_allow_html=True,
    )

    _validation_report(result)

    pdf_path, docx_path = Path(result["pdf_path"]), Path(result["docx_path"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Pages", result["page_count"])
    if pdf_path.exists():
        c2.download_button("⬇️ Download PDF", pdf_path.read_bytes(),
                           file_name=pdf_path.name, mime="application/pdf")
    if docx_path.exists():
        c3.download_button(
            "⬇️ Download DOCX", docx_path.read_bytes(), file_name=docx_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    if pdf_path.exists():
        b64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="650" '
            f'style="border:1px solid var(--border);border-radius:12px;"></iframe>',
            unsafe_allow_html=True)

    st.divider()
    st.caption("What next?")
    b1, b2, b3 = st.columns(3)
    if b1.button("🔁 Another job (same profile) ▶", type="primary"):
        _reset_job_state(); ss["stage"] = "job"; st.rerun()
    if b2.button("👤 New / load another profile"):
        # Back to step 1 with the profile cleared -> shows load/create selection.
        _reset_job_state()
        ss.pop("profile", None); ss.pop("profile_user", None)
        ss["stage"] = "profile"; st.rerun()
    if b3.button("✏️ Edit current profile"):
        ss["stage"] = "profile"; st.rerun()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title="AI Resume Agent", page_icon="⬡", layout="wide")
    ss = st.session_state
    mode = ss.setdefault("theme", "dark")
    inject_theme(mode)
    logger.info("Streamlit app started")

    # Drain any queued toast from a previous run (survives st.rerun).
    queued = ss.pop("_toast", None)
    if queued:
        st.toast(queued)

    # --- Top bar: brand (left) · LLM health · theme toggle (right) ---
    brand_col, health_col, toggle_col = st.columns([6, 2, 1])
    with brand_col:
        header()
    with health_col:
        up = llm_available()
        label = f"{active_provider()}" if up else "offline"
        st.markdown(
            f'<div class="healthdot" style="margin-top:16px;justify-content:flex-end;">'
            f'<span class="dot {"up" if up else "down"}"></span>'
            f'LLM: {label}</div>',
            unsafe_allow_html=True,
        )
    with toggle_col:
        dark = st.toggle("🌙", value=(mode == "dark"), key="theme_toggle")
        new_mode = "dark" if dark else "light"
        if new_mode != mode:
            ss["theme"] = new_mode
            st.rerun()

    ss.setdefault("stage", "profile")
    stage = ss["stage"]

    # Clickable step navigation.
    breadcrumb(ss)

    # The live pipeline graph (reflects real state; animated by the chains).
    graph_ph = st.empty()
    done, active = resting_states(ss)
    render_flow(graph_ph, done, active)
    # Live activity panel — updated in lockstep with the graph during chains.
    status_ph = st.empty()
    st.write("")

    # Current step rendered inside a clean card.
    with st.container(border=True):
        if stage == "profile":
            _profile_panel(graph_ph)
        elif stage == "job":
            _job_panel(graph_ph, status_ph)
        elif stage == "confirm":
            _confirm_panel(graph_ph, status_ph)
        elif stage == "output":
            _output_panel(graph_ph)

    st.write("")
    with st.expander("⚙️ Engine & logs"):
        up = llm_available()
        prov = active_provider()
        health = ("🟢 LLM reachable" if up
                  else "🔴 No LLM available — start Ollama or set a Gemini/Groq key")
        model = {"ollama": settings.ollama_model, "gemini": settings.gemini_model,
                 "groq": settings.groq_model}.get(prov, "—")
        st.caption(f"{health} · Active provider `{prov}` · Model `{model}` "
                   f"(LLM_PROVIDER=`{settings.llm_provider}`)")
        st.code(tail_log(30), language="text")

    st.markdown(
        '<div class="appfoot">AI Resume Agent · runs fully locally · your data never '
        "leaves your machine</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
