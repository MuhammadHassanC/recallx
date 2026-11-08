"""RecallX MCP Tools - Tool implementations for AI coding agents."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from recallx.mcp.server import mcp
from recallx.utils.logging import get_logger

if TYPE_CHECKING:
    from recallx.core.memory import MemoryEngine

logger = get_logger("mcp.tools")

_engine: MemoryEngine | None = None


def _get_engine() -> MemoryEngine:
    """Lazily initialize and return the MemoryEngine singleton.

    Returns:
        Configured MemoryEngine instance.
    """
    global _engine
    if _engine is None:
        from recallx.core.memory import MemoryEngine
        from recallx.storage.database import get_database

        db = get_database()
        db.initialize()
        _engine = MemoryEngine(db)
    return _engine


@mcp.tool()
def remember(
    content: str,
    project_id: str,
    memory_type: str = "project",
    tags: list[str] = [],  # noqa: B006
    importance: float = 0.5,
    source: str = "mcp",
) -> str:
    """Save a memory into RecallX persistent storage.

    Args:
        content: The information to remember.
        project_id: Project identifier (e.g. 'my-api', 'frontend-app').
        memory_type: Category: project, decision, bug_solution, preference, session.
        tags: Tags for categorization.
        importance: Importance from 0.0 to 1.0.
        source: Source of this memory.

    Returns:
        JSON string with the created memory.
    """
    try:
        engine = _get_engine()
        tag_list = list(tags) if tags else []
        result = engine.remember(
            content=content,
            project_id=project_id,
            memory_type=memory_type,
            tags=tag_list,
            importance=importance,
            source=source,
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in remember tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def recall(
    query: str,
    project_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 10,
) -> str:
    """Search for relevant memories matching a query.

    Args:
        query: What to search for.
        project_id: Filter by project.
        memory_type: Filter by memory type.
        limit: Maximum results (default 10).

    Returns:
        JSON string with list of relevant memories with relevance scores.
    """
    try:
        engine = _get_engine()
        results = engine.recall(
            query=query,
            project_id=project_id,
            memory_type=memory_type,
            limit=limit,
        )
        return json.dumps(results, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in recall tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def get_memory(memory_id: str) -> str:
    """Retrieve a specific memory by ID.

    Args:
        memory_id: Unique memory identifier.

    Returns:
        JSON string with the memory or error.
    """
    try:
        engine = _get_engine()
        mem = engine.get(memory_id)
        if mem is None:
            return json.dumps({"error": f"Memory not found: {memory_id}"}, indent=2)
        return json.dumps(mem, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in get_memory tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def update_memory(
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    importance: float | None = None,
) -> str:
    """Update an existing memory.

    Args:
        memory_id: Unique memory identifier.
        content: Updated text content.
        tags: Updated tags list.
        importance: Updated importance score (0.0 to 1.0).

    Returns:
        JSON string with updated memory.
    """
    try:
        engine = _get_engine()
        updated = engine.update(
            memory_id=memory_id,
            content=content,
            tags=tags,
            importance=importance,
        )
        if updated is None:
            return json.dumps({"error": f"Memory not found: {memory_id}"}, indent=2)
        return json.dumps(updated, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in update_memory tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def forget(memory_id: str) -> str:
    """Delete a specific memory by ID.

    Args:
        memory_id: Unique memory identifier.

    Returns:
        JSON confirmation.
    """
    try:
        engine = _get_engine()
        deleted = engine.forget(memory_id)
        if not deleted:
            return json.dumps({"error": f"Memory not found: {memory_id}"}, indent=2)
        return json.dumps({"success": True, "deleted_id": memory_id}, indent=2)
    except Exception as exc:
        logger.error("Error in forget tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def list_memories(
    project_id: str | None = None,
    memory_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    pinned_only: bool = False,
) -> str:
    """List memories with filtering.

    Args:
        project_id: Filter by project.
        memory_type: Filter by memory type.
        limit: Maximum results (default 20).
        offset: Offset for pagination (default 0).
        pinned_only: Return only pinned memories if True.

    Returns:
        JSON string with memory list.
    """
    try:
        engine = _get_engine()
        memories = engine.list_memories(
            project_id=project_id,
            memory_type=memory_type,
            limit=limit,
            offset=offset,
            pinned_only=pinned_only,
        )
        return json.dumps(memories, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in list_memories tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def get_project_context(project_id: str, limit: int = 10) -> str:
    """Get compact project context summary.

    Args:
        project_id: Project identifier.
        limit: Maximum memories per category.

    Returns:
        JSON string with structured project context.
    """
    try:
        engine = _get_engine()
        context = engine.get_project_context(project_id=project_id, limit=limit)
        return json.dumps(context, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in get_project_context tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def save_session_summary(
    project_id: str,
    summary: str,
    tasks_completed: list[str] = [],  # noqa: B006
    tasks_pending: list[str] = [],  # noqa: B006
    issues: list[str] = [],  # noqa: B006
) -> str:
    """Save a coding session summary.

    Args:
        project_id: Project identifier.
        summary: Brief summary of what was accomplished.
        tasks_completed: List of tasks completed.
        tasks_pending: List of tasks remaining/pending.
        issues: List of issues or blockers discovered.

    Returns:
        JSON confirmation.
    """
    try:
        engine = _get_engine()
        result = engine.save_session_summary(
            project_id=project_id,
            summary=summary,
            tasks_completed=list(tasks_completed) if tasks_completed else [],
            tasks_pending=list(tasks_pending) if tasks_pending else [],
            issues=list(issues) if issues else [],
        )
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in save_session_summary tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def consolidate_memories(project_id: str) -> str:
    """Find related memories and propose consolidation.

    Args:
        project_id: Project identifier.

    Returns:
        JSON with groups of related memories.
    """
    try:
        engine = _get_engine()
        from recallx.core.consolidation import ConsolidationEngine

        consolidation_engine = ConsolidationEngine(engine.repo)
        candidates = consolidation_engine.find_consolidation_candidates(project_id=project_id)
        result: dict[str, Any] = {
            "project_id": project_id,
            "groups_count": len(candidates),
            "groups": candidates,
        }
        return json.dumps(result, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in consolidate_memories tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.tool()
def get_memory_stats(project_id: str | None = None) -> str:
    """Get memory statistics.

    Args:
        project_id: Optional project filter.

    Returns:
        JSON with memory counts by type, total, projects.
    """
    try:
        engine = _get_engine()
        stats = engine.get_stats(project_id=project_id)
        return json.dumps(stats, indent=2, default=str)
    except Exception as exc:
        logger.error("Error in get_memory_stats tool: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)
