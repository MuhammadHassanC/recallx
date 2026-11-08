"""RecallX MCP Resources - Static and dynamic context resources."""
from __future__ import annotations

import json
from typing import Any

from recallx.mcp.server import mcp
from recallx.utils.logging import get_logger

logger = get_logger("mcp.resources")


@mcp.resource("memory://stats")
def memory_stats() -> str:
    """Memory statistics overview across all projects."""
    try:
        from recallx.mcp.tools import _get_engine

        engine = _get_engine()
        stats = engine.get_stats()
        return json.dumps(stats, indent=2, default=str)
    except Exception as exc:
        logger.error("Error reading memory://stats resource: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)


@mcp.resource("memory://projects")
def memory_projects() -> str:
    """List of projects with memory counts."""
    try:
        from recallx.mcp.tools import _get_engine

        engine = _get_engine()
        stats = engine.get_stats()
        project_ids = list(stats.get("projects", []))

        # Include registered projects from repository as well
        repo_projects = {p["id"]: p for p in engine.project_repo.list()}
        for p_id in repo_projects:
            if p_id not in project_ids:
                project_ids.append(p_id)

        projects_data: list[dict[str, Any]] = []
        for p_id in sorted(project_ids):
            p_stats = engine.get_stats(project_id=p_id)
            meta = repo_projects.get(p_id, {})
            projects_data.append(
                {
                    "project_id": p_id,
                    "name": meta.get("name", p_id),
                    "description": meta.get("description"),
                    "total_memories": p_stats.get("total", 0),
                    "counts_by_type": p_stats.get("counts_by_type", {}),
                    "pinned": p_stats.get("pinned", 0),
                }
            )

        return json.dumps(projects_data, indent=2, default=str)
    except Exception as exc:
        logger.error("Error reading memory://projects resource: %s", exc, exc_info=True)
        return json.dumps({"error": str(exc)}, indent=2)
