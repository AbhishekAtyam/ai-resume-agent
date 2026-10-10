"""Streamlit entry point for the AI Resume Agent.

A guided, four-step workflow (Profile → Job → Review → Resume) built around a live
animated pipeline graph. Long-running steps run on a dedicated processing screen so
the UI always shows what's happening and duplicate submissions are impossible.
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
from ui.components import (
    breadcrumb,
    checks_table,
    chips,
    header,
    processing_banner,
    score_card,
    section_header,
    status_badge,
)
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


def _start_over() -> None:
    """Return to the very first step, clearing the current profile and job."""
    _reset_job_state()
    for key in ("profile", "profile_user", "raw_jd", "pending", "pending_url"):
        st.session_state.pop(key, None)
    st.session_state["stage"] = "profile"


def _lines_to_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.splitlines() if item.strip()]


def _friendly_error(exc: Exception) -> str:
    """Turn low-level errors into actionable user messages."""
    s = str(exc).lower()
    if any(k in s for k in ("connection", "refused", "timed out", "timeout",
                            "11434", "max retries", "connecterror")):
        return (f"{exc}\n\n**Is an LLM available?** Start Ollama locally "
                f"(`ollama serve`) or configure a Gemini/Groq API key.")
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
    log: list[str] = []

    render_flow(graph_ph, done, "parse")
    render_activity(status_ph, log, STEP_DESC["parse"], title="Processing the job")
    time.sleep(0.2)
    jd = parse_jd(raw); ss["structured_jd"] = jd; done.add("parse")
    log.append(f"Parsed the posting — {len(jd.required_skills)} required skill(s), "
               f"role: {jd.job_title or 'n/a'}")

    render_flow(graph_ph, done, "analyze")
    render_activity(status_ph, log, STEP_DESC["analyze"], title="Processing the job")
    time.sleep(0.2)
    analysis = analyze_jd(jd); ss["jd_analysis"] = analysis; done.add("analyze")
    log.append(f"Ranked priorities — {len(analysis.critical_skills)} critical skill(s)")

    render_flow(graph_ph, done, "gap")
    render_activity(status_ph, log, STEP_DESC["gap"], title="Processing the job")
    time.sleep(0.2)
    gap = analyze_gap(profile, jd, analysis); ss["gap_analysis"] = gap; done.add("gap")
    log.append(f"Matched your profile — {len(gap.matched_skills)} matched, "
               f"{len(gap.missing_skills)} to review")

    render_flow(graph_ph, done, "confirm")
    render_activity(status_ph, log, "Ready for your review.", title="Processing the job")
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
    done_label = {
        "customize": "Tailored the content to the role",
        "format": "Rendered the PDF & DOCX (fitted to pages)",
        "validate": "Validated (ATS rules + AI review)",
    }

    def _advance(node: str) -> None:
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
            current = msg
        render_flow(graph_ph, state["done"], state["active"], loop=loop)
        render_activity(status_ph, log, current, title="Generating your resume")

    result = generate_and_validate(
        ss["profile"], jd, ss.get("jd_analysis"), ss.get("gap_analysis"),
        ss.get("confirmed_skills", []), out_dir, basename=basename, progress=cb,
    )
    state["done"].update(["customize", "format", "validate", "output"])
    render_flow(graph_ph, state["done"], "output")
    render_activity(
        status_ph, log + ["Validated (ATS rules + AI review)"], current=None,
        note=f"Done — {result['status']}, {result['page_count']} page(s).",
        title="Resume ready",
    )
    ss["gen_result"] = result
    ss["gen_resume"] = result["resume"]


# --------------------------------------------------------------------------- #
# Processing screen — runs a pending long task with no duplicate-click risk
# --------------------------------------------------------------------------- #
_PENDING_COPY = {
    "structure": ("Structuring your resume", "Extracting your details with AI…"),
    "jd": ("Processing the job description", "Parsing, analyzing, and matching…"),
    "jd_url": ("Fetching & processing the job", "Reading the page, then matching…"),
    "generate": ("Generating your resume", "Tailoring, formatting, and validating…"),
}


def _run_pending(graph_ph, status_ph) -> None:
    """Execute the queued long task, then advance and rerun."""
    ss = st.session_state
    action = ss.get("pending")
    try:
        if action == "structure":
            path = ss.pop("pending_path", None)
            uid = ss.pop("pending_user", "user_001")
            render_flow(graph_ph, set(), "profile")
            render_activity(status_ph, [], "Reading and structuring your resume…",
                            title="Working")
            profile = build_profile_from_file(path)
            ss["profile"] = profile
            ss["profile_user"] = uid
            save_profile(uid, profile)
            ss["stage"] = "profile"
            ss["_toast"] = "Resume structured — review the details below"

        elif action == "jd":
            _run_jd_chain(graph_ph, status_ph)
            ss["stage"] = "confirm"

        elif action == "jd_url":
            url = ss.pop("pending_url", "")
            render_flow(graph_ph, {"profile"}, "job")
            render_activity(status_ph, [], "Fetching the job description…",
                            title="Working")
            result = extract_jd(url)
            if result.status == "SUCCESS":
                if result.raw_jd != ss.get("raw_jd"):
                    _reset_job_state()
                ss["raw_jd"] = result.raw_jd
                _run_jd_chain(graph_ph, status_ph)
                ss["stage"] = "confirm"
            else:
                ss["_jd_error"] = result.message
                ss["stage"] = "job"

        elif action == "generate":
            _run_generate_chain(graph_ph, status_ph)
            r = ss["gen_result"]
            ss["_toast"] = f"Resume ready — {r['status']} ({r['page_count']} page(s))"
            ss["stage"] = "output"

    except ResumeParsingError as exc:
        ss["_err"] = f"Could not read that resume: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.error("Pipeline step '%s' failed: %s", action, exc)
        ss["_err"] = _friendly_error(exc)
    finally:
        ss.pop("pending", None)
        ss.pop("pending_url", None)
        ss.pop("pending_path", None)
    st.rerun()


# --------------------------------------------------------------------------- #
# Profile editor
# --------------------------------------------------------------------------- #
def _profile_editor(profile: MasterProfile) -> MasterProfile:
    st.markdown("##### Personal")
    c1, c2 = st.columns(2)
    name = c1.text_input("Name", profile.personal.name)
    email = c2.text_input("Email", profile.personal.email)
    phone = c1.text_input("Phone", profile.personal.phone)
    location = c2.text_input("Location", profile.personal.location)

    summary = st.text_area("Professional summary", profile.summary, height=110)
    skills = _lines_to_list(
        st.text_area("Skills (one per line)", "\n".join(profile.skills), height=110))

    st.caption('Edit as JSON. Use "Present" for a current role; put CGPA/% in `grade`.')
    exp_raw = st.text_area("Experience (JSON)",
        json.dumps([e.model_dump() for e in profile.experience], indent=2), height=180)
    proj_raw = st.text_area("Projects (JSON)",
        json.dumps([p.model_dump() for p in profile.projects], indent=2), height=160)
    edu_raw = st.text_area("Education (JSON)",
        json.dumps([e.model_dump() for e in profile.education], indent=2), height=140)

    with st.expander("Optional details (links, certifications, achievements, languages, hobbies)"):
        lc1, lc2, lc3 = st.columns(3)
        linkedin = lc1.text_input("LinkedIn", profile.personal.linkedin)
        github = lc2.text_input("GitHub", profile.personal.github)
        portfolio = lc3.text_input("Portfolio", profile.personal.portfolio)
        certifications = _lines_to_list(st.text_area(
            "Certifications (one per line)", "\n".join(profile.certifications), height=70))
        achievements = _lines_to_list(st.text_area(
            "Achievements (one per line)", "\n".join(profile.achievements), height=70))
        ac1, ac2 = st.columns(2)
        languages = _lines_to_list(ac1.text_area(
            "Languages", "\n".join(profile.languages), height=70))
        hobbies = _lines_to_list(ac2.text_area(
            "Hobbies", "\n".join(profile.hobbies), height=70))

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
def _profile_panel() -> None:
    ss = st.session_state

    if ss.get("profile") is None:
        section_header("Step 1 of 4", "Choose your profile",
                       "Upload your master resume once, or continue with a saved profile.")
        existing = list_profiles()
        options = ["Saved profile", "Upload new"] if existing else ["Upload new"]
        src = st.radio("How would you like to start?", options, horizontal=True)

        if src == "Saved profile":
            chosen = st.selectbox("Select a saved profile", existing)
            lc, dc = st.columns([3, 1])
            if lc.button("Load profile →", type="primary", use_container_width=True):
                ss["profile"] = load_profile(chosen)
                ss["profile_user"] = chosen
                st.rerun()
            if dc.button("Delete", use_container_width=True):
                ss["confirm_delete"] = chosen
                st.rerun()

            if ss.get("confirm_delete"):
                target = ss["confirm_delete"]
                st.warning(f"Delete **{target}**? This permanently removes the saved "
                           "profile and its uploaded resume.")
                yc, nc = st.columns([1, 1])
                if yc.button("Yes, delete it", type="primary", use_container_width=True):
                    delete_profile(target)
                    if ss.get("profile_user") == target:
                        ss.pop("profile", None); ss.pop("profile_user", None)
                    ss.pop("confirm_delete", None)
                    ss["_toast"] = f"Deleted profile '{target}'"
                    st.rerun()
                if nc.button("Cancel", use_container_width=True):
                    ss.pop("confirm_delete", None)
                    st.rerun()
        else:
            user_id = st.text_input("Profile name", value=ss.get("profile_user", "My profile"),
                                    help="A label to save this profile under.")
            up = st.file_uploader("Upload your master resume (PDF or DOCX)",
                                  type=["pdf", "docx"])
            if up is not None and st.button("Structure resume →", type="primary"):
                try:
                    path = save_uploaded_resume(user_id, up.name, up.getvalue())
                    ss["pending_path"] = str(path)
                    ss["pending_user"] = user_id
                    ss["pending"] = "structure"
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(_friendly_error(exc))
        return

    # Profile exists -> summary card + review/edit, then continue.
    section_header("Step 1 of 4", "Your profile is ready",
                   "Review the details below, then continue to the job description.")

    p = ss["profile"]
    meta = " · ".join(x for x in [p.personal.email, p.personal.phone,
                                  p.personal.location] if x) or "No contact details yet"
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
        st.warning("For the best results, consider adding:\n\n"
                   + "\n".join(f"- {m}" for m in missing))
    with st.expander("Review and edit details", expanded=bool(missing)):
        try:
            edited = _profile_editor(p)
        except json.JSONDecodeError as exc:
            st.error(f"There's a formatting error in one of the JSON fields: {exc}")
            edited = None
        if edited is not None and st.button("Save changes"):
            save_profile(ss["profile_user"], edited)
            ss["profile"] = edited
            st.toast("Profile saved")

    c1, c2 = st.columns([3, 1])
    if c1.button("Continue →", type="primary", use_container_width=True):
        # Commit any unsaved edits (e.g. dates typed in the editor) so they aren't
        # lost just because the user didn't click "Save changes" first.
        if edited is not None:
            ss["profile"] = edited
        save_profile(ss["profile_user"], ss["profile"])
        ss["stage"] = "job"; st.rerun()
    if c2.button("Switch profile", use_container_width=True):
        ss.pop("profile", None); ss.pop("profile_user", None)
        _reset_job_state()
        st.rerun()


def _job_panel() -> None:
    ss = st.session_state
    section_header("Step 2 of 4", "Add the job description",
                   "Paste the job post (most reliable) or enter its URL. We'll parse, "
                   "analyze, and match it to your profile.")

    err = ss.pop("_jd_error", None)
    if err:
        st.warning(err)
        with st.expander("Why couldn't we read the URL?"):
            st.markdown("Many job boards block automated access or load content with "
                        "JavaScript. Pasting the text always works. Recent logs:")
            st.code(tail_log(20), language="text")

    method = st.radio("Input method", ["Paste text", "From URL"], horizontal=True)

    if method == "From URL":
        url = st.text_input("Job posting URL", placeholder="https://…")
        c1, c2 = st.columns([3, 1])
        if c1.button("Fetch & match →", type="primary", use_container_width=True):
            if route_input(url, None) != "extract":
                st.error("Please enter a valid URL.")
            else:
                ss["pending_url"] = url
                ss["pending"] = "jd_url"
                st.rerun()
        if c2.button("← Back", use_container_width=True):
            ss["stage"] = "profile"; st.rerun()
    else:
        pasted = st.text_area("Paste the full job description", height=240,
                              value=ss.get("raw_jd", ""))
        c1, c2 = st.columns([3, 1])
        if c1.button("Parse & match →", type="primary", use_container_width=True):
            if route_input(None, pasted) != "parse":
                st.error("Please paste the job description text first.")
            else:
                if pasted.strip() != ss.get("raw_jd"):
                    _reset_job_state()
                ss["raw_jd"] = pasted.strip()
                ss["pending"] = "jd"
                st.rerun()
        if c2.button("← Back", use_container_width=True):
            ss["stage"] = "profile"; st.rerun()


def _confirmable_skills(gap, jd, analysis, profile) -> list[str]:
    """Skills the user can confirm: gap candidates + the JD's hard skills they don't
    already have — so what they can tick matches what the job-fit score measures."""
    from agents.gap_analyzer import _covered_by_profile, _normkey
    from tools.skills import clean_skills

    out = candidate_skills_for_confirmation(gap)
    seen = {_normkey(x) for x in out}
    prof_norms = {_normkey(s) for s in (profile.skills if profile else [])}

    extra = list(jd.required_skills) + list(jd.tools_and_technologies) if jd else []
    if analysis is not None:
        extra += list(analysis.critical_skills) + list(analysis.important_skills)
    for s in clean_skills(extra):
        k = _normkey(s)
        if k in seen or _covered_by_profile(s, prof_norms):
            continue  # skip ones already in the profile
        seen.add(k)
        out.append(s)
    return out


def _confirm_panel() -> None:
    ss = st.session_state
    gap = ss.get("gap_analysis")
    if gap is None:
        ss["stage"] = "job"; st.rerun()
        return

    section_header("Step 3 of 4", "Review the match",
                   "Confirm any skills you genuinely have — they'll be woven in "
                   "naturally. Then generate your tailored resume.")

    # What the backend extracted from the posting (so the user can verify it).
    jd = ss.get("structured_jd")
    analysis = ss.get("jd_analysis")
    if jd is not None:
        title = jd.job_title or "Role"
        company = f" · {jd.company}" if jd.company else ""
        st.markdown(f'<div class="scard"><div class="nm">{title}{company}</div>'
                    '<div class="meta">What we read from the job posting</div></div>',
                    unsafe_allow_html=True)
        with st.expander("Parsed job description & analysis", expanded=True):
            if analysis is not None and analysis.critical_skills:
                chips("Critical skills", analysis.critical_skills, key=True)
            if analysis is not None and analysis.important_skills:
                chips("Important skills", analysis.important_skills)
            chips("Required skills", jd.required_skills, key=True)
            chips("Preferred skills", jd.preferred_skills)
            if jd.tools_and_technologies:
                chips("Tools & technologies", jd.tools_and_technologies)
            if analysis is not None and analysis.role_focus:
                chips("Role focus", analysis.role_focus)
            if jd.responsibilities:
                st.markdown('<div class="chiplabel">Key responsibilities</div>',
                            unsafe_allow_html=True)
                for r in jd.responsibilities[:6]:
                    st.markdown(f"- {r}")

    st.markdown("##### How your profile matches")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matched", len(gap.matched_skills))
    c2.metric("Partial", len(gap.partial_skills))
    c3.metric("Working", len(gap.working_knowledge))
    c4.metric("Missing", len(gap.missing_skills))
    with st.expander("See full match details"):
        if gap.matched_skills:
            st.markdown("**Matched skills**")
            st.dataframe(_skill_rows(gap.matched_skills), use_container_width=True)
        if gap.missing_skills:
            st.markdown("**Missing from your profile** (never added unless you confirm)")
            st.dataframe(_skill_rows(gap.missing_skills), use_container_width=True)
        st.markdown("**Most relevant experience**"); st.write(gap.relevant_experience or "—")
        st.markdown("**Most relevant projects**"); st.write(gap.relevant_projects or "—")

    candidates = _confirmable_skills(gap, jd, analysis, ss.get("profile"))
    edited = []
    if candidates:
        st.markdown("##### Skills you actually have")
        st.caption("Tick only what's genuinely true. These apply to this resume only — "
                   "your saved profile is never changed.")
        already = set(ss.get("confirmed_skills", []))
        rows = [{"I have this": (c in already), "Skill": c} for c in candidates]
        edited = st.data_editor(
            rows, hide_index=True, use_container_width=True,
            column_config={
                "I have this": st.column_config.CheckboxColumn("I have this", width="small"),
                "Skill": st.column_config.TextColumn("Skill", disabled=True),
            }, key="skill_confirm_editor")
    else:
        st.info("Your profile already covers the key skills — you're ready to generate.")
    extra = st.text_input("Add any other skills you have (comma-separated)")

    label = "Generate resume →" if candidates else "Generate resume →"
    c1, c2 = st.columns([3, 1])
    if c1.button(label, type="primary", use_container_width=True):
        confirmed = [r["Skill"] for r in edited if r.get("I have this")]
        confirmed += [x.strip() for x in extra.split(",") if x.strip()]
        ss["confirmed_skills"] = sorted(set(confirmed))
        ss["confirm_done"] = True
        ss["pending"] = "generate"
        st.rerun()
    if c2.button("← Back", use_container_width=True):
        ss["stage"] = "job"; st.rerun()


def _validation_report(result: dict) -> None:
    rule, verdict = result.get("rule"), result.get("llm")

    st.markdown("##### ATS structure & formatting")
    if rule is not None and rule.checks:
        checks_table(rule.checks)
    else:
        st.caption("No structural checks available.")

    st.markdown("##### Content review (AI)")
    rows: list[dict] = []
    if verdict is not None:
        rows.append({
            "label": "Factual consistency",
            "passed": verdict.status == "PASS", "severity": "error",
            "detail": ("Content is fully supported by your profile"
                       if verdict.status == "PASS"
                       else "Some items need attention (below)"),
        })
        for i in verdict.issues:
            rows.append({"label": "Needs attention", "passed": False,
                         "severity": "warning", "detail": i})
    checks_table(rows) if rows else st.caption("No content issues found.")
    if verdict is not None and verdict.corrections:
        st.caption("Suggestions: " + " · ".join(verdict.corrections))

    with st.expander("Generation attempts"):
        st.dataframe(result["attempts"], use_container_width=True)


def _score_explanation(result, structural, fit, overall) -> None:
    """Explain the score and give actionable evidence for what to fix."""
    rule = result.get("rule")
    reasons: list[str] = []

    if fit is not None and fit < 85:
        missing = result.get("missing_critical", [])
        if missing:
            reasons.append(
                f"**Job fit is {fit}%.** These skills the role calls for aren't on your "
                f"resume: **{', '.join(missing)}**. If you genuinely have them, go to "
                "**Review → confirm skills** and tick them — the score will rise. If not, "
                "this role may expect experience you don't list yet."
            )
        else:
            reasons.append(f"**Job fit is {fit}%** — broaden coverage of the role's "
                           "key skills where truthful.")

    if rule is not None:
        hard = [c["detail"] for c in rule.checks
                if not c["passed"] and c["severity"] == "error"]
        soft = [c["detail"] for c in rule.checks
                if not c["passed"] and c["severity"] == "warning"]
        if hard:
            reasons.append("**Structural issues to fix:** " + "; ".join(hard) + ".")
        elif structural < 100 and soft:
            reasons.append("**Minor structure tips:** " + "; ".join(soft[:3]) + ".")

    if overall >= 85 and not reasons:
        st.success("Looks strong — structure and job fit are both solid. Good to submit.")
        return
    if reasons:
        st.warning("**Why this score, and how to raise it**\n\n"
                   + "\n\n".join(f"- {r}" for r in reasons))


def _output_panel() -> None:
    ss = st.session_state
    result = ss.get("gen_result")
    if not result:
        ss["stage"] = "confirm"; st.rerun()
        return

    section_header("Step 4 of 4", "Your tailored resume",
                   "Reviewed and ATS-checked. Download it below, or start another.")

    jd = ss.get("structured_jd")
    role = (jd.job_title if jd else "") or "Role"
    company = (jd.company if jd else "") or "—"
    st.markdown(
        f'<div class="scard"><div class="rtitle">{role} &nbsp;{status_badge(result["status"])}'
        f'</div><div class="rmeta">{company} &nbsp;·&nbsp; '
        f'{result["page_count"]} page(s)</div></div>',
        unsafe_allow_html=True,
    )

    # --- Overall score (structure + job fit) ---
    rule = result.get("rule")
    structural = result.get("structural_score", rule.score if rule is not None else 0)
    fit = result.get("fit_score")
    overall = result.get("overall_score", structural)
    band = ("Strong — ready to submit" if overall >= 85
            else "Good — a few improvements" if overall >= 70
            else "Needs work before submitting")
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        score_card(overall, f"Resume score · {band}",
                   "Blends ATS structure with how well you fit this job")
    with sc2:
        st.metric("ATS structure", f"{structural}%")
        if fit is not None:
            st.metric("Job fit (critical skills)", f"{fit}%")
        st.metric("Pages", result["page_count"])

    _score_explanation(result, structural, fit, overall)

    pdf_path, docx_path = Path(result["pdf_path"]), Path(result["docx_path"])
    c1, c2 = st.columns(2)
    if pdf_path.exists():
        c1.download_button("⬇  Download PDF", pdf_path.read_bytes(),
                           file_name=pdf_path.name, mime="application/pdf",
                           use_container_width=True)
    if docx_path.exists():
        c2.download_button(
            "⬇  Download DOCX", docx_path.read_bytes(), file_name=docx_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True)

    _validation_report(result)

    if pdf_path.exists():
        st.markdown("##### Preview")
        b64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="650" '
            f'style="border:1px solid var(--border);border-radius:12px;"></iframe>',
            unsafe_allow_html=True)

    st.divider()
    b1, b2, b3 = st.columns(3)
    if b1.button("Create another →", type="primary", use_container_width=True):
        _reset_job_state(); ss["stage"] = "job"; st.rerun()
    if b2.button("New profile", use_container_width=True):
        _reset_job_state()
        ss.pop("profile", None); ss.pop("profile_user", None)
        ss["stage"] = "profile"; st.rerun()
    if b3.button("Edit profile", use_container_width=True):
        ss["stage"] = "profile"; st.rerun()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def _topbar(ss, mode) -> None:
    brand_col, health_col, toggle_col = st.columns([6, 2, 1])
    with brand_col:
        header()
    with health_col:
        up = llm_available()
        label = active_provider() if up else "offline"
        st.markdown(
            f'<div class="healthdot" style="margin-top:16px;justify-content:flex-end;">'
            f'<span class="dot {"up" if up else "down"}"></span>'
            f'AI engine: {label}</div>',
            unsafe_allow_html=True,
        )
    with toggle_col:
        st.write("")
        label = "☀️ Light" if mode == "dark" else "🌙 Dark"
        if st.button(label, key="theme_btn", use_container_width=True,
                     help="Switch light / dark theme"):
            ss["theme"] = "light" if mode == "dark" else "dark"
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="AI Resume Agent", page_icon="📄", layout="wide")
    ss = st.session_state
    mode = ss.setdefault("theme", "dark")
    inject_theme(mode)
    ss.setdefault("stage", "profile")
    logger.info("Streamlit app started")

    # Toasts + errors queued from a previous run (survive st.rerun).
    toast = ss.pop("_toast", None)
    if toast:
        st.toast(toast)
    err = ss.pop("_err", None)

    _topbar(ss, mode)
    if err:
        st.error(err)

    # --- Processing screen: a long task is running. No panel/buttons shown. ---
    if ss.get("pending"):
        title, sub = _PENDING_COPY.get(ss["pending"], ("Working…", "Please wait…"))
        processing_banner(title, sub)
        graph_ph = st.empty()
        status_ph = st.empty()
        done, active = resting_states(ss)
        render_flow(graph_ph, done, active)
        _run_pending(graph_ph, status_ph)  # animates, then reruns
        return

    # --- Normal view: navigation + graph + current step ---
    nav_col, over_col = st.columns([5, 1])
    with nav_col:
        breadcrumb(ss)
    with over_col:
        if st.button("↺ Start over", use_container_width=True,
                     help="Clear everything and return to step 1"):
            _start_over(); st.rerun()

    graph_ph = st.empty()
    done, active = resting_states(ss)
    render_flow(graph_ph, done, active)
    st.write("")

    with st.container(border=True):
        stage = ss["stage"]
        if stage == "profile":
            _profile_panel()
        elif stage == "job":
            _job_panel()
        elif stage == "confirm":
            _confirm_panel()
        elif stage == "output":
            _output_panel()

    st.write("")
    with st.expander("Engine & logs"):
        up = llm_available()
        prov = active_provider()
        health = ("🟢 AI engine reachable" if up
                  else "🔴 No AI engine available — start Ollama or set a Gemini/Groq key")
        model = {"ollama": settings.ollama_model, "gemini": settings.gemini_model,
                 "groq": settings.groq_model}.get(prov, "—")
        st.caption(f"{health} · Provider `{prov}` · Model `{model}`")
        st.code(tail_log(30), language="text")

    st.markdown('<div class="appfoot">AI Resume Agent</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
