"""Integration tests for agent session summary capture and metadata preservation."""
from __future__ import annotations

from recallx.core.memory import MemoryEngine


def test_save_session_summary(engine: MemoryEngine) -> None:
    """Ensure session summaries can be saved and retrieved."""
    summary_text = (
        "Completed authentication module refactoring. Added JWT bearer token validation "
        "and implemented unit tests."
    )
    saved = engine.save_session_summary(
        project_id="session-proj",
        summary=summary_text,
        tasks_completed=["Refactor auth", "Add JWT validation"],
        tasks_pending=["Add rate limiting"],
    )

    assert saved["id"] is not None
    assert saved["content"] == summary_text
    assert saved["project_id"] == "session-proj"

    # Verify retrieval
    retrieved = engine.get(saved["id"])
    assert retrieved is not None
    assert retrieved["content"] == summary_text


def test_session_summary_has_correct_type(engine: MemoryEngine) -> None:
    """Ensure saved session summaries have memory_type set to 'session'."""
    saved = engine.save_session_summary(
        project_id="session-proj",
        summary="Working session progress summary note.",
    )

    assert saved["memory_type"] == "session"
    assert "session" in saved["tags"]
    assert "progress" in saved["tags"]


def test_session_summary_metadata(engine: MemoryEngine) -> None:
    """Ensure tasks completed, pending tasks, and issues are stored in metadata."""
    completed = ["Unit test suite implementation", "Database migrations"]
    pending = ["MCP server registration"]
    issues = ["Occasional busy timeout during concurrent SQLite writes"]

    saved = engine.save_session_summary(
        project_id="meta-proj",
        summary="Session with complete metadata checklist.",
        tasks_completed=completed,
        tasks_pending=pending,
        issues=issues,
    )

    metadata = saved.get("metadata") or saved.get("metadata_json") or {}
    assert metadata["tasks_completed"] == completed
    assert metadata["tasks_pending"] == pending
    assert metadata["issues"] == issues
    assert "session_saved_at" in metadata
