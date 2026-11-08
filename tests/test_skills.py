"""Tests for RecallX agent skills documentation and specifications."""

from __future__ import annotations

from pathlib import Path


def test_skills_files_exist() -> None:
    """Verify that all required SKILL.md files exist and are well-formed."""
    skills_root = Path("src/recallx/skills")

    remember_skill = skills_root / "remember" / "SKILL.md"
    recall_skill = skills_root / "recall" / "SKILL.md"
    project_context_skill = skills_root / "project-context" / "SKILL.md"

    for path in (remember_skill, recall_skill, project_context_skill):
        assert path.is_file(), f"Expected skill file missing: {path}"
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---")
        assert "name:" in content
        assert "description:" in content
        assert "When to Trigger" in content
        assert "When NOT to Trigger" in content
        assert "How to Use" in content


def test_remember_skill_content() -> None:
    """Verify recallx-remember skill specifications."""
    remember_skill = Path("src/recallx/skills/remember/SKILL.md")
    content = remember_skill.read_text(encoding="utf-8")

    assert "name: recallx-remember" in content
    assert "**memory_type**: One of: project, decision, bug_solution, preference, session" in content
    assert "**importance**: 0.0-1.0" in content


def test_recall_skill_content() -> None:
    """Verify recallx-recall skill specifications."""
    recall_skill = Path("src/recallx/skills/recall/SKILL.md")
    content = recall_skill.read_text(encoding="utf-8")

    assert "name: recallx-recall" in content
    assert "get_project_context" in content


def test_project_context_skill_content() -> None:
    """Verify recallx-project-context skill specifications."""
    project_skill = Path("src/recallx/skills/project-context/SKILL.md")
    content = project_skill.read_text(encoding="utf-8")

    assert "name: recallx-project-context" in content
    assert "save_session_summary" in content
