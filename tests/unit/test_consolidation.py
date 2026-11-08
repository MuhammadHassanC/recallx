"""Unit tests for ConsolidationEngine."""

from __future__ import annotations

import pytest

from recallx.core.consolidation import ConsolidationEngine
from recallx.storage.database import DatabaseManager
from recallx.storage.repositories import MemoryCreate, MemoryRepository


def test_find_consolidation_candidates(db: DatabaseManager) -> None:
    repo = MemoryRepository(db)
    cons = ConsolidationEngine(repo)

    repo.create(
        MemoryCreate(
            content="Configured Redis cache with 10 minute eviction policy",
            project_id="cons-proj",
            memory_type="decision",
            tags=["redis", "cache"],
        )
    )
    repo.create(
        MemoryCreate(
            content="Configured Redis cluster replica nodes for failover",
            project_id="cons-proj",
            memory_type="decision",
            tags=["redis", "cache"],
        )
    )

    candidates = cons.find_consolidation_candidates("cons-proj", similarity_threshold=0.3)
    assert len(candidates) >= 1
    assert len(candidates[0]) >= 2


def test_consolidate_memories(db: DatabaseManager) -> None:
    repo = MemoryRepository(db)
    cons = ConsolidationEngine(repo)

    m1 = repo.create(
        MemoryCreate(
            content="Use SQLite WAL mode for fast writes",
            project_id="cons-proj-2",
            memory_type="decision",
            tags=["sqlite", "database"],
            importance=0.7,
        )
    )
    m2 = repo.create(
        MemoryCreate(
            content="Use SQLite PRAGMA busy_timeout=5000 to avoid lock timeouts",
            project_id="cons-proj-2",
            memory_type="decision",
            tags=["sqlite", "pragmas"],
            importance=0.8,
        )
    )

    consolidated = cons.consolidate(
        memory_ids=[m1["id"], m2["id"]],
        new_content="Standardized SQLite configuration: WAL mode with busy_timeout=5000ms.",
        project_id="cons-proj-2",
    )

    assert consolidated["id"] != m1["id"]
    assert consolidated["id"] != m2["id"]
    assert consolidated["importance"] == 0.8
    assert "sqlite" in consolidated["tags"]
    assert "database" in consolidated["tags"]
    assert "pragmas" in consolidated["tags"]
    assert "consolidated_from" in consolidated["metadata"]
    assert m1["id"] in consolidated["metadata"]["consolidated_from"]

    # Verify original memories were archived (not deleted)
    old_m1 = repo.get(m1["id"])
    old_m2 = repo.get(m2["id"])
    assert old_m1 is not None and old_m1["is_archived"] is True
    assert old_m2 is not None and old_m2["is_archived"] is True


def test_consolidate_invalid_inputs(db: DatabaseManager) -> None:
    repo = MemoryRepository(db)
    cons = ConsolidationEngine(repo)

    with pytest.raises(ValueError):
        cons.consolidate(memory_ids=[], new_content="something", project_id="cons-proj")

    with pytest.raises(ValueError):
        cons.consolidate(memory_ids=["dummy"], new_content="", project_id="cons-proj")
