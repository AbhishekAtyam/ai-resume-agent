"""Unit tests for tools/skills.py (atomic filter, cleaning, categorization)."""

from __future__ import annotations

from tools.skills import categorize_skills, clean_skills, is_atomic_skill


def test_is_atomic_skill_accepts_real_skills():
    assert is_atomic_skill("Python")
    assert is_atomic_skill("Apache Spark")
    assert is_atomic_skill("RAG")
    assert is_atomic_skill("Azure Data Lake Storage Gen2")  # 6 words, still a tool


def test_is_atomic_skill_rejects_sentences():
    assert not is_atomic_skill(
        "Experience building multi-agent systems that coordinate retrieval and action")
    assert not is_atomic_skill("Ability to translate business problems into designs")
    assert not is_atomic_skill("AWS, GCP, or Azure — AWS preferred")  # commas/dash
    assert not is_atomic_skill("ML frameworks such as PyTorch or TensorFlow")  # 'such as'
    assert not is_atomic_skill("")


def test_clean_skills_drops_sentences_and_dupes():
    raw = [
        "Python", "python", "SQL",
        "Experience with cloud platforms such as AWS, GCP, or Azure",
        "Apache Spark", "Apache Spark",
    ]
    cleaned = clean_skills(raw)
    assert "Python" in cleaned
    assert cleaned.count("Python") == 1               # de-duplicated
    assert "Apache Spark" in cleaned
    assert all(is_atomic_skill(s) for s in cleaned)   # no sentences survive
    assert not any("Experience with cloud" in s for s in cleaned)


def test_clean_skills_caps_length():
    assert len(clean_skills([f"Skill{i}" for i in range(50)], cap=20)) == 20


def test_categorize_skills_groups_correctly():
    groups = dict(categorize_skills(
        ["Python", "SQL", "Spark", "Snowflake", "LangChain", "RAG", "Tableau",
         "FastAPI", "Git", "SomeNicheThing"]))
    assert "Python" in groups.get("Languages", [])
    assert "Snowflake" in groups.get("Data & Cloud", [])
    assert "LangChain" in groups.get("AI & ML", [])
    assert "Tableau" in groups.get("BI & Visualization", [])
    assert "FastAPI" in groups.get("Web & APIs", [])
    assert "Git" in groups.get("Tools & Practices", [])
    assert "SomeNicheThing" in groups.get("Other", [])
