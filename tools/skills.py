"""Skill hygiene + categorization.

Keeps the resume's Skills section professional: only *atomic* skills (short tool/
tech names — never sentences), de-duplicated, and grouped into sensible categories
for display. Shared by the JD gap step, the resume customizer, the renderers, and
the ATS validator.
"""

from __future__ import annotations

import re

# A real skill is a short noun phrase. These signal a *sentence*, not a skill.
_SENTENCE_LEADS = (
    "experience", "ability", "able", "demonstrated", "strong", "proven",
    "familiar", "familiarity", "hands-on", "handson", "knowledge", "understanding",
    "track record", "prior", "proficiency", "expertise in", "skilled", "exposure",
)
_SENTENCE_MARKERS = (
    ",", ";", " — ", "(e.g", "e.g.", "such as", "including", " across ",
    "with the", "preferred", " etc", ":",
)
_MAX_SKILL_WORDS = 6


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+#.]+", "", (s or "").lower())


def is_atomic_skill(s: str) -> bool:
    """True if `s` looks like a real skill token (not a requirement sentence)."""
    t = (s or "").strip()
    if not t:
        return False
    low = t.lower()
    if len(t.split()) > _MAX_SKILL_WORDS:
        return False
    if any(low.startswith(lead) for lead in _SENTENCE_LEADS):
        return False
    if any(m in low for m in _SENTENCE_MARKERS):
        return False
    return True


def clean_skills(items, cap: int = 30) -> list[str]:
    """Keep only atomic skills; drop duplicates; preserve order; cap length."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in items or []:
        s = (raw or "").strip().strip("•-·").strip()
        if not is_atomic_skill(s):
            continue
        key = _norm(s)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= cap:
            break
    return out


# Category -> normalized-substring matchers.
_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Languages": ("python", "sql", "scala", "java", "javascript", "typescript",
                  "golang", "bash", "shell", "rlang", "cplusplus", "csharp"),
    "Data & Cloud": ("spark", "pyspark", "hadoop", "kafka", "snowflake", "iceberg",
                     "databricks", "airflow", "hive", "etl", "elt", "warehouse",
                     "lakehouse", "azure", "aws", "gcp", "redshift", "bigquery",
                     "synapse", "datalake", "adf", "adls", "cassandra", "hana",
                     "singlestore", "dbt", "datamodeling", "datapipelines", "database"),
    "AI & ML": ("langchain", "langgraph", "llamaindex", "rag", "retrievalaugmented",
                "embedding", "vector", "llm", "genai", "generativeai", "pytorch",
                "tensorflow", "scikit", "sklearn", "nlp", "machinelearning",
                "deeplearning", "promptengineering", "agent", "agentic", "chatbot"),
    "BI & Visualization": ("tableau", "powerbi", "looker", "matplotlib", "seaborn",
                           "dashboard", "eda", "exploratorydata", "visualization"),
    "Web & APIs": ("react", "fastapi", "streamlit", "flask", "django", "nodejs",
                   "node", "rest", "graphql", "html", "css", "fullstack"),
    "Tools & Practices": ("git", "github", "gitlab", "jira", "agile", "scrum",
                          "docker", "kubernetes", "cicd", "linux", "excel",
                          "workflowautomation", "performanceoptimization"),
}
# Match specific categories BEFORE Languages so compound terms like
# "Azure SQL Database" resolve to Data & Cloud (not Languages via the "sql" match).
# Works for any skill/role — not tuned to one company.
_MATCH_ORDER = ["Data & Cloud", "AI & ML", "BI & Visualization", "Web & APIs",
                "Tools & Practices", "Languages"]
# Conventional display order (Languages first).
_DISPLAY_ORDER = ["Languages", "Data & Cloud", "AI & ML", "BI & Visualization",
                  "Web & APIs", "Tools & Practices", "Other"]


def categorize_skills(items) -> list[tuple[str, list[str]]]:
    """Group atomic skills into display categories (skipping empty ones)."""
    skills = clean_skills(items)
    buckets: dict[str, list[str]] = {label: [] for label in _DISPLAY_ORDER}
    for s in skills:
        key = _norm(s)
        placed = next((label for label in _MATCH_ORDER
                       if any(m in key for m in _CATEGORIES[label])), "Other")
        buckets[placed].append(s)
    return [(label, buckets[label]) for label in _DISPLAY_ORDER if buckets[label]]
