"""Global theme for the AI Resume Agent UI (dark + light).

A refined, professional look (modern SaaS-dashboard aesthetic). All colors come
from CSS variables so the whole app AND the animated graph switch cleanly between
dark and light. inject_theme(mode) injects the stylesheet for the chosen mode.
"""

from __future__ import annotations

import streamlit as st

_ROOT_DARK = """
  --bg:#0b0f19; --bg-glow:rgba(99,102,241,.10);
  --surface:#121829; --surface-2:#161d31;
  --border:rgba(148,163,184,.14); --border-2:rgba(148,163,184,.22);
  --text:#e8ecf5; --muted:#97a1bb; --faint:#6b7490;
  --accent:#6366f1; --accent-soft:#8b8ff5; --accent-2:#22d3ee; --good:#34d399;
  --input-bg:#0e1424; --code-bg:#0e1424;
  --shadow:0 10px 30px rgba(0,0,0,.30);
  --canvas-bg:#0e1424; --canvas-dot:rgba(148,163,184,.14);
  --node-bg:#151c2e; --node-brd:#2b3350; --node-label:#7a83a3; --edge-idle:#2b3350;
"""

_ROOT_LIGHT = """
  --bg:#f5f7fc; --bg-glow:rgba(99,102,241,.10);
  --surface:#ffffff; --surface-2:#f2f5fb;
  --border:rgba(15,23,42,.10); --border-2:rgba(15,23,42,.16);
  --text:#1b2338; --muted:#5b6682; --faint:#8a93ad;
  --accent:#6366f1; --accent-soft:#5457d6; --accent-2:#0891b2; --good:#059669;
  --input-bg:#ffffff; --code-bg:#f1f5f9;
  --shadow:0 8px 24px rgba(15,23,42,.08);
  --canvas-bg:#f8fafc; --canvas-dot:rgba(100,116,139,.20);
  --node-bg:#ffffff; --node-brd:#cbd5e1; --node-label:#64748b; --edge-idle:#cbd5e1;
"""

_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp{
  background:
    radial-gradient(900px 500px at 50% -10%, var(--bg-glow), transparent 60%),
    var(--bg);
  color:var(--text); font-family:'Inter',system-ui,-apple-system,sans-serif;
}
[data-testid="stHeader"]{background:transparent;}
#MainMenu, footer{visibility:hidden;}
/* Hide Streamlit chrome for a clean, shareable product look */
[data-testid="stToolbar"], .stDeployButton,
[data-testid="stStatusWidget"], [data-testid="stDecoration"]{display:none!important;}
.block-container{padding-top:1.4rem;padding-bottom:3rem;max-width:1080px;}
p, span, label, li{color:var(--text);}
[data-testid="stCaptionContainer"], .stCaption{color:var(--muted)!important;}

.brand{display:flex;align-items:center;gap:13px;margin-bottom:2px;}
.brand-logo{width:40px;height:40px;display:flex;align-items:center;justify-content:center;}
.app-title{font-size:1.55rem;font-weight:800;letter-spacing:-.4px;margin:0;color:var(--text);}
.app-title .accent{color:var(--accent-soft);}
.app-sub{color:var(--muted);font-size:.9rem;margin:.12rem 0 0 0;}

.steppill{display:inline-flex;align-items:center;gap:8px;margin:14px 0 2px;
  padding:5px 12px;border-radius:999px;background:var(--surface);
  border:1px solid var(--border);color:var(--muted);font-size:.8rem;font-weight:700;
  letter-spacing:.3px;}
.steppill b{color:var(--text);}

.section-title{font-weight:700;font-size:1.15rem;margin:.1rem 0;color:var(--text);
  letter-spacing:-.2px;}
.section-desc{color:var(--muted);font-size:.9rem;margin:.1rem 0 .6rem;}

[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--surface);border:1px solid var(--border)!important;
  border-radius:14px;box-shadow:var(--shadow);padding:8px 6px;}

.stButton>button, .stDownloadButton>button{
  border-radius:10px;font-weight:600;font-size:.92rem;padding:.5rem 1.05rem;
  background:var(--surface-2);color:var(--text);border:1px solid var(--border-2);
  transition:all .15s ease;}
.stButton>button:hover, .stDownloadButton>button:hover{
  border-color:var(--accent);transform:translateY(-1px);}
.stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"]{
  background:linear-gradient(135deg,#4f46e5,#6366f1);border:none;color:#fff;
  box-shadow:0 4px 14px rgba(79,70,229,.26);}
.stButton>button[kind="primary"]:hover{filter:brightness(1.06);}

.stTextInput input, .stTextArea textarea, [data-baseweb="select"]>div,
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea{
  background:var(--input-bg)!important;color:var(--text)!important;
  border:1px solid var(--border)!important;border-radius:10px!important;}
.stTextInput input:focus, .stTextArea textarea:focus{
  border-color:var(--accent)!important;box-shadow:0 0 0 2px rgba(99,102,241,.22)!important;}
.stRadio label, .stCheckbox label{color:var(--text)!important;}

[data-testid="stExpander"]{border:1px solid var(--border);border-radius:12px;
  background:var(--surface);}
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:12px 14px;}
[data-testid="stMetricValue"]{color:var(--text);font-weight:700;}
[data-testid="stMetricLabel"]{color:var(--muted);}
hr{border-color:var(--border);}
[data-testid="stAlert"]{border-radius:12px;}
code{background:var(--code-bg);border:1px solid var(--border);border-radius:6px;
  padding:1px 6px;color:var(--text);}

.neon-wrap{display:flex;align-items:center;gap:14px;padding:14px 18px;
  border-radius:12px;background:var(--surface);border:1px solid var(--border);
  box-shadow:var(--shadow);}
.neon-ring{width:26px;height:26px;border-radius:50%;
  border:3px solid rgba(99,102,241,.22);border-top-color:var(--accent-2);
  border-right-color:var(--accent);animation:spin .8s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}
.neon-msg{color:var(--text);font-weight:600;}
.neon-sub{color:var(--muted);font-size:.84rem;}

/* Health dot (top bar) */
.healthdot{display:inline-flex;align-items:center;gap:6px;font-size:.8rem;
  color:var(--muted);font-weight:600;}
.healthdot .dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.healthdot .dot.up{background:#34d399;box-shadow:0 0 8px rgba(52,211,153,.7);}
.healthdot .dot.down{background:#ef4444;box-shadow:0 0 8px rgba(239,68,68,.7);}

/* Badges */
.badge{display:inline-block;padding:.2rem .6rem;border-radius:999px;font-size:.78rem;
  font-weight:700;letter-spacing:.3px;}
.badge.ok{color:#34d399;background:rgba(52,211,153,.12);border:1px solid rgba(52,211,153,.4);}
.badge.warn{color:#f59e0b;background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.4);}

/* Summary / result cards */
.scard{background:var(--surface-2);border:1px solid var(--border);border-radius:12px;
  padding:14px 18px;margin:2px 0 8px;}
.scard .nm{font-size:1.1rem;font-weight:700;color:var(--text);}
.scard .meta{color:var(--muted);font-size:.88rem;margin-top:2px;}
.scard .chips{margin-top:10px;display:flex;gap:8px;flex-wrap:wrap;}
.chip{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:4px 10px;font-size:.8rem;color:var(--text);}
.chip b{color:var(--accent-soft);}
.rtitle{font-size:1.15rem;font-weight:700;color:var(--text);}
.rmeta{color:var(--muted);font-size:.9rem;margin-top:2px;}

/* App footer */
.appfoot{color:var(--faint);font-size:.78rem;text-align:center;margin-top:18px;
  padding-top:12px;border-top:1px solid var(--border);}
"""


def inject_theme(mode: str = "dark") -> None:
    """Inject the global stylesheet for the given mode ('dark' or 'light')."""
    root = _ROOT_LIGHT if mode == "light" else _ROOT_DARK
    st.markdown(f"<style>:root{{{root}}}{_BASE}</style>", unsafe_allow_html=True)
