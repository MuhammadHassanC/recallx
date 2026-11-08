"""Unit tests for RelevanceRanker and ranking algorithms."""
from __future__ import annotations

from datetime import datetime, timedelta

from recallx.core.ranking import RelevanceRanker, rank

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone

    UTC = timezone.utc  # type: ignore[attr-defined]


def test_text_relevance_exact_match() -> None:
    ranker = RelevanceRanker()
    score = ranker._text_relevance("Use PostgreSQL for storage", "PostgreSQL")
    assert score == 1.0


def test_text_relevance_partial_overlap() -> None:
    ranker = RelevanceRanker()
    score = ranker._text_relevance("Use PostgreSQL database for backend API", "PostgreSQL Redis")
    assert 0.3 <= score <= 0.8


def test_text_relevance_empty_query() -> None:
    ranker = RelevanceRanker()
    score = ranker._text_relevance("Some content", "")
    assert score == 0.5


def test_recency_score_decay() -> None:
    ranker = RelevanceRanker(recency_half_life_days=30.0)
    now = datetime.now(UTC)

    fresh_score = ranker._recency_score(now.isoformat(), now.isoformat())
    old_score = ranker._recency_score((now - timedelta(days=30)).isoformat(), now.isoformat())
    very_old_score = ranker._recency_score((now - timedelta(days=90)).isoformat(), now.isoformat())

    assert fresh_score > 0.95
    assert 0.45 <= old_score <= 0.55  # ~50% at 30 days
    assert very_old_score < 0.2


def test_type_boost_intent_matching() -> None:
    ranker = RelevanceRanker()

    why_decision = ranker._type_boost("decision", "Why did we choose Postgres?")
    why_bug = ranker._type_boost("bug_solution", "Why did we choose Postgres?")
    assert why_decision > why_bug

    fix_bug = ranker._type_boost("bug_solution", "Fix CORS error and crash")
    fix_pref = ranker._type_boost("preference", "Fix CORS error and crash")
    assert fix_bug > fix_pref


def test_rank_returns_sorted_by_relevance() -> None:
    """Ensure rank() returns memories sorted in descending order of relevance."""
    memories = [
        {"id": "1", "content": "Unrelated note about deployment", "importance": 0.2, "memory_type": "session"},
        {"id": "2", "content": "PostgreSQL database connection pooling", "importance": 0.9, "memory_type": "decision"},
        {"id": "3", "content": "Database migration script for PostgreSQL", "importance": 0.5, "memory_type": "project"},
    ]
    ranked = rank(memories, "PostgreSQL database")

    assert len(ranked) == 3
    assert ranked[0]["id"] in ("2", "3")
    for i in range(len(ranked) - 1):
        assert ranked[i]["relevance"] >= ranked[i + 1]["relevance"]


def test_rank_text_relevance_exact_match_high() -> None:
    """Ensure exact text matches receive significantly higher scores."""
    ranker = RelevanceRanker()
    memories = [
        {"id": "exact", "content": "JWT authentication with refresh tokens", "importance": 0.5, "memory_type": "decision"},
        {"id": "partial", "content": "Authentication mechanism discussion", "importance": 0.5, "memory_type": "decision"},
        {"id": "none", "content": "CSS flexbox alignment issues in navbar", "importance": 0.5, "memory_type": "decision"},
    ]
    results = ranker.rank(memories, "JWT authentication")
    assert results[0]["id"] == "exact"
    assert results[0]["relevance"] > results[1]["relevance"]
    assert results[1]["relevance"] > results[2]["relevance"]


def test_rank_importance_affects_score() -> None:
    """Ensure higher importance results in a higher score when text match is identical."""
    memories = [
        {"id": "low", "content": "Standard logging configuration", "importance": 0.2, "memory_type": "preference"},
        {"id": "high", "content": "Standard logging configuration", "importance": 0.9, "memory_type": "preference"},
    ]
    results = rank(memories, "logging configuration")
    assert results[0]["id"] == "high"
    assert results[0]["relevance"] > results[1]["relevance"]


def test_rank_recency_affects_score() -> None:
    """Ensure recent memories score higher than older memories with identical content."""
    now = datetime.now(UTC)
    old_time = (now - timedelta(days=90)).isoformat()
    new_time = now.isoformat()

    memories = [
        {
            "id": "old",
            "content": "Redis caching layer configuration",
            "importance": 0.5,
            "memory_type": "project",
            "created_at": old_time,
            "accessed_at": old_time,
        },
        {
            "id": "new",
            "content": "Redis caching layer configuration",
            "importance": 0.5,
            "memory_type": "project",
            "created_at": new_time,
            "accessed_at": new_time,
        },
    ]
    results = rank(memories, "Redis caching")
    assert results[0]["id"] == "new"
    assert results[0]["relevance"] > results[1]["relevance"]


def test_rank_type_boost_for_error_queries() -> None:
    """Ensure bug_solution memories receive boost for error/fix queries."""
    memories = [
        {"id": "session", "content": "Database timeout connection handling", "importance": 0.5, "memory_type": "session"},
        {"id": "bug", "content": "Database timeout connection handling", "importance": 0.5, "memory_type": "bug_solution"},
    ]
    results = rank(memories, "fix database timeout error bug")
    assert results[0]["id"] == "bug"
    assert results[0]["relevance"] > results[1]["relevance"]


def test_rank_empty_memories_returns_empty() -> None:
    """Ensure ranking an empty memory list returns an empty list."""
    assert rank([], "any search query") == []
