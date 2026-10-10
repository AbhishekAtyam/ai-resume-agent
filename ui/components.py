"""Reusable themed UI components (header, navigation, banners, loader)."""

from __future__ import annotations

import streamlit as st

_LOGO_SVG = (
    '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" '
    'xmlns="http://www.w3.org/2000/svg">'
    '<rect x="2" y="2" width="20" height="20" rx="6" fill="url(#arlg)"/>'
    '<path d="M8.4 7.2h3.9l3.3 3.3V16a.9.9 0 0 1-.9.9H8.4a.9.9 0 0 1-.9-.9V8.1a.9.9 0 0 1 '
    '.9-.9z" fill="#ffffff"/>'
    '<path d="M12.3 7.2v3.3h3.3" stroke="#3b63e6" stroke-width="1.1" fill="none"/>'
    '<path d="M9.4 11.2h4.2M9.4 13h4.2M9.4 14.6h2.6" stroke="#4f7cff" '
    'stroke-width="1" stroke-linecap="round"/>'
    '<defs><linearGradient id="arlg" x1="2" y1="2" x2="22" y2="22" '
    'gradientUnits="userSpaceOnUse">'
    '<stop stop-color="#4f7cff"/><stop offset="1" stop-color="#22d3ee"/>'
    "</linearGradient></defs></svg>"
)


def header() -> None:
    """App brand block."""
    st.markdown(
        f'<div class="brand"><div class="brand-logo">{_LOGO_SVG}</div>'
        '<div><div class="app-title">AI Resume <span class="accent">Agent</span></div>'
        '<div class="app-sub">Craft a tailored, ATS-ready resume for any job '
        "in minutes.</div></div></div>",
        unsafe_allow_html=True,
    )


_CRUMB_STEPS = [
    ("profile", "Profile"), ("job", "Job"),
    ("confirm", "Review"), ("output", "Resume"),
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
    for i, (col, (key, label)) in enumerate(zip(cols, _CRUMB_STEPS), start=1):
        is_cur = key == stage
        mark = "✓ " if (done.get(key) and not is_cur) else f"{i}. "
        if is_cur:
            col.button(f"{i}. {label}", key=f"crumb_{key}", type="primary",
                       use_container_width=True)
        else:
            if col.button(f"{mark}{label}", key=f"crumb_{key}",
                          disabled=not reach[key], use_container_width=True):
                ss["stage"] = key
                st.rerun()


def section_header(eyebrow: str, title: str, desc: str = "") -> None:
    """A step heading: small uppercase eyebrow + title + description."""
    html = ""
    if eyebrow:
        html += f'<div class="eyebrow">{eyebrow}</div>'
    html += f'<div class="section-title">{title}</div>'
    if desc:
        html += f'<div class="section-desc">{desc}</div>'
    st.markdown(html, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    """Return an inline HTML badge for a validation status."""
    if status == "PASS":
        return '<span class="badge ok">PASSED</span>'
    return '<span class="badge warn">NEEDS REVIEW</span>'


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def chips(label: str, items, key: bool = False) -> None:
    """Render a labelled row of chips (e.g. required/critical skills)."""
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    cls = "tchip key" if key else "tchip"
    if items:
        body = "".join(f'<span class="{cls}">{_esc(i)}</span>' for i in items)
    else:
        body = '<span class="tchip none">none detected</span>'
    st.markdown(
        f'<div class="chiplabel">{_esc(label)}</div><div class="chiprow">{body}</div>',
        unsafe_allow_html=True,
    )


def score_card(score: int, title: str, subtitle: str = "") -> None:
    """Render a circular ATS-score card coloured by band."""
    score = max(0, min(100, int(score)))
    color = "var(--good)" if score >= 85 else ("var(--warn)" if score >= 70
                                               else "var(--danger)")
    st.markdown(
        f'<div class="atswrap">'
        f'<div class="atsring" style="--ring-pct:{score};--ring-c:{color};">'
        f'<div class="inner"><div class="num">{score}</div><div class="den">/ 100</div>'
        f'</div></div>'
        f'<div class="atsinfo"><div class="t">{_esc(title)}</div>'
        f'<div class="s">{_esc(subtitle)}</div></div></div>',
        unsafe_allow_html=True,
    )


def checks_table(rows: list[dict]) -> None:
    """Render a pass/fail checks table.

    Each row: {label, passed: bool, detail: str, severity: "error"|"warning"|"info"}.
    """
    body = []
    for r in rows:
        passed = r.get("passed", False)
        sev = r.get("severity", "error")
        if passed:
            mark, cls = "✓", "st ok"
        elif sev == "warning":
            mark, cls = "!", "st warnc"
        else:
            mark, cls = "✗", "st no"
        body.append(
            f'<tr><td class="{cls}">{mark}</td>'
            f'<td class="lbl">{_esc(r.get("label", ""))}</td>'
            f'<td class="dt">{_esc(r.get("detail", ""))}</td></tr>'
        )
    st.markdown(
        '<table class="ctbl"><thead><tr><th style="width:42px;">Status</th>'
        '<th>Check</th><th>Details</th></tr></thead><tbody>'
        + "".join(body) + "</tbody></table>",
        unsafe_allow_html=True,
    )


def processing_banner(title: str, sub: str = "") -> None:
    """A prominent 'working…' banner with an animated progress bar."""
    st.markdown(
        f'<div class="proc"><div class="ring"></div>'
        f'<div style="flex:1;"><div class="pt">{title}</div>'
        f'<div class="ps">{sub}</div>'
        f'<div class="procbar"><i></i></div></div></div>',
        unsafe_allow_html=True,
    )
