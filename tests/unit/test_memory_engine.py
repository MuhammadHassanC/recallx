"""Unit tests for central MemoryEngine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from recallx.core.memory import MemoryEngine
from recallx.storage.database import DatabaseManager


def test_remember_and_get(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    mem = engine.remember(
        content="Decided to use SQLite with WAL mode for local-first embedded storage.",
        project_id="test-engine-proj",
        memory_type="decision",
        tags=["sqlite", "wal"],
        source="test",
        importance=0.85,
    )

    assert mem["id"] is not None
    assert mem["project_id"] == "test-engine-proj"
    assert mem["memory_type"] == "decision"
    assert mem["importance"] == 0.85
    assert "sqlite" in mem["tags"]

    retrieved = engine.get(mem["id"])
    assert retrieved is not None
    assert retrieved["id"] == mem["id"]


def test_remember_redacts_secrets(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    # Content containing high-entropy GitHub PAT and AWS credentials
    raw_content = "Configured deployment token ghp_123456789012345678901234567890123456 for CI."
    mem = engine.remember(
        content=raw_content,
        project_id="secret-proj",
    )

    assert "ghp_" not in mem["content"]
    assert "[REDACTED]" in mem["content"]


def test_remember_deduplication(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    content = "Single deterministic guideline for python imports."
    mem1 = engine.remember(content=content, project_id="dedup-engine")
    mem2 = engine.remember(content=content, project_id="dedup-engine")

    assert mem1["id"] == mem2["id"]
    stats = engine.get_stats(project_id="dedup-engine")
    assert stats["total"] == 1


def test_recall_and_ranking(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    engine.remember(
        content="Configured Redis cache with 60s TTL",
        project_id="recall-proj",
        tags=["redis", "cache"],
    )
    engine.remember(
        content="Chose PostgreSQL for relational data persistence",
        project_id="recall-proj",
        memory_type="decision",
        tags=["postgres", "database"],
        importance=0.9,
    )

    results = engine.recall(
        query="Why PostgreSQL relational database?",
        project_id="recall-proj",
        limit=5,
    )

    assert len(results) >= 1
    assert "postgres" in results[0]["content"].lower()
    assert "relevance" in results[0]


def test_update_and_forget(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    mem = engine.remember(
        content="Initial draft of architecture notes.",
        project_id="mod-proj",
    )

    updated = engine.update(
        mem["id"],
        content="Revised finalized architecture notes using event sourcing.",
        importance=0.95,
        tags=["architecture", "events"],
    )

    assert updated is not None
    assert "event sourcing" in updated["content"]
    assert updated["importance"] == 0.95
    assert "events" in updated["tags"]

    # Verify forget deletes memory
    assert engine.forget(mem["id"]) is True
    assert engine.get(mem["id"]) is None
    assert engine.forget("nonexistent") is False


def test_pin_unpin_archive(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    mem = engine.remember(content="Core rule: All tests must pass.", project_id="pin-proj")

    assert engine.pin(mem["id"]) is True
    pinned = engine.get(mem["id"])
    assert pinned is not None and pinned["is_pinned"] is True

    assert engine.unpin(mem["id"]) is True
    unpinned = engine.get(mem["id"])
    assert unpinned is not None and unpinned["is_pinned"] is False

    assert engine.archive(mem["id"]) is True
    archived = engine.get(mem["id"])
    assert archived is not None and archived["is_archived"] is True


def test_list_memories_filters(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    m1 = engine.remember(content="Rule 1", project_id="list-proj", memory_type="preference")
    m2 = engine.remember(content="Decision 1", project_id="list-proj", memory_type="decision")
    engine.pin(m1["id"])

    # Pinned only
    pinned = engine.list_memories(project_id="list-proj", pinned_only=True)
    assert len(pinned) == 1
    assert pinned[0]["id"] == m1["id"]

    # By memory type
    decisions = engine.list_memories(project_id="list-proj", memory_type="decision")
    assert len(decisions) == 1
    assert decisions[0]["id"] == m2["id"]


def test_session_summary(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)

    mem = engine.save_session_summary(
        project_id="sess-proj",
        summary="Completed database abstraction and FTS indexing.",
        tasks_completed=["setup db", "fts virtual table"],
        tasks_pending=["add backup cli"],
        issues=["locked database on high concurrency"],
    )

    assert mem["memory_type"] == "session"
    assert "fts virtual table" in mem["metadata"]["tasks_completed"]
    assert "locked database" in mem["metadata"]["issues"][0]


def test_export_and_import_memories(db: DatabaseManager, tmp_path: Path) -> None:
    engine = MemoryEngine(db)

    engine.remember(content="Memory for export 1", project_id="exp-proj", tags=["tag1"])
    engine.remember(content="Memory for export 2", project_id="exp-proj", tags=["tag2"])

    out_file = tmp_path / "export.json"
    json_str = engine.export_memories(project_id="exp-proj", output_path=out_file)

    assert out_file.exists()
    assert "Memory for export 1" in json_str

    # Import into another project
    stats = engine.import_memories(json_str, project_id="imp-proj")
    assert stats["imported"] == 2
    assert stats["skipped"] == 0
    assert stats["errors"] == 0

    # Re-importing should skip duplicates
    stats_dup = engine.import_memories(json_str, project_id="imp-proj")
    assert stats_dup["imported"] == 0
    assert stats_dup["skipped"] == 2


def test_backup(db: DatabaseManager, tmp_path: Path) -> None:
    engine = MemoryEngine(db)
    engine.remember(content="Content before backup", project_id="bk-proj")

    backup_file = tmp_path / "backup_test.db"
    result_path = engine.backup(dest_path=backup_file)

    assert result_path.exists()
    assert result_path.stat().st_size > 0
