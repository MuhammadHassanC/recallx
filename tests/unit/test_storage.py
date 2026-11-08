"""Comprehensive unit and functional tests for RecallX storage subsystem."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from recallx.storage.database import DatabaseManager, get_database
from recallx.storage.migrations import SCHEMA_VERSION, SchemaManager
from recallx.storage.models import Base, Memory, Project
from recallx.storage.repositories import (
    MemoryCreate,
    MemoryRepository,
    ProjectRepository,
)
from recallx.utils.hashing import content_hash


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Fixture supplying an isolated file-backed database."""
    db_file = tmp_path / "test_storage.db"
    mgr = DatabaseManager(db_file)
    mgr.initialize()
    yield mgr
    mgr.close()


def test_memory_model_roundtrip() -> None:
    """Test Memory model serialization and deserialization."""
    now = datetime.now(timezone.utc)
    c_hash = content_hash("System architecture decision")

    mem = Memory(
        id="mem123456789",
        memory_type="decision",
        content="System architecture decision",
        project_id="proj_alpha",
        tags=["arch", "database"],
        source="claude-code",
        importance=0.8,
        confidence=0.9,
        is_pinned=True,
        is_archived=False,
        content_hash=c_hash,
        metadata_json={"author": "lead"},
        created_at=now,
        updated_at=now,
        accessed_at=now,
    )

    data = mem.to_dict()
    assert data["id"] == "mem123456789"
    assert data["memory_type"] == "decision"
    assert data["importance"] == 0.8
    assert data["is_pinned"] is True
    assert data["tags"] == ["arch", "database"]
    assert data["metadata"]["author"] == "lead"

    reconstructed = Memory.from_dict(data)
    assert reconstructed.id == mem.id
    assert reconstructed.content == mem.content
    assert reconstructed.content_hash == mem.content_hash
    assert reconstructed.importance == mem.importance


def test_project_model_roundtrip() -> None:
    """Test Project model serialization and deserialization."""
    now = datetime.now(timezone.utc)
    proj = Project(
        id="proj_1",
        name="Project One",
        description="Core persistent storage infrastructure",
        path="/workspace/proj1",
        created_at=now,
        updated_at=now,
        metadata_json={"env": "prod"},
    )

    data = proj.to_dict()
    assert data["id"] == "proj_1"
    assert data["name"] == "Project One"
    assert data["metadata"]["env"] == "prod"

    reconstructed = Project.from_dict(data)
    assert reconstructed.id == proj.id
    assert reconstructed.name == proj.name
    assert reconstructed.description == proj.description


def test_memory_create_pydantic_validation() -> None:
    """Test MemoryCreate schema validation rules."""
    # Valid model
    m_valid = MemoryCreate(
        content="Valid memory entry",
        project_id="proj_valid",
        memory_type="bug_solution",
        tags=["fix", "sql"],
        importance=0.9,
    )
    assert m_valid.memory_type == "bug_solution"

    # Invalid empty content
    with pytest.raises(ValueError):
        MemoryCreate(content="   ", project_id="proj_valid")

    # Invalid memory_type
    with pytest.raises(ValueError):
        MemoryCreate(
            content="Some valid content",
            project_id="proj_valid",
            memory_type="unsupported_type",
        )

    # Importance range check
    with pytest.raises(ValueError):
        MemoryCreate(
            content="Some valid content",
            project_id="proj_valid",
            importance=1.5,
        )


def test_memory_repository_crud(temp_db: DatabaseManager) -> None:
    """Test full CRUD operations in MemoryRepository."""
    repo = MemoryRepository(temp_db)

    # Create
    item = repo.create(
        MemoryCreate(
            content="Always use parameterized SQL queries to prevent SQL injection.",
            project_id="web_app",
            memory_type="decision",
            tags=["security", "sql"],
            importance=0.95,
            confidence=0.99,
        )
    )
    mem_id = item["id"]
    assert len(mem_id) == 12
    assert item["project_id"] == "web_app"
    assert item["is_pinned"] is False
    assert item["is_archived"] is False

    # Get
    fetched = repo.get(mem_id)
    assert fetched is not None
    assert fetched["id"] == mem_id
    assert fetched["content"] == item["content"]

    # Update
    updated = repo.update(
        mem_id,
        {
            "content": "Always use parameterized queries for defense against SQL injection attacks.",
            "is_pinned": True,
            "tags": ["security", "sql", "injection"],
        },
    )
    assert updated is not None
    assert updated["is_pinned"] is True
    assert "injection" in updated["tags"]
    assert updated["content_hash"] == content_hash(
        "Always use parameterized queries for defense against SQL injection attacks."
    )

    # Delete
    deleted = repo.delete(mem_id)
    assert deleted is True
    assert repo.get(mem_id) is None
    assert repo.delete(mem_id) is False


def test_memory_repository_list_and_filters(temp_db: DatabaseManager) -> None:
    """Test listing memories with multiple criteria and pagination."""
    repo = MemoryRepository(temp_db)

    # Seed records
    repo.create(
        MemoryCreate(
            content="Database migration v1 applied",
            project_id="backend",
            memory_type="session",
        )
    )
    m_pinned = repo.create(
        MemoryCreate(
            content="Critical database tuning decision",
            project_id="backend",
            memory_type="decision",
        )
    )
    repo.update(m_pinned["id"], {"is_pinned": True})

    repo.create(
        MemoryCreate(
            content="Frontend build optimization",
            project_id="frontend",
            memory_type="decision",
        )
    )

    # List backend project
    backend_mems = repo.list(project_id="backend")
    assert len(backend_mems) == 2
    # Pinned memory must come first
    assert backend_mems[0]["id"] == m_pinned["id"]

    # List by type
    decisions = repo.list(memory_type="decision")
    assert len(decisions) == 2

    # Pinned only
    pinned_list = repo.list(pinned_only=True)
    assert len(pinned_list) == 1
    assert pinned_list[0]["id"] == m_pinned["id"]

    # Limit and offset
    page = repo.list(limit=1, offset=0)
    assert len(page) == 1


def test_memory_repository_search_fts(temp_db: DatabaseManager) -> None:
    """Test SQLite FTS5 BM25 search functionality."""
    repo = MemoryRepository(temp_db)

    repo.create(
        MemoryCreate(
            content="Optimized query execution by adding compound index on user_id and created_at",
            project_id="infra",
            memory_type="bug_solution",
            tags=["postgres", "performance"],
        )
    )
    repo.create(
        MemoryCreate(
            content="Redis cache layer configured for hot user sessions",
            project_id="infra",
            memory_type="decision",
            tags=["redis", "cache"],
        )
    )

    # Search for index optimization
    results = repo.search_fts("compound index", project_id="infra")
    assert len(results) >= 1
    assert "compound index" in results[0]["content"]

    # Search by tag
    tag_results = repo.search_fts("redis")
    assert len(tag_results) >= 1
    assert tag_results[0]["memory_type"] == "decision"

    # Search with special characters (must not crash)
    special_res = repo.search_fts("user_id: [test]* &*!@#")
    assert isinstance(special_res, list)

    # Empty search
    assert repo.search_fts("") == []
    assert repo.search_fts("   ") == []


def test_memory_repository_stats_and_counts(temp_db: DatabaseManager) -> None:
    """Test stats aggregation and counting."""
    repo = MemoryRepository(temp_db)

    repo.create(
        MemoryCreate(
            content="Decision one",
            project_id="proj_x",
            memory_type="decision",
        )
    )
    m2 = repo.create(
        MemoryCreate(
            content="Decision two",
            project_id="proj_x",
            memory_type="decision",
        )
    )
    repo.update(m2["id"], {"is_pinned": True})

    m3 = repo.create(
        MemoryCreate(
            content="Bug solution",
            project_id="proj_y",
            memory_type="bug_solution",
        )
    )
    repo.update(m3["id"], {"is_archived": True})

    assert repo.count(project_id="proj_x") == 2
    assert repo.count(project_id="proj_y") == 0  # archived memory not counted in active

    stats = repo.get_stats()
    assert stats["total"] == 2
    assert stats["pinned"] == 1
    assert stats["archived"] == 1
    assert stats["counts_by_type"].get("decision") == 2
    assert "proj_x" in stats["projects"]
    assert "proj_y" in stats["projects"]


def test_memory_repository_accessed_at(temp_db: DatabaseManager) -> None:
    """Test accessed_at timestamp updates."""
    repo = MemoryRepository(temp_db)
    mem = repo.create(
        MemoryCreate(
            content="Track access frequency",
            project_id="proj_z",
        )
    )

    initial_accessed = mem["accessed_at"]
    repo.update_accessed(mem["id"])
    refetched = repo.get(mem["id"])
    assert refetched is not None
    assert refetched["accessed_at"] is not None


def test_project_repository(temp_db: DatabaseManager) -> None:
    """Test ProjectRepository CRUD operations."""
    repo = ProjectRepository(temp_db)

    # Create
    proj = repo.create(
        project_id="core_engine",
        name="Core Engine",
        description="Persistent memory engine",
        path="/workspaces/core",
        metadata={"priority": "high"},
    )
    assert proj["id"] == "core_engine"
    assert repo.exists("core_engine") is True

    # Get
    fetched = repo.get("core_engine")
    assert fetched is not None
    assert fetched["name"] == "Core Engine"

    # Update
    updated = repo.update("core_engine", {"name": "Core Engine V2", "path": "/new/path"})
    assert updated is not None
    assert updated["name"] == "Core Engine V2"
    assert updated["path"] == "/new/path"

    # List
    all_projects = repo.list()
    assert len(all_projects) >= 1
    assert any(p["id"] == "core_engine" for p in all_projects)

    # Delete
    assert repo.delete("core_engine") is True
    assert repo.exists("core_engine") is False
    assert repo.get("core_engine") is None


def test_schema_manager_lifecycle(temp_db: DatabaseManager) -> None:
    """Test schema version tracking and migration runner."""
    sm = SchemaManager(temp_db)
    assert sm.get_current_version() == 0
    assert sm.needs_migration() is True

    final_v = sm.migrate()
    assert final_v == SCHEMA_VERSION
    assert sm.get_current_version() == SCHEMA_VERSION
    assert sm.needs_migration() is False

    # Second migration call is no-op
    repeat_v = sm.migrate()
    assert repeat_v == SCHEMA_VERSION


def test_database_manager_rebuild_fts(temp_db: DatabaseManager) -> None:
    """Test rebuild_fts repopulates FTS index from active memories."""
    m_repo = MemoryRepository(temp_db)
    m_repo.create(
        MemoryCreate(
            content="Determinism across multiple sessions",
            project_id="p1",
            tags=["deterministic"],
        )
    )

    # Rebuild FTS
    temp_db.rebuild_fts()

    results = m_repo.search_fts("determinism")
    assert len(results) == 1
    assert "Determinism" in results[0]["content"]


def test_get_database_singleton(tmp_path: Path) -> None:
    """Test get_database singleton behavior."""
    custom_db_path = tmp_path / "singleton_test.db"
    db1 = get_database(custom_db_path)
    db2 = get_database(custom_db_path)
    assert db1 is db2
    assert db1.verify_integrity() is True
    db1.close()
