"""Input routing logic (spec §8, Agent 1 — Input Router).

Pure deterministic Python. Decides how the workflow should proceed based on
which inputs the user supplied. Kept separate so the LangGraph wiring (added in
a later phase) can import these decisions directly.
"""

from __future__ import annotations

from typing import Literal

InputRoute = Literal["extract", "parse", "error"]


def route_input(job_url: str | None, pasted_jd: str | None) -> InputRoute:
    """Decide the next step from the provided inputs.

    - A pasted JD is used directly (no scraping needed) -> "parse".
    - Otherwise a URL triggers extraction -> "extract".
    - Neither -> "error".

    A pasted JD takes precedence: if the user bothered to paste text, trust it.
    """
    if pasted_jd and pasted_jd.strip():
        return "parse"
    if job_url and job_url.strip():
        return "extract"
    return "error"
