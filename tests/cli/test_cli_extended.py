"""Extended CLI unit and integration tests for RecallX.

Tests project subcommands, MCP commands, integrate commands, update, backup,
import/export, json mode, and quiet mode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from recallx.cli.app import app
from recallx.config import get_config


@pytest.fixture
def cli_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    """Provide isolated environment for CLI testing."""
    monkeypatch.setenv("RECALLX_DATA_DIR", str(tmp_path))
    get_config(reload=True)
    runner = CliRunner()
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    return runner


def test_remember_and_show_json(cli_runner: CliRunner) -> None:
    """Test remember and show with --json flag."""
    res = cli_runner.invoke(
        app,
        [
            "--json",
            "remember",
            "JSON memory test item",
            "-p",
            "json-proj",
            "-t",
            "decision",
            "--tags",
            "test,json",
            "-i",
            "0.9",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["content"] == "JSON memory test item"
    mem_id = data["id"]

    res_show = cli_runner.invoke(app, ["--json", "show", mem_id])
    assert res_show.exit_code == 0
    show_data = json.loads(res_show.stdout)
    assert show_data["id"] == mem_id
    assert show_data["importance"] == 0.9


def test_update_memory(cli_runner: CliRunner) -> None:
    """Test updating memory content, tags, and importance."""
    res = cli_runner.invoke(
        app,
        ["--json", "remember", "Original text", "-p", "upd-proj"],
    )
    assert res.exit_code == 0
    mem_id = json.loads(res.stdout)["id"]

    res_upd = cli_runner.invoke(
        app,
        ["update", mem_id, "--content", "Updated text", "--tags", "newtag", "-i", "0.75"],
    )
    assert res_upd.exit_code == 0
    assert "updated successfully" in res_upd.stdout.lower()

    res_show = cli_runner.invoke(app, ["--json", "show", mem_id])
    assert res_show.exit_code == 0
    upd_data = json.loads(res_show.stdout)
    assert upd_data["content"] == "Updated text"
    assert "newtag" in upd_data["tags"]
    assert upd_data["importance"] == 0.75


def test_project_subcommands(cli_runner: CliRunner, tmp_path: Path) -> None:
    """Test project init, list, and context commands."""
    res_init = cli_runner.invoke(
        app,
        [
            "project",
            "init",
            "my-service",
            "--name",
            "My Service Name",
            "-d",
            "Microservice description",
            "--path",
            str(tmp_path),
        ],
    )
    assert res_init.exit_code == 0
    assert "project 'my-service'" in res_init.stdout

    # List projects
    res_list = cli_runner.invoke(app, ["project", "list"])
    assert res_list.exit_code == 0
    assert "my-service" in res_list.stdout

    # List projects --json
    res_list_json = cli_runner.invoke(app, ["--json", "project", "list"])
    assert res_list_json.exit_code == 0
    projects = json.loads(res_list_json.stdout)
    assert any(p["id"] == "my-service" for p in projects)

    # Project context
    cli_runner.invoke(
        app,
        ["remember", "Context decision item", "-p", "my-service", "-t", "decision"],
    )
    res_ctx = cli_runner.invoke(app, ["project", "context", "my-service"])
    assert res_ctx.exit_code == 0
    assert "my-service" in res_ctx.stdout
    assert "Context decision item" in res_ctx.stdout


def test_mcp_info_command(cli_runner: CliRunner) -> None:
    """Test mcp info command in both text and JSON modes."""
    res = cli_runner.invoke(app, ["mcp", "info"])
    assert res.exit_code == 0
    assert "RecallX" in res.stdout
    assert "remember" in res.stdout

    res_json = cli_runner.invoke(app, ["--json", "mcp", "info"])
    assert res_json.exit_code == 0
    info = json.loads(res_json.stdout)
    assert info["name"] == "RecallX"
    assert any(t["name"] == "remember" for t in info["tools"])


def test_integrate_commands(cli_runner: CliRunner) -> None:
    """Test integrate --list and specific agent integration configs."""
    res_list = cli_runner.invoke(app, ["integrate", "--list"])
    assert res_list.exit_code == 0
    assert "claude-code" in res_list.stdout
    assert "cursor" in res_list.stdout

    res_agent = cli_runner.invoke(app, ["integrate", "cursor"])
    assert res_agent.exit_code == 0
    assert "mcpServers" in res_agent.stdout

    res_json = cli_runner.invoke(app, ["--json", "integrate", "claude-code"])
    assert res_json.exit_code == 0
    cfg = json.loads(res_json.stdout)
    assert "mcpServers" in cfg


def test_backup_and_import(cli_runner: CliRunner, tmp_path: Path) -> None:
    """Test database backup and memory import commands."""
    cli_runner.invoke(
        app,
        ["remember", "Memory to be backed up and imported", "-p", "bk-proj"],
    )

    backup_dest = tmp_path / "test_backup.db"
    res_bk = cli_runner.invoke(app, ["backup", "-o", str(backup_dest)])
    assert res_bk.exit_code == 0
    assert backup_dest.is_file()

    # Export to json
    export_dest = tmp_path / "export_data.json"
    res_exp = cli_runner.invoke(app, ["export", "-p", "bk-proj", "-o", str(export_dest)])
    assert res_exp.exit_code == 0
    assert export_dest.is_file()

    # Import from json
    res_imp = cli_runner.invoke(app, ["import", str(export_dest), "-p", "imported-proj"])
    assert res_imp.exit_code == 0
    assert "Import complete" in res_imp.stdout


def test_stats_command(cli_runner: CliRunner) -> None:
    """Test stats command."""
    cli_runner.invoke(app, ["remember", "Stats item 1", "-p", "stats-proj", "-t", "decision"])
    res = cli_runner.invoke(app, ["stats", "-p", "stats-proj"])
    assert res.exit_code == 0
    assert "Total Memories" in res.stdout

    res_json = cli_runner.invoke(app, ["--json", "stats"])
    assert res_json.exit_code == 0
    stats_data = json.loads(res_json.stdout)
    assert "total" in stats_data or "total_memories" in stats_data
