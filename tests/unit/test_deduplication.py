"""Unit tests for DeduplicationEngine."""
from __future__ import annotations

import pytest

from recallx.core.deduplication import DeduplicationEngine
from recallx.storage.database import DatabaseManager
from recallx.storage.repositories import MemoryCreate, MemoryRepository


def test_is_duplicate_exact_match(db: DatabaseManager) -> None:
    """Ensure exact duplicate matches are identified by normalized content hash."""
    repo = MemoryRepository(db)
    dedup = DeduplicationEngine(repo)

    content = "Using Pytest for automated unit and integration testing"
    repo.create(
        MemoryCreate(
            content=content,
            project_id="dedup-proj",
        )
    )

    dup = dedup.is_duplicate(content, project_id="dedup-proj")
    assert dup is not None
    assert dup["project_id"] == "dedup-proj"

    # Also check case and space-insensitive match
    dup_normalized = dedup.is_duplicate(
        "  using   pytest for   automated unit and integration testing \n",
        project_id="dedup-proj",
    )
    assert dup_normalized is not None


def test_is_duplicate_no_match(db: DatabaseManager) -> None:
    """Ensure distinct content does not register as a duplicate."""
    repo = MemoryRepository(db)
    dedup = DeduplicationEngine(repo)

    repo.create(
        MemoryCreate(
            content="Using Pytest for automated unit testing",
            project_id="dedup-proj",
        )
    )

    not_dup = dedup.is_duplicate("Completely different content about Docker", project_id="dedup-proj")
    assert not_dup is None


def test_find_similar_above_threshold(db: DatabaseManager) -> None:
    """Ensure similar content above the similarity threshold is detected."""
    repo = MemoryRepository(db)
    dedup = DeduplicationEngine(repo)

    content1 = "Always use absolute imports in python backend code"
    repo.create(
        MemoryCreate(
            content=content1,
            project_id="dedup-sim-proj",
        )
    )

    content_similar = "Always use absolute import paths in python backend code"
    similar = dedup.find_similar(content_similar, project_id="dedup-sim-proj", threshold=0.7)

    assert len(similar) >= 1
    assert similar[0]["similarity"] >= 0.7


def test_find_similar_below_threshold(db: DatabaseManager) -> None:
    """Ensure dissimilar content below threshold is not returned."""
    repo = MemoryRepository(db)
    dedup = DeduplicationEngine(repo)

    content1 = "Always use absolute imports in python backend code"
    repo.create(
        MemoryCreate(
            content=content1,
            project_id="dedup-sim-proj",
        )
    )

    unrelated = "Deploy the Kubernetes helm chart to the staging cluster"
    similar = dedup.find_similar(unrelated, project_id="dedup-sim-proj", threshold=0.8)

    assert len(similar) == 0


def test_merge_duplicates(db: DatabaseManager) -> None:
    """Ensure duplicate memories can be merged into a single consolidated record."""
    repo = MemoryRepository(db)
    dedup = DeduplicationEngine(repo)

    m1 = repo.create(
        MemoryCreate(
            content="Standardize on Ruff for linting and formatting",
            project_id="merge-proj",
            tags=["linting", "python"],
            importance=0.6,
        )
    )
    m2 = repo.create(
        MemoryCreate(
            content="Standardize on Ruff for code linting and formatting rules",
            project_id="merge-proj",
            tags=["formatting", "tooling"],
            importance=0.9,
        )
    )

    merged = dedup.merge_duplicates(memory_ids=[m2["id"]], keep_id=m1["id"])
    assert merged["id"] == m1["id"]
    assert merged["importance"] == 0.9  # kept higher importance
    assert "linting" in merged["tags"]
    assert "formatting" in merged["tags"]
    assert "tooling" in merged["tags"]

    # Verify m2 was deleted
    assert repo.get(m2["id"]) is None


def test_merge_duplicates_nonexistent_keep_id(db: DatabaseManager) -> None:
    """Ensure merging with a nonexistent keep_id raises ValueError."""
    repo = MemoryRepository(db)
    dedup = DeduplicationEngine(repo)

    with pytest.raises(ValueError):
        dedup.merge_duplicates(memory_ids=["dummy"], keep_id="nonexistent-id")
