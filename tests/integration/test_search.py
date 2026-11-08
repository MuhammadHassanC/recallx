"""Integration tests for FTS5 search and MemoryEngine.recall retrieval."""
from __future__ import annotations

from typing import Any

from recallx.core.memory import MemoryEngine
from recallx.storage.repositories import MemoryRepository


def test_fts_search_finds_matching(memory_repo: MemoryRepository, engine: MemoryEngine) -> None:
    """Ensure FTS search returns records matching query terms."""
    engine.remember(
        content="Configured PostgreSQL with connection pooling using pgBouncer.",
        project_id="search-proj",
        memory_type="decision",
        tags=["database", "postgres"],
    )

    results = memory_repo.search_fts("PostgreSQL pgBouncer", project_id="search-proj")
    assert len(results) >= 1
    assert "pgbouncer" in results[0]["content"].lower()


def test_fts_search_no_results(memory_repo: MemoryRepository, engine: MemoryEngine) -> None:
    """Ensure FTS search returns an empty list when no memories match."""
    engine.remember(
        content="Frontend built with React 18 and Tailwind CSS",
        project_id="search-proj",
    )

    results = memory_repo.search_fts("quantum computing cryptography", project_id="search-proj")
    assert len(results) == 0


def test_fts_search_project_filter(memory_repo: MemoryRepository, engine: MemoryEngine) -> None:
    """Ensure FTS search respects project_id filtering."""
    engine.remember(content="Common utility functions in Python", project_id="proj-1")
    engine.remember(content="Common utility functions in Python", project_id="proj-2")

    res_1 = memory_repo.search_fts("utility functions", project_id="proj-1")
    res_2 = memory_repo.search_fts("utility functions", project_id="proj-2")

    assert len(res_1) == 1
    assert res_1[0]["project_id"] == "proj-1"
    assert len(res_2) == 1
    assert res_2[0]["project_id"] == "proj-2"


def test_fts_search_type_filter(memory_repo: MemoryRepository, engine: MemoryEngine) -> None:
    """Ensure FTS search respects memory_type filtering."""
    engine.remember(
        content="Chose SQLAlchemy 2.0 ORM over raw SQLite queries",
        project_id="type-proj",
        memory_type="decision",
    )
    engine.remember(
        content="SQLAlchemy connection leak bug was fixed by wrapping sessions in contextmanager",
        project_id="type-proj",
        memory_type="bug_solution",
    )

    decisions = memory_repo.search_fts("SQLAlchemy", project_id="type-proj", memory_type="decision")
    assert len(decisions) == 1
    assert decisions[0]["memory_type"] == "decision"

    bugs = memory_repo.search_fts("SQLAlchemy", project_id="type-proj", memory_type="bug_solution")
    assert len(bugs) == 1
    assert bugs[0]["memory_type"] == "bug_solution"


def test_search_special_characters_handled(memory_repo: MemoryRepository, engine: MemoryEngine) -> None:
    """Ensure search queries containing punctuation, quotes, or special characters execute safely."""
    engine.remember(
        content="Handled error: HTTP 500 'Internal Server Error' in /api/v1/users",
        project_id="special-proj",
    )

    tricky_queries = [
        "error: HTTP 500",
        'HTTP "500"',
        "/api/v1/users",
        "(500) OR [error]",
        "***???@@@###",
    ]

    for q in tricky_queries:
        # Must not raise an exception / syntax error in SQLite FTS5
        results = memory_repo.search_fts(q, project_id="special-proj")
        assert isinstance(results, list)


def test_recall_returns_ranked_results(engine: MemoryEngine, sample_memories: list[dict[str, Any]]) -> None:
    """Ensure engine.recall returns memories ordered by relevance score."""
    for item in sample_memories:
        engine.remember(
            content=item["content"],
            project_id=item["project_id"],
            memory_type=item["memory_type"],
            tags=item["tags"],
            importance=item["importance"],
        )

    results = engine.recall(
        query="JWT access tokens and refresh authentication",
        project_id="test-project",
    )

    assert len(results) >= 1
    assert "relevance" in results[0]
    assert results[0]["relevance"] > 0.0

    # Highest ranked should be the JWT auth memory
    assert "jwt" in results[0]["content"].lower()

    # Results should be descending by relevance
    for i in range(len(results) - 1):
        assert results[i]["relevance"] >= results[i + 1]["relevance"]


def test_recall_respects_limit(engine: MemoryEngine) -> None:
    """Ensure recall respects the limit parameter."""
    for i in range(15):
        engine.remember(
            content=f"Docker container deployment configuration note {i}",
            project_id="limit-proj",
        )

    results = engine.recall(query="Docker container", project_id="limit-proj", limit=5)
    assert len(results) <= 5


def test_recall_project_filter(engine: MemoryEngine) -> None:
    """Ensure recall only returns results from the requested project."""
    engine.remember(content="Use Redis cache in Alpha", project_id="proj-a")
    engine.remember(content="Use Redis cache in Beta", project_id="proj-b")

    results_a = engine.recall(query="Redis cache", project_id="proj-a")
    assert all(r["project_id"] == "proj-a" for r in results_a)

    results_b = engine.recall(query="Redis cache", project_id="proj-b")
    assert all(r["project_id"] == "proj-b" for r in results_b)
