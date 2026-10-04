"""Animated workflow graph — the live pipeline UI.

A single horizontal node/edge graph that reflects REAL pipeline state. Nodes are
idle (grey), active (pulsing cyan, with the incoming edge flowing), or done
(green). The driver re-renders this into a placeholder between agent calls so the
user watches the workflow move from node to node as it actually executes.
"""

from __future__ import annotations

import streamlit as st

# (id, icon, short label). Order defines the left-to-right pipeline.
NODES: list[tuple[str, str, str]] = [
    ("profile", "📄", "Profile"),
    ("job", "🧾", "Job Desc"),
    ("parse", "🔍", "Parse"),
    ("analyze", "📊", "Analyze"),
    ("gap", "🔗", "Match"),
    ("confirm", "🧑‍💻", "Confirm"),
    ("customize", "✍️", "Customize"),
    ("format", "🧩", "Format"),
    ("validate", "🛡️", "Validate"),
    ("output", "📥", "Resume"),
]

_FLOW_CSS = """
<style>
.flowcanvas{border:1px solid var(--border);border-radius:16px;
  background:var(--canvas-bg);
  background-image:radial-gradient(circle, var(--canvas-dot) 1px, transparent 1px);
  background-size:22px 22px;padding:6px 4px;margin:2px 0 6px;}
.flowwrap{display:flex;align-items:center;justify-content:center;flex-wrap:nowrap;
  overflow-x:auto;padding:18px 10px 42px;}
.fnode{position:relative;width:62px;height:50px;flex:0 0 auto;
  display:flex;align-items:center;justify-content:center;}
.fcirc{width:48px;height:48px;border-radius:13px;display:flex;align-items:center;
  justify-content:center;font-size:20px;background:var(--node-bg);
  border:1.5px solid var(--node-brd);transition:all .35s ease;
  box-shadow:0 2px 8px rgba(0,0,0,.12);}
.flabel{position:absolute;top:54px;left:50%;transform:translateX(-50%);
  font-size:10.5px;font-weight:600;color:var(--node-label);white-space:nowrap;
  letter-spacing:.2px;}
.fnode.active .fcirc{border-color:#22d3ee;border-width:2px;
  box-shadow:0 0 14px rgba(34,211,238,.40);animation:fpulse 1.4s ease-in-out infinite;}
.fnode.active .flabel{color:var(--accent-2);}
.fnode.done .fcirc{border-color:#34d399;background:rgba(52,211,153,.12);
  box-shadow:0 0 8px rgba(52,211,153,.25);}
.fnode.done .flabel{color:var(--good);}
.fnode.human.active .fcirc{border-color:#ec4899;
  box-shadow:0 0 14px rgba(236,72,153,.40);}
.fnode.human.active .flabel{color:#ec4899;}
.fnode.loop .fcirc{animation:fspin 1.1s linear infinite,fpulse 1.4s ease-in-out infinite;}
.fedge{width:30px;height:2.5px;border-radius:3px;background:var(--edge-idle);
  flex:0 0 auto;transition:all .35s ease;}
.fedge.done{background:linear-gradient(90deg,#34d399,#2bb98a);}
.fedge.active{background:linear-gradient(90deg,#22d3ee,#6366f1,#22d3ee);
  background-size:200% 100%;animation:fflow 1s linear infinite;}
@keyframes fpulse{0%,100%{transform:scale(1);}50%{transform:scale(1.09);}}
@keyframes fflow{to{background-position:-200% 0;}}
@keyframes fspin{to{transform:rotate(360deg);}}
</style>
"""

_HUMAN = {"confirm"}


def render_flow(placeholder, done=None, active=None, loop: bool = False) -> None:
    """Render the pipeline graph into a placeholder with the given states."""
    done = set(done or [])
    parts: list[str] = []
    for i, (nid, icon, label) in enumerate(NODES):
        state = "done" if nid in done else ("active" if nid == active else "idle")
        cls = f"fnode {state}"
        if nid in _HUMAN:
            cls += " human"
        if loop and nid == active:
            cls += " loop"
        parts.append(
            f'<div class="{cls}"><div class="fcirc">{icon}</div>'
            f'<div class="flabel">{label}</div></div>'
        )
        if i < len(NODES) - 1:
            nxt = NODES[i + 1][0]
            estate = "done" if nxt in done else ("active" if nxt == active else "idle")
            parts.append(f'<div class="fedge {estate}"></div>')
    html = (_FLOW_CSS + '<div class="flowcanvas"><div class="flowwrap">'
            + "".join(parts) + "</div></div>")
    placeholder.markdown(html, unsafe_allow_html=True)


# Human-readable descriptions for the activity panel (what each node is doing).
STEP_DESC: dict[str, str] = {
    "parse": "Parsing the job description into structured fields…",
    "analyze": "Ranking critical vs. preferred skills for this role…",
    "gap": "Matching your profile against the job (with evidence)…",
    "customize": "Tailoring summary, skills, and bullets to the job…",
    "format": "Rendering ATS-safe PDF & DOCX and fitting to pages…",
    "validate": "Running ATS checks + LLM judge for unsupported claims…",
    "correction": "Issues found — applying corrections…",
}

_ACTIVITY_CSS = """
<style>
.actcard{background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:14px 18px;margin:4px 0 2px;box-shadow:var(--shadow);}
.actrow{display:flex;align-items:center;gap:10px;padding:3px 0;font-size:.93rem;}
.actrow.done{color:var(--good);}
.actrow.now{color:var(--text);font-weight:600;}
.actrow.todo{color:var(--faint);}
.actring{width:17px;height:17px;border-radius:50%;flex:0 0 auto;
  border:3px solid rgba(99,102,241,.22);border-top-color:var(--accent-2);
  border-right-color:var(--accent);animation:aspin .8s linear infinite;}
.actmark{width:18px;flex:0 0 auto;text-align:center;}
.actnote{color:var(--muted);font-size:.82rem;margin-left:28px;margin-top:-2px;}
@keyframes aspin{to{transform:rotate(360deg);}}
</style>
"""


def render_activity(status_ph, done_steps=None, current: str | None = None,
                    note: str = "", title: str = "Working…") -> None:
    """Render a live activity card (what just finished + what's running now)."""
    done_steps = done_steps or []
    rows: list[str] = []
    for label in done_steps:
        rows.append(f'<div class="actrow done"><span class="actmark">✓</span>{label}</div>')
    if current:
        rows.append(
            f'<div class="actrow now"><span class="actring"></span>{current}</div>'
        )
    if note:
        rows.append(f'<div class="actnote">{note}</div>')
    html = (
        _ACTIVITY_CSS
        + f'<div class="actcard"><div class="actrow" '
        f'style="font-weight:700;color:var(--accent-soft);margin-bottom:4px;">⚡ {title}</div>'
        + "".join(rows)
        + "</div>"
    )
    status_ph.markdown(html, unsafe_allow_html=True)


def resting_states(ss) -> tuple[set, str | None]:
    """Compute (done_set, active_node) from current session progress."""
    done: set[str] = set()
    if ss.get("profile"):
        done.add("profile")
    if ss.get("raw_jd"):
        done.add("job")
    if ss.get("structured_jd"):
        done.update(["job", "parse"])
    if ss.get("jd_analysis"):
        done.add("analyze")
    if ss.get("gap_analysis"):
        done.add("gap")
    if ss.get("confirm_done"):
        done.add("confirm")
    if ss.get("gen_result"):
        done.update(["customize", "format", "validate", "output"])

    active = {
        "profile": "profile",
        "job": "job",
        "confirm": "confirm",
        "output": "output",
    }.get(ss.get("stage", "profile"))
    return done, active
