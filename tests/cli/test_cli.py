"""CLI command tests using Typer's CliRunner."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from recallx.cli.app import _get_engine, app
from recallx.config import get_config


@pytest.fixture
def cli_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    """Set up isolated data directory and CliRunner."""
    monkeypatch.setenv("RECALLX_DATA_DIR", str(tmp_path))
    get_config(reload=True)
    runner = CliRunner()
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    return runner


def test_init_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure init command creates directories and default config."""
    monkeypatch.setenv("RECALLX_DATA_DIR", str(tmp_path))
    get_config(reload=True)
    runner = CliRunner()
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "initialized" in result.output.lower()


def test_status_command(cli_runner: CliRunner) -> None:
    """Ensure status command displays environment paths and status."""
    result = cli_runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "RecallX" in result.output


def test_remember_command(cli_runner: CliRunner) -> None:
    """Ensure remember command records a new memory."""
    result = cli_runner.invoke(
        app,
        [
            "remember",
            "Using PostgreSQL with SQLAlchemy for API backend",
            "-p",
            "test-cli-proj",
            "--tags",
            "database,sql",
            "-i",
            "0.8",
        ],
    )

    assert result.exit_code == 0
    assert "test-cli-proj" in result.output


def test_search_command(cli_runner: CliRunner) -> None:
    """Ensure search command finds matching saved memories."""
    cli_runner.invoke(
        app,
        [
            "remember",
            "PostgreSQL database clustering and replication",
            "-p",
            "search-cli-proj",
        ],
    )

    result = cli_runner.invoke(app, ["search", "PostgreSQL", "-p", "search-cli-proj"])

    assert result.exit_code == 0
    assert "PostgreSQL" in result.output


def test_list_command(cli_runner: CliRunner) -> None:
    """Ensure list command outputs recorded memories in tabular view."""
    cli_runner.invoke(
        app,
        [
            "remember",
            "List command test memory item content",
            "-p",
            "list-cli-proj",
        ],
    )

    result = cli_runner.invoke(app, ["list", "-p", "list-cli-proj"])

    assert result.exit_code == 0
    assert "test memory" in result.output


def test_show_command(cli_runner: CliRunner) -> None:
    """Ensure show command prints detailed view of a specific memory ID."""
    cli_runner.invoke(
        app,
        [
            "remember",
            "Unique detailed memory body for show test",
            "-p",
            "show-cli-proj",
        ],
    )

    engine = _get_engine()
    mems = engine.list_memories(project_id="show-cli-proj")
    assert len(mems) >= 1
    mem_id = mems[0]["id"]

    result = cli_runner.invoke(app, ["show", mem_id])

    assert result.exit_code == 0
    assert mem_id in result.output
    assert "Unique detailed memory body" in result.output


def test_delete_command_with_force(cli_runner: CliRunner) -> None:
    """Ensure delete command with --force removes memory without prompting."""
    cli_runner.invoke(
        app,
        [
            "remember",
            "Memory marked for deletion",
            "-p",
            "del-cli-proj",
        ],
    )

    engine = _get_engine()
    mems = engine.list_memories(project_id="del-cli-proj")
    assert len(mems) >= 1
    mem_id = mems[0]["id"]

    result = cli_runner.invoke(app, ["delete", mem_id, "--force"])

    assert result.exit_code == 0
    assert mem_id in result.output
    assert "deleted" in result.output.lower()


def test_export_command(cli_runner: CliRunner, tmp_path: Path) -> None:
    """Ensure export command serializes memories to file."""
    cli_runner.invoke(
        app,
        [
            "remember",
            "Memory to export via CLI flag",
            "-p",
            "exp-cli-proj",
        ],
    )

    dest_file = tmp_path / "cli_exported.json"
    result = cli_runner.invoke(app, ["export", "-p", "exp-cli-proj", "-o", str(dest_file)])

    assert result.exit_code == 0
    assert dest_file.is_file()
    assert "Memory to export" in dest_file.read_text(encoding="utf-8")


def test_version_flag(cli_runner: CliRunner) -> None:
    """Ensure --version flag prints the application version and exits."""
    result = cli_runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "RecallX version" in result.output


def test_help_flag(cli_runner: CliRunner) -> None:
    """Ensure --help flag prints usage help."""
    result = cli_runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "RecallX" in result.output
