"""Integration tests for Memory CRUD operations through MemoryEngine and MemoryRepository."""
from __future__ import annotations

from typing import Any

from recallx.core.memory import MemoryEngine
from recallx.storage.repositories import MemoryCreate, MemoryRepository


def test_create_memory(engine: MemoryEngine, sample_memory: dict[str, Any]) -> None:
    """Ensure a basic memory record is created and persists."""
    saved = engine.remember(
        content=sample_memory["content"],
        project_id=sample_memory["project_id"],
        memory_type=sample_memory["memory_type"],
    )

    assert saved["id"] is not None
    assert len(saved["id"]) == 12
    assert saved["content"] == sample_memory["content"]
    assert saved["project_id"] == sample_memory["project_id"]
    assert saved["memory_type"] == sample_memory["memory_type"]
    assert saved["is_archived"] is False


def test_create_memory_with_all_fields(engine: MemoryEngine, sample_memory: dict[str, Any]) -> None:
    """Ensure memory record creation succeeds when all optional fields are populated."""
    saved = engine.remember(
        content=sample_memory["content"],
        project_id=sample_memory["project_id"],
        memory_type=sample_memory["memory_type"],
        tags=sample_memory["tags"],
        source="unit_test",
        importance=0.85,
        confidence=0.95,
        metadata={"author": "developer", "env": "testing"},
        expires_at="2030-01-01T00:00:00Z",
    )

    assert saved["source"] == "unit_test"
    assert saved["importance"] == 0.85
    assert saved["confidence"] == 0.95
    assert "database" in saved["tags"]
    assert saved["metadata"]["author"] == "developer"
    assert saved["expires_at"] is not None


def test_get_memory_by_id(engine: MemoryEngine, sample_memory: dict[str, Any]) -> None:
    """Ensure an existing memory can be retrieved by its unique ID."""
    saved = engine.remember(
        content=sample_memory["content"],
        project_id=sample_memory["project_id"],
    )

    retrieved = engine.get(saved["id"])
    assert retrieved is not None
    assert retrieved["id"] == saved["id"]
    assert retrieved["content"] == saved["content"]


def test_get_memory_not_found(engine: MemoryEngine) -> None:
    """Ensure querying a nonexistent memory ID returns None."""
    assert engine.get("nonexistent12") is None


def test_update_memory_content(engine: MemoryEngine, sample_memory: dict[str, Any]) -> None:
    """Ensure updating a memory's text content updates the hash and body."""
    saved = engine.remember(
        content=sample_memory["content"],
        project_id=sample_memory["project_id"],
    )

    new_text = "Updated architecture to use async SQLAlchemy 2.0 sessions."
    updated = engine.update(saved["id"], content=new_text)

    assert updated is not None
    assert updated["content"] == new_text
    assert updated["content_hash"] != saved["content_hash"]

    # Verify retrieval reflects the updated text
    fresh = engine.get(saved["id"])
    assert fresh is not None
    assert fresh["content"] == new_text


def test_update_memory_tags(engine: MemoryEngine, sample_memory: dict[str, Any]) -> None:
    """Ensure memory tags can be updated independently."""
    saved = engine.remember(
        content=sample_memory["content"],
        project_id=sample_memory["project_id"],
        tags=["initial"],
    )

    updated = engine.update(saved["id"], tags=["fastapi", "asyncio"])
    assert updated is not None
    assert "fastapi" in updated["tags"]
    assert "asyncio" in updated["tags"]
    assert "initial" not in updated["tags"]


def test_delete_memory(engine: MemoryEngine, sample_memory: dict[str, Any]) -> None:
    """Ensure deleting an existing memory removes it completely."""
    saved = engine.remember(
        content=sample_memory["content"],
        project_id=sample_memory["project_id"],
    )

    deleted = engine.forget(saved["id"])
    assert deleted is True
    assert engine.get(saved["id"]) is None


def test_delete_memory_not_found(engine: MemoryEngine) -> None:
    """Ensure attempting to delete a nonexistent memory returns False."""
    assert engine.forget("notfound9999") is False


def test_list_memories_all(engine: MemoryEngine, sample_memories: list[dict[str, Any]]) -> None:
    """Ensure list_memories returns all active stored memories."""
    for item in sample_memories:
        engine.remember(
            content=item["content"],
            project_id=item["project_id"],
            memory_type=item["memory_type"],
            tags=item["tags"],
            importance=item["importance"],
        )

    all_memories = engine.list_memories()
    assert len(all_memories) == len(sample_memories)


def test_list_memories_by_project(engine: MemoryEngine, sample_memories: list[dict[str, Any]]) -> None:
    """Ensure filtering by project_id isolates results properly."""
    engine.remember(content="Alpha project core setting", project_id="alpha")
    engine.remember(content="Beta project core setting", project_id="beta")

    alpha_list = engine.list_memories(project_id="alpha")
    beta_list = engine.list_memories(project_id="beta")

    assert len(alpha_list) == 1
    assert alpha_list[0]["project_id"] == "alpha"
    assert len(beta_list) == 1
    assert beta_list[0]["project_id"] == "beta"


def test_list_memories_by_type(engine: MemoryEngine, sample_memories: list[dict[str, Any]]) -> None:
    """Ensure filtering by memory_type returns only matching category records."""
    for item in sample_memories:
        engine.remember(
            content=item["content"],
            project_id=item["project_id"],
            memory_type=item["memory_type"],
            tags=item["tags"],
        )

    decisions = engine.list_memories(project_id="test-project", memory_type="decision")
    assert len(decisions) >= 1
    assert all(d["memory_type"] == "decision" for d in decisions)


def test_list_memories_pinned_only(engine: MemoryEngine, sample_memories: list[dict[str, Any]]) -> None:
    """Ensure pinned_only filter returns only pinned memories."""
    m1 = engine.remember(content="Unpinned note for backend", project_id="test-proj")
    m2 = engine.remember(content="Pinned architectural invariant", project_id="test-proj")
    engine.pin(m2["id"])

    pinned_list = engine.list_memories(project_id="test-proj", pinned_only=True)
    assert len(pinned_list) == 1
    assert pinned_list[0]["id"] == m2["id"]
    assert pinned_list[0]["is_pinned"] is True


def test_list_memories_pagination(engine: MemoryEngine) -> None:
    """Ensure pagination limits and offsets work as expected."""
    for i in range(10):
        engine.remember(content=f"Record numbered {i:02d} for pagination test", project_id="page-proj")

    page1 = engine.list_memories(project_id="page-proj", limit=4, offset=0)
    page2 = engine.list_memories(project_id="page-proj", limit=4, offset=4)
    page3 = engine.list_memories(project_id="page-proj", limit=4, offset=8)

    assert len(page1) == 4
    assert len(page2) == 4
    assert len(page3) == 2

    # Check distinct IDs across pages
    ids_p1 = {m["id"] for m in page1}
    ids_p2 = {m["id"] for m in page2}
    assert ids_p1.isdisjoint(ids_p2)


def test_duplicate_detection_returns_existing(engine: MemoryEngine) -> None:
    """Ensure recording identical content in the same project returns the existing memory."""
    content = "Always write descriptive commit messages following Conventional Commits"
    first = engine.remember(content=content, project_id="test-proj")
    second = engine.remember(content=content, project_id="test-proj")

    assert first["id"] == second["id"]
    # Total count in project should remain 1
    assert len(engine.list_memories(project_id="test-proj")) == 1


def test_different_projects_not_duplicate(engine: MemoryEngine) -> None:
    """Ensure identical content in different projects is NOT treated as duplicate."""
    content = "Using Docker Compose for local development environment"
    proj_a = engine.remember(content=content, project_id="project-a")
    proj_b = engine.remember(content=content, project_id="project-b")

    assert proj_a["id"] != proj_b["id"]
    assert proj_a["project_id"] == "project-a"
    assert proj_b["project_id"] == "project-b"
