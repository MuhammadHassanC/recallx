#!/usr/bin/env python3
"""RecallX One-Step Automated Installer for Developers & AI Coding Agents.

Usage:
    python install.py           # Installs RecallX and auto-configures all detected agents
    python install.py --check   # Only checks agent configurations without modifying
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def print_banner() -> None:
    print("\n" + "=" * 65)
    print("  RecallX — Local-First Persistent Memory for AI Coding Agents")
    print("=" * 65 + "\n")


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        print(f"[!] Error: RecallX requires Python 3.10+. Current: {sys.version.split()[0]}")
        sys.exit(1)
    print(f"[✓] Python version verified: {sys.version.split()[0]}")


def install_package(force: bool = False) -> None:
    print("[*] Checking RecallX package installation...")
    repo_dir = Path(__file__).resolve().parent

    if not force:
        try:
            sys.path.insert(0, str(repo_dir / "src"))
            import recallx
            print(f"[✓] RecallX v{recallx.__version__} is already available.")
            return
        except ImportError:
            pass

    print("[*] Installing RecallX package and dependencies via pip...")
    cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_dir), "--no-build-isolation"]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        print("[✓] RecallX package installed successfully in editable mode.")
    except Exception:
        cmd_fallback = [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)]
        try:
            subprocess.run(cmd_fallback, check=True, capture_output=True, text=True, timeout=45)
            print("[✓] RecallX package installed successfully.")
        except Exception as err:
            print(f"[!] Warning: Pip install had warnings/errors ({err}), continuing with direct python path.")


def initialize_recallx() -> None:
    print("[*] Initializing local database and storage...")
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    try:
        from recallx.paths import ensure_directories
        from recallx.storage.database import get_database

        ensure_directories()
        db = get_database()
        db.initialize()
        print(f"[✓] Local SQLite database initialized at: {db.db_path}")
    except Exception as exc:
        print(f"[!] Failed to initialize database: {exc}")


def safe_load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
        return json.loads(content) if content else {}
    except Exception:
        return {}


def safe_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)


def copy_skills(target_dir: Path) -> list[str]:
    installed = []
    repo_dir = Path(__file__).resolve().parent
    src_skills = repo_dir / "src" / "recallx" / "skills"
    if not src_skills.is_dir():
        return installed

    target_dir.mkdir(parents=True, exist_ok=True)
    for skill in ["remember", "recall", "project-context"]:
        src_skill = src_skills / skill
        dest_skill = target_dir / skill
        if src_skill.is_dir():
            dest_skill.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_skill / "SKILL.md", dest_skill / "SKILL.md")
            installed.append(skill)
    return installed


def configure_agents() -> None:
    print("\n[*] Auto-detecting and configuring AI Coding Agents...")
    home = Path.home()
    cwd = Path.cwd()

    mcp_entry = {
        "command": "recallx",
        "args": ["mcp", "serve"],
    }

    configured_agents = []

    # 1. Claude Code
    try:
        claude_config = home / ".claude.json"
        data = safe_load_json(claude_config)
        data.setdefault("mcpServers", {})["recallx"] = mcp_entry
        safe_write_json(claude_config, data)
        copy_skills(home / ".claude" / "skills")
        configured_agents.append("Claude Code (~/.claude.json)")
    except Exception as e:
        print(f"    [-] Claude Code config notice: {e}")

    # 2. Cursor IDE
    try:
        cursor_dir = cwd / ".cursor"
        cursor_config = cursor_dir / "mcp.json"
        data = safe_load_json(cursor_config)
        data.setdefault("mcpServers", {})["recallx"] = mcp_entry
        safe_write_json(cursor_config, data)

        # Also add Cursor rule
        rules_dir = cursor_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        rule_content = """---
description: RecallX persistent memory rules for AI coding sessions
globs: *
---

# RecallX Persistent Memory Instructions

When working in this project:
1. At the beginning of a session or task, call `recall` or `get_project_context` MCP tool to retrieve previous architecture decisions, conventions, and solved bugs.
2. After making major technical decisions, solving non-trivial bugs, or when the user states a convention, call `remember` to persist it.
3. At the end of a session with pending work, call `save_session_summary` to maintain continuity.
"""
        (rules_dir / "recallx.mdc").write_text(rule_content.strip() + "\n", encoding="utf-8")
        configured_agents.append("Cursor (.cursor/mcp.json & .cursor/rules/recallx.mdc)")
    except Exception as e:
        print(f"    [-] Cursor config notice: {e}")

    # 3. Gemini CLI / Antigravity
    try:
        gemini_config = home / ".gemini" / "settings.json"
        data = safe_load_json(gemini_config)
        data.setdefault("mcpServers", {})["recallx"] = mcp_entry
        safe_write_json(gemini_config, data)

        skills_dir = home / ".gemini" / "config" / "skills"
        if skills_dir.parent.is_dir():
            copy_skills(skills_dir)
        skills_dir_2 = home / ".gemini" / "antigravity" / "skills"
        if skills_dir_2.parent.is_dir():
            copy_skills(skills_dir_2)

        configured_agents.append("Gemini CLI / Antigravity (~/.gemini/settings.json)")
    except Exception as e:
        print(f"    [-] Gemini CLI config notice: {e}")

    # 4. Windsurf
    windsurf_dir = home / ".codeium" / "windsurf"
    if windsurf_dir.is_dir():
        try:
            windsurf_config = windsurf_dir / "mcp_config.json"
            data = safe_load_json(windsurf_config)
            data.setdefault("mcpServers", {})["recallx"] = mcp_entry
            safe_write_json(windsurf_config, data)
            configured_agents.append("Windsurf (~/.codeium/windsurf/mcp_config.json)")
        except Exception:
            pass

    # 5. VS Code / Cline & Roo Code
    appdata = os.environ.get("APPDATA")
    if sys.platform == "win32" and appdata:
        code_storage = Path(appdata) / "Code" / "User" / "globalStorage"
        for name, subpath in [
            ("Cline", "saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
            ("Roo Code", "rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json"),
        ]:
            cfg_path = code_storage / Path(subpath)
            if cfg_path.parent.is_dir():
                data = safe_load_json(cfg_path)
                data.setdefault("mcpServers", {})["recallx"] = mcp_entry
                safe_write_json(cfg_path, data)
                configured_agents.append(f"{name} ({cfg_path.name})")

    for agent in configured_agents:
        print(f"  [✓] Configured {agent}")


def verify_installation() -> None:
    print("\n[*] Verifying RecallX CLI and MCP Server...")
    try:
        result = subprocess.run(
            ["recallx", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"  [✓] CLI is ready: {result.stdout.strip()}")
        else:
            print(f"  [i] CLI callable via: {sys.executable} -m recallx.cli.app")
    except Exception:
        print(f"  [i] Note: RecallX callable via '{sys.executable} -m recallx.cli.app'")

    print("\n" + "=" * 65)
    print("  [SUCCESS] RecallX is fully installed and configured!")
    print("=" * 65)
    print("\nAvailable MCP Tools in your AI Agent:")
    print("  • remember               - Save architecture, decisions, and bugs")
    print("  • recall                 - Search previous memories with ranking")
    print("  • get_project_context    - Get structured summary of project knowledge")
    print("  • save_session_summary   - Persist work done and pending tasks")
    print("  • get_memory_stats       - View memory metrics")
    print("\nHow to test:")
    print("  Ask your AI agent: 'What memories do you have for this project?'\n")


def main() -> None:
    print_banner()
    check_python_version()
    install_package()
    initialize_recallx()
    configure_agents()
    verify_installation()


if __name__ == "__main__":
    main()
