"""Animated "agent graph" visuals (hero + progress strip).

render_hero() draws the signature glowing hub-and-nodes graphic (self-contained
HTML/CSS/SVG in an iframe). render_pipeline_strip() shows a compact, inline
status strip of the workflow stages that lights up as the user progresses.
"""

from __future__ import annotations

import streamlit as st
from streamlit.components.v1 import html as _html

# Node color by state.
_C = {"done": "#34d399", "active": "#22d3ee", "todo": "#5b6191"}


def _node(x, y, icon, label, state):
    color = _C.get(state, _C["todo"])
    pulse = "animation:pulse 1.6s ease-in-out infinite;" if state == "active" else ""
    return f"""
    <div class="node" style="left:{x}px; top:{y}px; border-color:{color};
        box-shadow:0 0 22px {color}66, inset 0 0 12px {color}33; {pulse}">
      <div class="ico">{icon}</div>
    </div>
    <div class="nlabel" style="left:{x-30}px; top:{y+78}px; color:#cdd2f0;">{label}</div>
    """


def render_hero(states: dict | None = None, height: int = 460) -> None:
    """Render the glowing agent-pipeline hero graphic."""
    s = states or {}

    def st_of(k):
        return s.get(k, "todo")

    nodes = (
        _node(60, 110, "📄", "Master&nbsp;Profile", st_of("profile"))
        + _node(60, 300, "🧾", "Job&nbsp;Description", st_of("job"))
        + _node(820, 70, "📑", "ATS&nbsp;PDF", st_of("pdf"))
        + _node(820, 210, "📝", "Editable&nbsp;DOCX", st_of("docx"))
        + _node(820, 350, "✅", "Validation", st_of("validation"))
    )

    html = f"""
    <div class="stage">
      <svg class="wires" viewBox="0 0 960 460" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="g1" x1="0" x2="1">
            <stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#a855f7"/>
          </linearGradient>
          <linearGradient id="g2" x1="0" x2="1">
            <stop offset="0" stop-color="#a855f7"/><stop offset="1" stop-color="#ec4899"/>
          </linearGradient>
        </defs>
        <path class="edge" d="M150,150 C300,150 330,230 450,230" stroke="url(#g1)"/>
        <path class="edge" d="M150,340 C300,340 330,250 450,250" stroke="url(#g1)"/>
        <path class="edge" d="M620,230 C740,230 760,120 900,120" stroke="url(#g2)"/>
        <path class="edge" d="M630,240 C760,240 770,250 900,255" stroke="url(#g2)"/>
        <path class="edge" d="M620,255 C740,255 760,380 900,385" stroke="url(#g2)"/>
      </svg>

      <div class="hub">
        <div class="hex"></div>
        <div class="hub-core">
          <div class="hub-t">AI&nbsp;Resume</div>
          <div class="hub-t2">AGENT</div>
        </div>
      </div>
      {nodes}
    </div>

    <style>
      .stage {{ position:relative; width:960px; height:460px; margin:0 auto;
        font-family:'Inter',system-ui,sans-serif; }}
      .wires {{ position:absolute; inset:0; width:100%; height:100%; }}
      .edge {{ fill:none; stroke-width:2.4; stroke-linecap:round;
        stroke-dasharray:10 14; filter:drop-shadow(0 0 6px rgba(168,85,247,.6));
        animation: flow 1.2s linear infinite; opacity:.9; }}
      @keyframes flow {{ to {{ stroke-dashoffset:-48; }} }}
      .node {{ position:absolute; width:62px; height:62px; border-radius:50%;
        background:rgba(12,16,40,.85); border:2.5px solid #5b6191;
        display:flex; align-items:center; justify-content:center; }}
      .ico {{ font-size:26px; }}
      .nlabel {{ position:absolute; width:120px; text-align:center;
        font-size:12.5px; font-weight:600; }}
      @keyframes pulse {{ 0%,100%{{transform:scale(1);}} 50%{{transform:scale(1.08);}} }}
      .hub {{ position:absolute; left:430px; top:160px; width:150px; height:150px; }}
      .hex {{ position:absolute; inset:0;
        background:linear-gradient(135deg, rgba(34,211,238,.35), rgba(168,85,247,.45));
        clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);
        box-shadow:0 0 50px rgba(168,85,247,.6);
        animation: breathe 3s ease-in-out infinite; }}
      .hex::before {{ content:''; position:absolute; inset:6px;
        background:rgba(8,11,30,.92);
        clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%); }}
      @keyframes breathe {{ 0%,100%{{filter:drop-shadow(0 0 16px rgba(34,211,238,.5));}}
        50%{{filter:drop-shadow(0 0 34px rgba(168,85,247,.85));}} }}
      .hub-core {{ position:absolute; inset:0; display:flex; flex-direction:column;
        align-items:center; justify-content:center; z-index:2; }}
      .hub-t {{ font-family:'Orbitron',sans-serif; font-weight:700; color:#eaf2ff;
        font-size:16px; text-shadow:0 0 12px rgba(34,211,238,.8); }}
      .hub-t2 {{ font-family:'Orbitron',sans-serif; font-weight:800; font-size:20px;
        letter-spacing:3px;
        background:linear-gradient(90deg,#22d3ee,#ec4899);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
      body {{ margin:0; background:transparent; }}
    </style>
    """
    _html(html, height=height)


def render_pipeline_strip(states: dict) -> None:
    """Inline compact status strip of the workflow stages."""
    stages = [
        ("Profile", states.get("profile", "todo")),
        ("Job", states.get("job", "todo")),
        ("Analyze", states.get("analyze", "todo")),
        ("Fit", states.get("fit", "todo")),
        ("Generate", states.get("generate", "todo")),
        ("Validate", states.get("validation", "todo")),
    ]
    parts = []
    for i, (label, stt) in enumerate(stages):
        color = _C.get(stt, _C["todo"])
        dot = "●" if stt != "todo" else "○"
        parts.append(
            f'<span style="color:{color}; font-weight:700;">{dot} {label}</span>'
        )
        if i < len(stages) - 1:
            parts.append('<span style="color:#3a406e;">———</span>')
    strip = (
        '<div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap; '
        'padding:10px 14px; border-radius:12px; '
        'background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.08); '
        'font-size:.86rem;">' + " ".join(parts) + "</div>"
    )
    st.markdown(strip, unsafe_allow_html=True)
