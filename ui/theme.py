"""Global theme for the AI Resume Agent UI (dark + light).

Modern, production-grade look. Every color is a CSS variable so the whole app —
including the animated workflow graph and native Streamlit widgets — switches
cleanly between dark and light. inject_theme(mode) injects the stylesheet.
"""

from __future__ import annotations

import streamlit as st

_ROOT_DARK = """
  --bg:#1b1c1f; --bg-glow:rgba(138,180,248,.07);
  --surface:#26272b; --surface-2:#303134; --surface-3:#3c4043;
  --border:#3c4043; --border-2:#5f6368;
  --text:#e8eaed; --muted:#9aa0a6; --faint:#7e848d;
  --primary:#8ab4f8; --primary-2:#aecbfa; --on-primary:#202124; --accent-soft:#8ab4f8;
  --accent:#8ab4f8; --accent-2:#8ab4f8; --good:#81c995; --warn:#fdd663; --danger:#f28b82;
  --input-bg:#202124; --code-bg:#202124;
  --shadow:0 1px 3px rgba(0,0,0,.4), 0 6px 20px rgba(0,0,0,.28);
  --canvas-bg:#202124; --canvas-dot:rgba(255,255,255,.07);
  --node-bg:#303134; --node-brd:#5f6368; --node-label:#9aa0a6;
  --edge-idle:#5f6368;
"""

_ROOT_LIGHT = """
  --bg:#f8f9fa; --bg-glow:rgba(26,115,232,.06);
  --surface:#ffffff; --surface-2:#f1f3f4; --surface-3:#e8eaed;
  --border:#dadce0; --border-2:#c4c7c5;
  --text:#202124; --muted:#5f6368; --faint:#80868b;
  --primary:#1a73e8; --primary-2:#1765cc; --on-primary:#ffffff; --accent-soft:#1a73e8;
  --accent:#1a73e8; --accent-2:#1a73e8; --good:#188038; --warn:#e37400; --danger:#d93025;
  --input-bg:#ffffff; --code-bg:#f1f3f4;
  --shadow:0 1px 2px rgba(60,64,67,.1), 0 4px 14px rgba(60,64,67,.12);
  --canvas-bg:#ffffff; --canvas-dot:rgba(60,64,67,.12);
  --node-bg:#ffffff; --node-brd:#dadce0; --node-label:#5f6368;
  --edge-idle:#dadce0;
"""

_BASE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp{
  background:
    radial-gradient(1000px 520px at 50% -12%, var(--bg-glow), transparent 60%),
    var(--bg);
  color:var(--text);
  font-family:'Inter',system-ui,-apple-system,sans-serif;
}
[data-testid="stHeader"]{background:transparent;}
#MainMenu, footer{visibility:hidden;}
[data-testid="stToolbar"], .stDeployButton,
[data-testid="stStatusWidget"], [data-testid="stDecoration"]{display:none!important;}
.block-container{padding-top:1.3rem;padding-bottom:3rem;max-width:1060px;}
p, span, li{color:var(--text);}
label, [data-testid="stWidgetLabel"] p{color:var(--muted)!important;font-weight:600;}
[data-testid="stCaptionContainer"], .stCaption{color:var(--muted)!important;}

/* ---------- Brand / header ---------- */
.brand{display:flex;align-items:center;gap:13px;margin-bottom:0;}
.brand-logo{width:40px;height:40px;display:flex;align-items:center;justify-content:center;}
.app-title{font-size:1.5rem;font-weight:800;letter-spacing:-.4px;margin:0;color:var(--text);
  line-height:1.1;}
.app-title .accent{color:var(--accent-soft);}
.app-sub{color:var(--muted);font-size:.9rem;margin:.1rem 0 0 0;}

/* ---------- Section headings ---------- */
.eyebrow{font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
  color:var(--primary-2);}
.section-title{font-weight:700;font-size:1.22rem;margin:.1rem 0 .1rem;color:var(--text);
  letter-spacing:-.2px;}
.section-desc{color:var(--muted);font-size:.92rem;margin:.1rem 0 .7rem;line-height:1.5;}

/* ---------- Cards (bordered containers) ---------- */
[data-testid="stVerticalBlockBorderWrapper"]{
  background:var(--surface);border:1px solid var(--border)!important;
  border-radius:16px;box-shadow:var(--shadow);padding:10px 8px;}

/* ---------- Buttons (descendant selector so tooltip-wrapped buttons match too) ---------- */
.stButton button, .stDownloadButton button{
  border-radius:10px;font-weight:600;font-size:.92rem;padding:.55rem 1.05rem;
  background:var(--surface)!important;color:var(--text)!important;
  border:1px solid var(--border-2)!important;transition:all .15s ease;box-shadow:none;}
.stButton button:hover, .stDownloadButton button:hover{
  border-color:var(--primary)!important;color:var(--primary-2)!important;
  background:var(--surface-2)!important;transform:translateY(-1px);}
.stButton button:active{transform:translateY(0);}
.stButton button:disabled{opacity:.45;cursor:not-allowed;transform:none;}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"]{
  background:var(--primary)!important;border:1px solid var(--primary)!important;
  color:var(--on-primary)!important;box-shadow:var(--shadow);font-weight:700;}
.stButton button[kind="primary"]:hover{background:var(--primary-2)!important;
  border-color:var(--primary-2)!important;color:var(--on-primary)!important;}
.stButton button *, .stDownloadButton button *{color:inherit!important;}

/* ---------- File uploader ---------- */
[data-testid="stFileUploaderDropzone"], section[data-testid="stFileUploaderDropzone"]{
  background:var(--surface-2)!important;border:1px dashed var(--border-2)!important;
  border-radius:12px!important;color:var(--text)!important;}
[data-testid="stFileUploaderDropzone"] *{color:var(--text)!important;}
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzoneInstructions"] span{color:var(--muted)!important;}
[data-testid="stFileUploaderDropzone"] button{
  background:var(--surface)!important;color:var(--text)!important;
  border:1px solid var(--border-2)!important;border-radius:8px!important;}
[data-testid="stFileUploader"] [data-testid="stWidgetLabel"] p{color:var(--muted)!important;}

/* ---------- Radio / checkbox controls (fix unselected dot in both themes) ---------- */
[data-baseweb="radio"] [data-testid="stWidgetLabel"]{color:var(--text)!important;}
[data-baseweb="radio"] div[role="radio"]{background:transparent!important;}
[data-baseweb="radio"] div[role="radio"]>div{border-color:var(--border-2)!important;}
[data-baseweb="radio"] div[aria-checked="true"]>div{
  border-color:var(--primary)!important;background:var(--primary)!important;}
[data-baseweb="checkbox"] span[data-baseweb="checkbox"]>div{
  border-color:var(--border-2)!important;background:var(--input-bg)!important;}
[data-baseweb="checkbox"] span[aria-checked="true"]>div{
  background:var(--primary)!important;border-color:var(--primary)!important;}

/* ---------- Inputs ---------- */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea{
  background:var(--input-bg)!important;color:var(--text)!important;
  border:1px solid var(--border)!important;border-radius:10px!important;}
.stTextInput input::placeholder, .stTextArea textarea::placeholder{color:var(--faint)!important;}
.stTextInput input:focus, .stTextArea textarea:focus{
  border-color:var(--primary)!important;
  box-shadow:0 0 0 2px color-mix(in srgb,var(--primary) 30%,transparent)!important;}

/* Select control + its dropdown popover/menu (fixes light/dark mismatch) */
[data-baseweb="select"]>div{background:var(--input-bg)!important;color:var(--text)!important;
  border:1px solid var(--border)!important;border-radius:10px!important;}
[data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"], [data-baseweb="menu"] ul{
  background:var(--surface)!important;border:1px solid var(--border)!important;}
[role="option"]{background:var(--surface)!important;color:var(--text)!important;}
[role="option"]:hover, [role="option"][aria-selected="true"]{
  background:var(--surface-2)!important;}

/* Radio / checkbox / toggle accents */
.stRadio label, .stCheckbox label{color:var(--text)!important;font-weight:500;}
[data-baseweb="checkbox"] [data-testid="stCheckbox"] svg{color:var(--primary);}
[data-testid="stWidgetLabel"]+div [role="switch"][aria-checked="true"]{
  background:var(--primary)!important;}

/* ---------- Expander / metric / dataframe / alerts ---------- */
[data-testid="stExpander"]{border:1px solid var(--border)!important;border-radius:12px;
  background:var(--surface)!important;overflow:hidden;}
[data-testid="stExpander"] summary, [data-testid="stExpander"] details,
[data-testid="stExpander"] details>div{background:var(--surface)!important;}
[data-testid="stExpander"] summary{color:var(--text)!important;font-weight:600;
  padding:10px 14px;}
[data-testid="stExpander"] summary:hover{color:var(--primary-2)!important;}
[data-testid="stExpander"] summary p{color:var(--text)!important;}
[data-testid="stMetric"]{background:var(--surface-2);border:1px solid var(--border);
  border-radius:12px;padding:12px 14px;}
[data-testid="stMetricValue"]{color:var(--text);font-weight:700;}
[data-testid="stMetricLabel"]{color:var(--muted);}
[data-testid="stDataFrame"]{border:1px solid var(--border);border-radius:10px;}
hr{border-color:var(--border);}
[data-testid="stAlert"]{border-radius:12px;}
code{background:var(--code-bg);border:1px solid var(--border);border-radius:6px;
  padding:1px 6px;color:var(--text);}
.stRadio [role="radiogroup"]{gap:14px;}

@keyframes spin{to{transform:rotate(360deg);}}

/* ---------- Processing banner ---------- */
.proc{display:flex;align-items:center;gap:16px;padding:18px 22px;border-radius:16px;
  background:var(--surface);border:1px solid var(--border-2);box-shadow:var(--shadow);
  margin:4px 0 10px;}
.proc .ring{width:34px;height:34px;border-radius:50%;flex:0 0 auto;
  border:3px solid rgba(79,124,255,.22);border-top-color:var(--accent-2);
  border-right-color:var(--primary);animation:spin .8s linear infinite;}
.proc .pt{font-size:1.05rem;font-weight:700;color:var(--text);}
.proc .ps{color:var(--muted);font-size:.88rem;margin-top:1px;}
.procbar{height:4px;border-radius:999px;overflow:hidden;background:var(--surface-3);
  margin:8px 0 2px;}
.procbar i{display:block;height:100%;width:40%;border-radius:999px;
  background:linear-gradient(90deg,transparent,var(--primary),var(--accent-2),transparent);
  animation:slide 1.2s ease-in-out infinite;}
@keyframes slide{0%{margin-left:-40%;}100%{margin-left:100%;}}

/* ---------- Health dot / badges / cards / footer ---------- */
.healthdot{display:inline-flex;align-items:center;gap:7px;font-size:.8rem;
  color:var(--muted);font-weight:600;}
.healthdot .dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.healthdot .dot.up{background:var(--good);box-shadow:0 0 8px rgba(52,211,153,.7);}
.healthdot .dot.down{background:var(--danger);box-shadow:0 0 8px rgba(248,113,113,.7);}
.badge{display:inline-block;padding:.2rem .6rem;border-radius:999px;font-size:.76rem;
  font-weight:700;letter-spacing:.3px;vertical-align:middle;}
.badge.ok{color:var(--good);background:color-mix(in srgb,var(--good) 14%,transparent);
  border:1px solid color-mix(in srgb,var(--good) 45%,transparent);}
.badge.warn{color:var(--warn);background:color-mix(in srgb,var(--warn) 14%,transparent);
  border:1px solid color-mix(in srgb,var(--warn) 45%,transparent);}
.scard{background:var(--surface-2);border:1px solid var(--border);border-radius:14px;
  padding:16px 18px;margin:2px 0 10px;}
.scard .nm{font-size:1.15rem;font-weight:700;color:var(--text);}
.scard .meta{color:var(--muted);font-size:.88rem;margin-top:3px;}
.scard .chips{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;}
.chip{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:5px 11px;font-size:.8rem;color:var(--text);}
.chip b{color:var(--primary-2);}
.rtitle{font-size:1.2rem;font-weight:700;color:var(--text);}
.rmeta{color:var(--muted);font-size:.9rem;margin-top:3px;}
.appfoot{color:var(--faint);font-size:.78rem;text-align:center;margin-top:20px;
  padding-top:14px;border-top:1px solid var(--border);}
.appfoot b{color:var(--muted);font-weight:600;}

/* ---------- Chips (parsed JD / analysis) ---------- */
.chiplabel{font-size:.78rem;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:.06em;margin:10px 0 5px;}
.chiprow{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:4px;}
.tchip{background:var(--surface-2);border:1px solid var(--border);border-radius:999px;
  padding:4px 11px;font-size:.82rem;color:var(--text);}
.tchip.key{border-color:color-mix(in srgb,var(--primary) 50%,transparent);
  background:color-mix(in srgb,var(--primary) 12%,transparent);color:var(--primary-2);
  font-weight:600;}
.tchip.none{color:var(--faint);background:transparent;border-style:dashed;}

/* ---------- ATS score card ---------- */
.atswrap{display:flex;gap:18px;align-items:center;background:var(--surface-2);
  border:1px solid var(--border);border-radius:16px;padding:18px 22px;margin:4px 0 12px;}
.atsring{width:92px;height:92px;border-radius:50%;flex:0 0 auto;display:flex;
  align-items:center;justify-content:center;background:conic-gradient(var(--ring-c)
  calc(var(--ring-pct)*1%), var(--surface-3) 0);}
.atsring .inner{width:72px;height:72px;border-radius:50%;background:var(--surface);
  display:flex;flex-direction:column;align-items:center;justify-content:center;}
.atsring .num{font-size:1.5rem;font-weight:800;color:var(--text);line-height:1;}
.atsring .den{font-size:.66rem;color:var(--muted);margin-top:1px;}
.atsinfo .t{font-size:1.05rem;font-weight:700;color:var(--text);}
.atsinfo .s{color:var(--muted);font-size:.88rem;margin-top:2px;}

/* ---------- Checks table ---------- */
.ctbl{width:100%;border-collapse:separate;border-spacing:0;border:1px solid var(--border);
  border-radius:12px;overflow:hidden;margin:2px 0 10px;font-size:.88rem;}
.ctbl th{text-align:left;background:var(--surface-2);color:var(--muted);font-weight:700;
  padding:9px 14px;font-size:.76rem;text-transform:uppercase;letter-spacing:.05em;}
.ctbl td{padding:10px 14px;border-top:1px solid var(--border);color:var(--text);
  vertical-align:top;}
.ctbl tr:nth-child(even) td{background:color-mix(in srgb,var(--surface-2) 45%,transparent);}
.ctbl .st{font-weight:800;white-space:nowrap;}
.ctbl .st.ok{color:var(--good);}
.ctbl .st.no{color:var(--danger);}
.ctbl .st.warnc{color:var(--warn);}
.ctbl .lbl{font-weight:600;}
.ctbl .dt{color:var(--muted);}
"""


def inject_theme(mode: str = "dark") -> None:
    """Inject the global stylesheet for the given mode ('dark' or 'light')."""
    root = _ROOT_LIGHT if mode == "light" else _ROOT_DARK
    st.markdown(f"<style>:root{{{root}}}{_BASE}</style>", unsafe_allow_html=True)
