"""Unit tests for RetrievalEngine."""

from __future__ import annotations

from recallx.core.retrieval import RetrievalEngine
from recallx.storage.database import DatabaseManager
from recallx.storage.repositories import MemoryCreate, MemoryRepository


def test_retrieval_search_with_tag_filter(db: DatabaseManager) -> None:
    repo = MemoryRepository(db)
    engine = RetrievalEngine(repo)

    repo.create(
        MemoryCreate(
            content="Configured Redis cache with 300 second TTL for session store",
            project_id="retrieval-proj",
            memory_type="decision",
            tags=["redis", "cache"],
        )
    )
    repo.create(
        MemoryCreate(
            content="Configured Postgres connection pool with max 20 connections",
            project_id="retrieval-proj",
            memory_type="decision",
            tags=["postgres", "database"],
        )
    )

    # Search with tag filter
    results = engine.search(
        query="pool connections",
        project_id="retrieval-proj",
        tags=["database"],
    )

    assert len(results) == 1
    assert "postgres" in results[0]["content"].lower()


def test_retrieval_search_min_relevance(db: DatabaseManager) -> None:
    repo = MemoryRepository(db)
    engine = RetrievalEngine(repo)

    repo.create(
        MemoryCreate(
            content="Exact match query target phrase here for high relevance",
            project_id="retrieval-proj-2",
            importance=0.9,
        )
    )

    results = engine.search(
        query="Exact match query target phrase",
        project_id="retrieval-proj-2",
        min_relevance=0.3,
    )
    assert len(results) >= 1
    assert results[0]["relevance"] >= 0.3


def test_search_hybrid_fallback(db: DatabaseManager) -> None:
    repo = MemoryRepository(db)
    engine = RetrievalEngine(repo)

    repo.create(
        MemoryCreate(
            content="Docker compose multi-container deployment architecture",
            project_id="retrieval-hybrid",
            tags=["docker"],
        )
    )

    results = engine.search_hybrid(
        query="Docker deployment",
        project_id="retrieval-hybrid",
        limit=5,
    )
    assert len(results) >= 1
    assert "docker" in results[0]["content"].lower()
