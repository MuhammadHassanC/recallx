"""Integration tests for exporting and importing memories."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from recallx.core.memory import MemoryEngine


def test_export_all_memories(engine: MemoryEngine, tmp_path: Path) -> None:
    """Ensure all memories across projects are exported when no project filter is passed."""
    engine.remember(content="Memory from Project 1", project_id="p1")
    engine.remember(content="Memory from Project 2", project_id="p2")

    out_file = tmp_path / "all_memories.json"
    json_str = engine.export_memories(project_id=None, output_path=out_file)

    assert out_file.is_file()
    data = json.loads(json_str)
    assert data["count"] == 2
    assert len(data["memories"]) == 2
    contents = {m["content"] for m in data["memories"]}
    assert "Memory from Project 1" in contents
    assert "Memory from Project 2" in contents


def test_export_by_project(engine: MemoryEngine, tmp_path: Path) -> None:
    """Ensure exporting with a project_id exports only that project's memories."""
    engine.remember(content="Alpha specific memory", project_id="alpha")
    engine.remember(content="Beta specific memory", project_id="beta")

    out_file = tmp_path / "alpha_export.json"
    json_str = engine.export_memories(project_id="alpha", output_path=out_file)

    data = json.loads(json_str)
    assert data["count"] == 1
    assert data["memories"][0]["project_id"] == "alpha"
    assert data["memories"][0]["content"] == "Alpha specific memory"


def test_import_memories(engine: MemoryEngine) -> None:
    """Ensure memories exported to JSON can be imported into a target project."""
    payload = {
        "version": "1.0.0",
        "memories": [
            {
                "content": "Imported decision note 1",
                "project_id": "original-proj",
                "memory_type": "decision",
                "tags": ["import", "test"],
                "importance": 0.8,
            },
            {
                "content": "Imported preference note 2",
                "project_id": "original-proj",
                "memory_type": "preference",
                "tags": ["style"],
                "importance": 0.5,
            },
        ],
    }

    result = engine.import_memories(json.dumps(payload), project_id="target-proj")
    assert result["imported"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == 0

    imported_list = engine.list_memories(project_id="target-proj")
    assert len(imported_list) == 2
    assert any("Imported decision note 1" in m["content"] for m in imported_list)


def test_import_skips_duplicates(engine: MemoryEngine) -> None:
    """Ensure re-importing the same memories skips existing duplicate entries."""
    payload = {
        "memories": [
            {
                "content": "Idempotent memory payload entry",
                "project_id": "idempotent-proj",
            }
        ]
    }
    json_str = json.dumps(payload)

    first_run = engine.import_memories(json_str, project_id="idempotent-proj")
    assert first_run["imported"] == 1
    assert first_run["skipped"] == 0

    second_run = engine.import_memories(json_str, project_id="idempotent-proj")
    assert second_run["imported"] == 0
    assert second_run["skipped"] == 1


def test_import_invalid_json_raises(engine: MemoryEngine) -> None:
    """Ensure supplying malformed JSON string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid JSON"):
        engine.import_memories("{{{broken json content---", project_id="any-proj")


def test_import_malicious_content_redacted(engine: MemoryEngine) -> None:
    """Ensure imported memories containing credentials or access keys are redacted."""
    leaked_key = "AKIAIOSFODNN7EXAMPLE"
    payload = {
        "memories": [
            {
                "content": f"Leaked AWS key {leaked_key} in cloud deployment config",
                "project_id": "sec-proj",
            }
        ]
    }

    engine.import_memories(json.dumps(payload), project_id="sec-proj")
    mems = engine.list_memories(project_id="sec-proj")

    assert len(mems) == 1
    saved_content = mems[0]["content"]
    assert leaked_key not in saved_content
    assert "[REDACTED]" in saved_content
