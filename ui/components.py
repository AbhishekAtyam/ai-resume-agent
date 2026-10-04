"""Reusable themed UI components (header, step indicator, section header, loader)."""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st


_LOGO_SVG = (
    '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<rect x="2" y="2" width="20" height="20" rx="6" fill="url(#arlg)"/>'
    '<path d="M8.4 7.2h3.9l3.3 3.3V16a.9.9 0 0 1-.9.9H8.4a.9.9 0 0 1-.9-.9V8.1a.9.9 0 0 1 '
    '.9-.9z" fill="#ffffff"/>'
    '<path d="M12.3 7.2v3.3h3.3" stroke="#4f46e5" stroke-width="1.1" fill="none"/>'
    '<path d="M9.4 11.2h4.2M9.4 13h4.2M9.4 14.6h2.6" stroke="#6366f1" '
    'stroke-width="1" stroke-linecap="round"/>'
    '<defs><linearGradient id="arlg" x1="2" y1="2" x2="22" y2="22" '
    'gradientUnits="userSpaceOnUse">'
    '<stop stop-color="#6366f1"/><stop offset="1" stop-color="#22d3ee"/>'
    "</linearGradient></defs></svg>"
)


def header() -> None:
    """App brand block."""
    st.markdown(
        f'<div class="brand"><div class="brand-logo">{_LOGO_SVG}</div>'
        '<div><div class="app-title">AI Resume <span class="accent">Agent</span></div>'
        '<div class="app-sub">Tailor your resume to any job — ATS-ready, private, '
        "100% local.</div></div></div>",
        unsafe_allow_html=True,
    )


_CRUMB_STEPS = [
    ("profile", "Profile"), ("job", "Job"),
    ("confirm", "Confirm"), ("output", "Resume"),
]


def breadcrumb(ss) -> None:
    """Clickable step navigation. Jump to any reachable step; current highlighted."""
    stage = ss.get("stage", "profile")
    reach = {
        "profile": True,
        "job": bool(ss.get("profile")),
        "confirm": bool(ss.get("gap_analysis")),
        "output": bool(ss.get("gen_result")),
    }
    done = {
        "profile": bool(ss.get("profile")),
        "job": bool(ss.get("structured_jd")),
        "confirm": bool(ss.get("confirm_done")),
        "output": bool(ss.get("gen_result")),
    }
    cols = st.columns(len(_CRUMB_STEPS))
    for col, (key, label) in zip(cols, _CRUMB_STEPS):
        is_cur = key == stage
        mark = "✓ " if (done.get(key) and not is_cur) else ""
        if is_cur:
            col.button(f"{label}", key=f"crumb_{key}", type="primary",
                       use_container_width=True)
        else:
            if col.button(f"{mark}{label}", key=f"crumb_{key}",
                          disabled=not reach[key], use_container_width=True):
                ss["stage"] = key
                st.rerun()


def status_badge(status: str) -> str:
    """Return an inline HTML badge for a validation status."""
    if status == "PASS":
        return '<span class="badge ok">✓ PASS</span>'
    return '<span class="badge warn">⚠ WARNINGS</span>'


def section_header(title: str, desc: str = "") -> None:
    st.markdown(
        f'<div class="section-title">{title}</div>'
        + (f'<div class="section-desc">{desc}</div>' if desc else ""),
        unsafe_allow_html=True,
    )


@contextmanager
def neon_loader(msg: str, sub: str = ""):
    """A themed loading indicator shown while a block runs."""
    placeholder = st.empty()
    placeholder.markdown(
        f'<div class="neon-wrap"><div class="neon-ring"></div>'
        f'<div><div class="neon-msg">{msg}</div>'
        f'<div class="neon-sub">{sub}</div></div></div>',
        unsafe_allow_html=True,
    )
    try:
        yield
    finally:
        placeholder.empty()
