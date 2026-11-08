"""Unit and integration tests for RecallX Model Context Protocol (MCP) server."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from recallx.mcp import prompts, resources, tools
from recallx.mcp.server import mcp
from recallx.storage.database import DatabaseManager
from recallx.core.memory import MemoryEngine


@pytest.fixture(autouse=True)
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryEngine:
    """Provide an isolated database and reset the MCP lazy engine singleton for each test."""
    test_db_path = tmp_path / "test_mcp_recallx.db"
    db_mgr = DatabaseManager(test_db_path)
    db_mgr.initialize()
    engine = MemoryEngine(db_mgr)

    # Patch tools._engine and tools._get_engine
    monkeypatch.setattr(tools, "_engine", engine)
    monkeypatch.setattr(tools, "_get_engine", lambda: engine)

    yield engine
    db_mgr.close()


def test_server_registration() -> None:
    """Ensure FastMCP server registers all required tools, resources, and prompts."""
    tool_names = [t.name for t in mcp._tool_manager.list_tools()]
    expected_tools = [
        "remember",
        "recall",
        "get_memory",
        "update_memory",
        "forget",
        "list_memories",
        "get_project_context",
        "save_session_summary",
        "consolidate_memories",
        "get_memory_stats",
    ]
    for expected in expected_tools:
        assert expected in tool_names, f"Tool '{expected}' must be registered"

    resource_uris = [str(r.uri) for r in mcp._resource_manager.list_resources()]
    assert "memory://stats" in resource_uris
    assert "memory://projects" in resource_uris

    prompt_names = [p.name for p in mcp._prompt_manager.list_prompts()]
    assert "remember-context" in prompt_names
    assert "recall-context" in prompt_names
    assert "session-summary" in prompt_names


def test_remember_tool_success() -> None:
    """Test saving a memory via remember tool."""
    raw = tools.remember(
        content="Use PostgreSQL for transactional consistency",
        project_id="test-api",
        memory_type="decision",
        tags=["postgres", "sql", "db"],
        importance=0.85,
        source="mcp",
    )
    result = json.loads(raw)

    assert "id" in result
    assert result["content"] == "Use PostgreSQL for transactional consistency"
    assert result["project_id"] == "test-api"
    assert result["memory_type"] == "decision"
    assert "postgres" in result["tags"]
    assert result["importance"] == 0.85


def test_remember_tool_error_handling() -> None:
    """Test remember tool returns JSON error on invalid inputs."""
    raw = tools.remember(
        content="",  # Blank content should fail validation
        project_id="test-api",
    )
    result = json.loads(raw)
    assert "error" in result


def test_recall_tool() -> None:
    """Test searching memories via recall tool."""
    tools.remember(
        content="Use Redis for caching user session tokens",
        project_id="test-api",
        memory_type="decision",
        tags=["cache", "redis"],
        importance=0.75,
    )
    tools.remember(
        content="Configure CORS headers on API gateway",
        project_id="test-api",
        memory_type="decision",
        tags=["cors", "gateway"],
        importance=0.60,
    )

    raw = tools.recall(query="Redis session cache", project_id="test-api")
    results = json.loads(raw)

    assert isinstance(results, list)
    assert len(results) >= 1
    assert any("Redis" in r["content"] for r in results)
    assert "relevance" in results[0]


def test_get_and_update_memory_tools() -> None:
    """Test retrieving and updating specific memories by ID."""
    created = json.loads(
        tools.remember(
            content="Initial documentation string",
            project_id="test-api",
            memory_type="project",
            importance=0.5,
        )
    )
    mem_id = created["id"]

    # Get memory
    raw_get = tools.get_memory(memory_id=mem_id)
    retrieved = json.loads(raw_get)
    assert retrieved["id"] == mem_id
    assert retrieved["content"] == "Initial documentation string"

    # Update memory
    raw_update = tools.update_memory(
        memory_id=mem_id,
        content="Updated documentation string",
        tags=["docs", "v2"],
        importance=0.9,
    )
    updated = json.loads(raw_update)
    assert updated["id"] == mem_id
    assert updated["content"] == "Updated documentation string"
    assert updated["importance"] == 0.9
    assert "docs" in updated["tags"]


def test_get_memory_not_found() -> None:
    """Test get_memory returns error JSON when memory does not exist."""
    raw = tools.get_memory(memory_id="nonexistent12")
    result = json.loads(raw)
    assert "error" in result


def test_forget_tool() -> None:
    """Test deleting a memory via forget tool."""
    created = json.loads(
        tools.remember(
            content="Temporary note to be forgotten",
            project_id="test-api",
        )
    )
    mem_id = created["id"]

    raw_del = tools.forget(memory_id=mem_id)
    res_del = json.loads(raw_del)
    assert res_del.get("success") is True

    # Verify no longer exists
    raw_get = tools.get_memory(memory_id=mem_id)
    res_get = json.loads(raw_get)
    assert "error" in res_get


def test_forget_tool_not_found() -> None:
    """Test forget tool returns error JSON for missing memory."""
    raw = tools.forget(memory_id="missing_id12")
    res = json.loads(raw)
    assert "error" in res


def test_list_memories_tool() -> None:
    """Test listing memories with pagination and filters."""
    for i in range(5):
        tools.remember(
            content=f"Memory item {i}",
            project_id="proj-alpha" if i < 3 else "proj-beta",
            memory_type="decision" if i % 2 == 0 else "bug_solution",
        )

    # Filter by project
    raw = tools.list_memories(project_id="proj-alpha", limit=10)
    items = json.loads(raw)
    assert len(items) == 3
    assert all(it["project_id"] == "proj-alpha" for it in items)

    # Filter by memory_type
    raw_types = tools.list_memories(memory_type="bug_solution", limit=10)
    type_items = json.loads(raw_types)
    assert all(it["memory_type"] == "bug_solution" for it in type_items)


def test_get_project_context_tool() -> None:
    """Test retrieving structured project context."""
    tools.remember(
        content="Architecture uses FastAPI backend with SQLite",
        project_id="proj-context",
        memory_type="project",
        importance=0.9,
    )
    tools.remember(
        content="Convention: always format with black and isort",
        project_id="proj-context",
        memory_type="preference",
        importance=0.7,
    )

    raw = tools.get_project_context(project_id="proj-context", limit=5)
    ctx = json.loads(raw)

    assert ctx["project_id"] == "proj-context"
    assert "memories_by_type" in ctx
    assert ctx["total_memories"] == 2
    assert "project" in ctx["memories_by_type"]
    assert "preference" in ctx["memories_by_type"]


def test_save_session_summary_tool() -> None:
    """Test saving a coding session summary."""
    raw = tools.save_session_summary(
        project_id="proj-sess",
        summary="Completed API endpoints for user auth",
        tasks_completed=["JWT auth endpoint", "Refresh token handler"],
        tasks_pending=["Password reset email"],
        issues=["Rate limiter timeout on burst requests"],
    )
    result = json.loads(raw)

    assert "id" in result
    assert result["project_id"] == "proj-sess"
    assert result["memory_type"] == "session"
    assert result["content"] == "Completed API endpoints for user auth"
    assert "metadata" in result
    meta = result["metadata"]
    assert "JWT auth endpoint" in meta["tasks_completed"]
    assert "Password reset email" in meta["tasks_pending"]
    assert "Rate limiter timeout on burst requests" in meta["issues"]


def test_consolidate_memories_tool() -> None:
    """Test consolidate_memories tool returns candidate groups."""
    tools.remember(
        content="Use PostgreSQL for relational storage in backend",
        project_id="proj-cons",
        memory_type="decision",
        tags=["database", "postgres"],
    )
    tools.remember(
        content="PostgreSQL chosen as relational storage database",
        project_id="proj-cons",
        memory_type="decision",
        tags=["database", "postgres"],
    )

    raw = tools.consolidate_memories(project_id="proj-cons")
    res = json.loads(raw)

    assert res["project_id"] == "proj-cons"
    assert "groups" in res
    assert "groups_count" in res


def test_get_memory_stats_tool() -> None:
    """Test get_memory_stats tool output structure."""
    tools.remember(
        content="Test item for stats",
        project_id="proj-stats",
        memory_type="preference",
    )

    raw = tools.get_memory_stats(project_id="proj-stats")
    stats = json.loads(raw)

    assert "total" in stats
    assert stats["total"] >= 1
    assert "counts_by_type" in stats
    assert "projects" in stats


def test_resources_memory_stats_and_projects() -> None:
    """Test memory://stats and memory://projects resource readers."""
    tools.remember(
        content="Resource test item",
        project_id="proj-res",
        memory_type="project",
    )

    # Test memory://stats
    raw_stats = resources.memory_stats()
    stats = json.loads(raw_stats)
    assert "total" in stats
    assert stats["total"] >= 1

    # Test memory://projects
    raw_projects = resources.memory_projects()
    projects = json.loads(raw_projects)
    assert isinstance(projects, list)
    proj_entry = next((p for p in projects if p["project_id"] == "proj-res"), None)
    assert proj_entry is not None
    assert proj_entry["total_memories"] >= 1


def test_prompts_templates() -> None:
    """Test prompt templates generation."""
    p_remember = prompts.remember_context(project_id="proj-test", topic="Authentication")
    assert "proj-test" in p_remember
    assert "Authentication" in p_remember
    assert "remember" in p_remember

    p_recall = prompts.recall_context(project_id="proj-test", task="Setup OAuth")
    assert "proj-test" in p_recall
    assert "Setup OAuth" in p_recall
    assert "recall" in p_recall

    p_session = prompts.session_summary(project_id="proj-test")
    assert "proj-test" in p_session
    assert "save_session_summary" in p_session
