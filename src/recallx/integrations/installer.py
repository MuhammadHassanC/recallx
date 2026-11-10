"""Automated configuration and installation engine for AI Coding Agents.

Enables one-step setup for Claude Code, Cursor, Gemini CLI / Antigravity,
Windsurf, Roo Code / Cline, Codex, and OpenCode.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SetupResult:
    """Summary of automated agent setup operations."""

    agent_name: str
    config_file: Optional[Path] = None
    configured: bool = False
    skills_installed: list[str] = field(default_factory=list)
    message: str = ""


def _safe_load_json(path: Path) -> dict[str, Any]:
    """Safely load JSON file or return empty dictionary if missing/malformed."""
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return {}
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_write_json(path: Path, data: dict[str, Any]) -> None:
    """Safely write JSON file with 2-space indentation, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _get_mcp_server_entry(command: str = "recallx") -> dict[str, Any]:
    """Generate canonical MCP server entry."""
    return {
        "command": command,
        "args": ["mcp", "serve"],
    }


def _update_mcp_config(
    file_path: Path,
    server_key: str = "recallx",
    command: str = "recallx",
) -> bool:
    """Inject or update recallx server in an agent's MCP settings file."""
    try:
        data = _safe_load_json(file_path)
        if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
            data["mcpServers"] = {}

        data["mcpServers"][server_key] = _get_mcp_server_entry(command)
        _safe_write_json(file_path, data)
        return True
    except Exception:
        return False


def get_skills_source_dir() -> Path:
    """Locate the packaged skills directory."""
    # First check internal package skills
    pkg_skills = Path(__file__).resolve().parent.parent / "skills"
    if pkg_skills.is_dir():
        return pkg_skills

    # Fallback to repo root skills
    repo_skills = Path(__file__).resolve().parent.parent.parent.parent / "skills"
    if repo_skills.is_dir():
        return repo_skills

    return pkg_skills


def copy_agent_skills(target_dir: Path) -> list[str]:
    """Copy Agent Skills (remember, recall, project-context) into target directory."""
    installed = []
    source_dir = get_skills_source_dir()
    if not source_dir.is_dir():
        return installed

    target_dir.mkdir(parents=True, exist_ok=True)
    for skill_name in ["remember", "recall", "project-context"]:
        src_skill = source_dir / skill_name
        dest_skill = target_dir / skill_name

        if src_skill.is_dir():
            dest_skill.mkdir(parents=True, exist_ok=True)
            skill_md = src_skill / "SKILL.md"
            if skill_md.is_file():
                shutil.copy2(skill_md, dest_skill / "SKILL.md")
                installed.append(f"{skill_name}/SKILL.md")

    return installed


# ----------------------------------------------------------------------
# Agent Specific Setup Functions
# ----------------------------------------------------------------------

def setup_claude_code(command: str = "recallx") -> SetupResult:
    """Configure Claude Code CLI and settings."""
    home = Path.home()
    config_file = home / ".claude.json"

    # Also check if cwd has .claude
    local_claude = Path.cwd() / ".claude"
    if local_claude.is_dir():
        local_config = local_claude / "config.json"
        _update_mcp_config(local_config, command=command)

    success = _update_mcp_config(config_file, command=command)

    # Copy skills to ~/.claude/skills and .claude/skills
    skills_installed = []
    global_skills = home / ".claude" / "skills"
    skills_installed.extend(copy_agent_skills(global_skills))
    if local_claude.is_dir():
        copy_agent_skills(local_claude / "skills")

    return SetupResult(
        agent_name="Claude Code",
        config_file=config_file,
        configured=success,
        skills_installed=skills_installed,
        message="Configured in ~/.claude.json and installed skills in ~/.claude/skills/",
    )


def setup_cursor(command: str = "recallx") -> SetupResult:
    """Configure Cursor IDE settings and rules."""
    cwd = Path.cwd()
    cursor_dir = cwd / ".cursor"
    config_file = cursor_dir / "mcp.json"

    # Also configure home cursor if it exists
    home_cursor = Path.home() / ".cursor"
    if home_cursor.is_dir():
        _update_mcp_config(home_cursor / "mcp.json", command=command)

    success = _update_mcp_config(config_file, command=command)

    # Setup Cursor Rule (.cursor/rules/recallx.mdc)
    rules_dir = cursor_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rule_file = rules_dir / "recallx.mdc"

    rule_content = """---
description: RecallX persistent memory rules for AI coding sessions
globs: *
---

# RecallX Persistent Memory Instructions

When working in this project:
1. At the beginning of a session or task, call the `recall` or `get_project_context` MCP tool to retrieve previous architecture decisions, conventions, and solved bugs.
2. After making major technical decisions, solving non-trivial bugs, or when the user states a convention, call the `remember` MCP tool to persist it.
3. At the end of a session with pending work, call `save_session_summary` to maintain continuity.
"""
    rule_file.write_text(rule_content.strip() + "\n", encoding="utf-8")

    return SetupResult(
        agent_name="Cursor",
        config_file=config_file,
        configured=success,
        skills_installed=["rules/recallx.mdc"],
        message="Configured in .cursor/mcp.json and added rule in .cursor/rules/recallx.mdc",
    )


def setup_gemini_antigravity(command: str = "recallx") -> SetupResult:
    """Configure Gemini CLI / Antigravity IDE settings and skills."""
    home = Path.home()
    config_file = home / ".gemini" / "settings.json"

    # Also check local .gemini
    local_gemini = Path.cwd() / ".gemini"
    if local_gemini.is_dir():
        _update_mcp_config(local_gemini / "settings.json", command=command)

    success = _update_mcp_config(config_file, command=command)

    # Copy skills to ~/.gemini/config/skills and ~/.gemini/antigravity/skills
    skills_installed = []
    target_skills_1 = home / ".gemini" / "config" / "skills"
    target_skills_2 = home / ".gemini" / "antigravity" / "skills"
    if target_skills_1.parent.is_dir():
        skills_installed.extend(copy_agent_skills(target_skills_1))
    if target_skills_2.parent.is_dir():
        skills_installed.extend(copy_agent_skills(target_skills_2))

    return SetupResult(
        agent_name="Gemini CLI / Antigravity",
        config_file=config_file,
        configured=success,
        skills_installed=skills_installed,
        message="Configured in ~/.gemini/settings.json and copied skills to Gemini skills directory",
    )


def setup_windsurf(command: str = "recallx") -> SetupResult:
    """Configure Windsurf IDE settings."""
    home = Path.home()
    config_file = home / ".codeium" / "windsurf" / "mcp_config.json"
    success = _update_mcp_config(config_file, command=command)

    return SetupResult(
        agent_name="Windsurf",
        config_file=config_file,
        configured=success,
        message="Configured in ~/.codeium/windsurf/mcp_config.json",
    )


def setup_cline_roo(command: str = "recallx") -> list[SetupResult]:
    """Configure Cline and Roo Code extensions in VS Code."""
    results = []
    appdata = os.environ.get("APPDATA")
    home = Path.home()

    potential_paths = []
    if sys.platform == "win32" and appdata:
        code_user = Path(appdata) / "Code" / "User" / "globalStorage"
        potential_paths.extend([
            ("Cline", code_user / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"),
            ("Roo Code", code_user / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json"),
        ])
    elif sys.platform == "darwin":
        code_user = home / "Library" / "Application Support" / "Code" / "User" / "globalStorage"
        potential_paths.extend([
            ("Cline", code_user / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"),
            ("Roo Code", code_user / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json"),
        ])
    else:
        code_user = home / ".config" / "Code" / "User" / "globalStorage"
        potential_paths.extend([
            ("Cline", code_user / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"),
            ("Roo Code", code_user / "rooveterinaryinc.roo-cline" / "settings" / "cline_mcp_settings.json"),
        ])

    for name, path in potential_paths:
        if path.parent.is_dir() or path.is_file():
            success = _update_mcp_config(path, command=command)
            results.append(
                SetupResult(
                    agent_name=name,
                    config_file=path,
                    configured=success,
                    message=f"Configured in {path}",
                )
            )

    return results


def setup_all_agents(command: str = "recallx") -> list[SetupResult]:
    """Automatically detect and configure all supported AI coding agents."""
    results: list[SetupResult] = []

    # 1. Claude Code
    results.append(setup_claude_code(command=command))

    # 2. Cursor
    results.append(setup_cursor(command=command))

    # 3. Gemini CLI / Antigravity
    results.append(setup_gemini_antigravity(command=command))

    # 4. Windsurf (if directory exists)
    if (Path.home() / ".codeium" / "windsurf").is_dir():
        results.append(setup_windsurf(command=command))

    # 5. Cline & Roo Code
    results.extend(setup_cline_roo(command=command))

    return results

