"""Unit tests for rule-based MemoryExtractor."""
from __future__ import annotations

from recallx.core.extraction import MemoryExtractor


def test_extract_decision_from_text() -> None:
    """Ensure architectural and engineering decisions are extracted from text."""
    extractor = MemoryExtractor()
    text = (
        "In today's sync, we decided to use SQLAlchemy 2.0 with type annotations. "
        "Also, we chose PostgreSQL over MongoDB for structured relational consistency."
    )
    results = extractor.extract(text, project_id="test-proj")
    decisions = [m for m in results if m["memory_type"] == "decision"]

    assert len(decisions) >= 1
    assert any("sqlalchemy" in d["content"].lower() or "postgresql" in d["content"].lower() for d in decisions)
    for d in decisions:
        assert d["project_id"] == "test-proj"
        assert d["importance"] >= 0.7
        assert d["confidence"] >= 0.8


def test_extract_bug_solution_from_text() -> None:
    """Ensure resolved bugs and root cause solutions are extracted."""
    extractor = MemoryExtractor()
    text = (
        "Fixed bug where SQLite database locked during concurrent agent memory writes. "
        "Root cause was missing busy_timeout setting in connection pragmas."
    )
    results = extractor.extract(text, project_id="test-proj")
    bugs = [m for m in results if m["memory_type"] == "bug_solution"]

    assert len(bugs) >= 1
    assert any("sqlite" in b["content"].lower() or "busy_timeout" in b["content"].lower() for b in bugs)


def test_extract_preference_from_text() -> None:
    """Ensure coding preferences and guidelines are extracted."""
    extractor = MemoryExtractor()
    text = (
        "Always use absolute imports in python code. "
        "Never use print statements for logging; standard is to use structured loggers."
    )
    results = extractor.extract(text, project_id="test-proj")
    prefs = [m for m in results if m["memory_type"] == "preference"]

    assert len(prefs) >= 1
    assert any("absolute imports" in p["content"].lower() or "logging" in p["content"].lower() for p in prefs)


def test_extract_project_info_from_text() -> None:
    """Ensure tech stack and project architecture information are extracted."""
    extractor = MemoryExtractor()
    text = (
        "Tech stack: FastAPI backend with SQLite storage and Next.js frontend. "
        "Uses Pydantic for data validation across all modules."
    )
    results = extractor.extract(text, project_id="test-proj")
    proj_memories = [m for m in results if m["memory_type"] == "project"]

    assert len(proj_memories) >= 1
    assert any("fastapi" in p["content"].lower() or "pydantic" in p["content"].lower() for p in proj_memories)


def test_extract_empty_text_returns_empty() -> None:
    """Ensure empty or whitespace-only text returns an empty list."""
    extractor = MemoryExtractor()
    assert extractor.extract("", project_id="test-proj") == []
    assert extractor.extract("   \n\t   ", project_id="test-proj") == []


def test_extract_no_patterns_returns_empty() -> None:
    """Ensure text without any matching pattern returns an empty list."""
    extractor = MemoryExtractor()
    ordinary_text = "The weather was cloudy and we went for a short afternoon walk."
    assert extractor.extract(ordinary_text, project_id="test-proj") == []


def test_importance_assignment() -> None:
    """Ensure importance scoring applies heuristics correctly."""
    extractor = MemoryExtractor()
    dec_score = extractor._assign_importance("decision", "chose Postgres over SQLite")
    assert dec_score >= 0.8

    crit_score = extractor._assign_importance("decision", "critical security auth credential fix")
    assert crit_score > dec_score
    assert crit_score <= 1.0
