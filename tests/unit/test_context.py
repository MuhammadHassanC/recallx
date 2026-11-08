"""Unit tests for ContextBuilder."""

from __future__ import annotations

from recallx.core.context import ContextBuilder
from recallx.core.memory import MemoryEngine
from recallx.storage.database import DatabaseManager


def test_build_project_context(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)
    builder = ContextBuilder(engine)

    engine.project_repo.create(
        project_id="ctx-proj",
        name="Context Test Project",
        description="A project demonstrating context building",
    )

    m1 = engine.remember(
        content="Core architectural rule: Never commit API credentials to git repository",
        project_id="ctx-proj",
        memory_type="decision",
        tags=["security", "rules"],
    )
    engine.pin(m1["id"])

    engine.remember(
        content="Backend framework is FastAPI with Uvicorn runner",
        project_id="ctx-proj",
        memory_type="project",
        tags=["fastapi", "stack"],
    )

    context_str = builder.build_project_context("ctx-proj", max_tokens=1000)

    assert "Context Test Project" in context_str
    assert "Pinned Guidelines & Architectural Directives" in context_str
    assert "Never commit API credentials" in context_str
    assert "Backend framework is FastAPI" in context_str


def test_build_query_context(db: DatabaseManager) -> None:
    engine = MemoryEngine(db)
    builder = ContextBuilder(engine)

    engine.remember(
        content="Resolved PostgreSQL connection pool starvation by increasing pool size to 30",
        project_id="query-ctx-proj",
        memory_type="bug_solution",
        tags=["postgres", "pools"],
    )

    ctx_str = builder.build_query_context("postgres pool starvation", "query-ctx-proj", limit=3)

    assert "Relevant Project Memories" in ctx_str
    assert "pool starvation" in ctx_str
    assert "postgres" in ctx_str
