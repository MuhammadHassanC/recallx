"""RecallX command-line interface entrypoint.

Provides a unified, local-first persistent memory CLI for AI coding agents.
Implements lazy database initialization, structured Rich formatting, JSON output,
and zero artificial decorations or telemetry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import typer

from recallx import __version__
from recallx.cli.output import OutputFormatter
from recallx.config import get_config
from recallx.core.memory import MemoryEngine
from recallx.paths import ensure_directories, get_config_dir, get_data_dir
from recallx.storage.database import DatabaseManager, get_database
from recallx.storage.repositories import ProjectRepository
from recallx.utils.logging import get_logger, setup_logging
from recallx.utils.validation import validate_project_id

logger = get_logger("recallx.cli.app")

# Internal runtime state for CLI invocation
_cli_state: dict[str, Any] = {
    "json": False,
    "quiet": False,
    "formatter": None,
}

# Main Typer application
app = typer.Typer(
    name="recallx",
    help="RecallX — Universal local-first persistent memory for AI coding agents.",
    no_args_is_help=True,
    add_completion=False,
)

# Project sub-command group
project_app = typer.Typer(
    name="project",
    help="Manage project workspaces and namespaces.",
    no_args_is_help=True,
)
app.add_typer(project_app, name="project")

# MCP sub-command group
mcp_app = typer.Typer(
    name="mcp",
    help="Model Context Protocol (MCP) server commands.",
    no_args_is_help=True,
)
app.add_typer(mcp_app, name="mcp")


def _version_callback(value: bool) -> None:
    """Print version and exit immediately."""
    if value:
        typer.echo(f"RecallX version {__version__}")
        raise typer.Exit(code=0)


def _get_formatter(ctx: Optional[typer.Context] = None) -> OutputFormatter:
    """Obtain or instantiate the active OutputFormatter.

    Args:
        ctx: Optional Typer Context holding invocation state.

    Returns:
        Configured OutputFormatter respecting --json and --quiet flags.
    """
    if ctx and ctx.obj and isinstance(ctx.obj, dict) and ctx.obj.get("formatter"):
        return ctx.obj["formatter"]
    if _cli_state.get("formatter") is not None:
        return _cli_state["formatter"]
    return OutputFormatter(
        json_mode=_cli_state.get("json", False),
        quiet=_cli_state.get("quiet", False),
    )


def _get_engine(db_path: Optional[Path] = None) -> MemoryEngine:
    """Lazily initialize DatabaseManager and return a configured MemoryEngine.

    Args:
        db_path: Optional explicit database path override.

    Returns:
        Instantiated MemoryEngine bound to the active database.
    """
    db = get_database(db_path)
    return MemoryEngine(db)


def _detect_default_project() -> str:
    """Resolve a default project identifier from configuration or current working directory.

    Returns:
        Sanitized project identifier string.
    """
    cfg = get_config()
    if cfg.default_project:
        return cfg.default_project
    try:
        cwd_name = Path.cwd().name.strip().lower()
        return validate_project_id(cwd_name)
    except Exception:
        return "default"


def _collect_status(db: DatabaseManager) -> dict[str, Any]:
    """Collect runtime, database, and repository metrics for status inspection.

    Args:
        db: Active DatabaseManager instance.

    Returns:
        Dictionary of status metrics.
    """
    cfg = get_config()
    engine = MemoryEngine(db)
    stats = engine.get_stats()
    proj_repo = ProjectRepository(db)
    projects = proj_repo.list()

    mcp_status = "Available (FastMCP)"
    try:
        import mcp  # noqa: F401
    except ImportError:
        mcp_status = "Not installed ('pip install mcp')"

    total_m = stats.get("total_memories", stats.get("total", 0))
    archived_m = stats.get("archived_memories", stats.get("archived", 0))
    pinned_m = stats.get("pinned_memories", stats.get("pinned", 0))
    active_m = stats.get("active_memories", total_m - archived_m)

    return {
        "version": __version__,
        "database_path": str(db.db_path),
        "database_size": db.get_db_size(),
        "data_dir": str(get_data_dir()),
        "config_dir": str(get_config_dir()),
        "total_projects": len(projects),
        "total_memories": total_m,
        "active_memories": active_m,
        "pinned_memories": pinned_m,
        "archived_memories": archived_m,
        "semantic_search": cfg.enable_semantic_search,
        "embedding_model": cfg.embedding_model,
        "mcp_server": mcp_status,
    }


@app.callback()
def main_callback(
    ctx: typer.Context,
    json: bool = typer.Option(
        False,
        "--json",
        help="Format output as machine-readable JSON.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress informational console output.",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    log_level: Optional[str] = typer.Option(
        None,
        "--log-level",
        help="Set logging verbosity level.",
    ),
) -> None:
    """RecallX — Universal local-first persistent memory for AI coding agents."""
    cfg = get_config()
    _cli_state["json"] = json or cfg.json_output
    _cli_state["quiet"] = quiet or cfg.quiet
    _cli_state["formatter"] = OutputFormatter(
        json_mode=_cli_state["json"],
        quiet=_cli_state["quiet"],
    )

    ctx.obj = _cli_state

    effective_level = log_level or cfg.log_level
    setup_logging(
        level=effective_level,
        quiet=_cli_state["quiet"],
        json_format=_cli_state["json"],
    )
    ensure_directories()


# ----------------------------------------------------------------------
# Command: init
# ----------------------------------------------------------------------
@app.command("init")
def init_cmd(ctx: typer.Context) -> None:
    """Initialize RecallX directories, database, and configuration."""
    formatter = _get_formatter(ctx)
    try:
        ensure_directories()
        cfg = get_config()
        cfg.save()
        db = get_database()
        db.initialize()

        formatter.success("Initialized RecallX directories, database, and configuration.")
        status_info = _collect_status(db)
        formatter.status_display(status_info)
    except Exception as exc:
        logger.exception("Failed to initialize RecallX: %s", exc)
        formatter.error(f"Initialization failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: status
# ----------------------------------------------------------------------
@app.command("status")
def status_cmd(ctx: typer.Context) -> None:
    """Show installation, storage, and runtime status."""
    formatter = _get_formatter(ctx)
    try:
        ensure_directories()
        db = get_database()
        status_info = _collect_status(db)
        formatter.status_display(status_info)
    except Exception as exc:
        logger.exception("Error checking status: %s", exc)
        formatter.error(f"Status check failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: remember
# ----------------------------------------------------------------------
@app.command("remember")
def remember_cmd(
    ctx: typer.Context,
    content: str = typer.Argument(..., help="The information to remember."),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Project identifier (default from config or current directory).",
    ),
    type_: str = typer.Option(
        "project",
        "--type",
        "-t",
        help="Category: project, decision, bug_solution, preference, session.",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        help="Comma-separated categorization tags.",
    ),
    importance: float = typer.Option(
        0.5,
        "--importance",
        "-i",
        min=0.0,
        max=1.0,
        help="Significance score between 0.0 and 1.0.",
    ),
    source: Optional[str] = typer.Option(
        "cli",
        "--source",
        "-s",
        help="Origin identifier (e.g. cli, claude-code).",
    ),
) -> None:
    """Save a memory record to persistent storage."""
    formatter = _get_formatter(ctx)
    try:
        cfg = get_config()
        resolved_project = project or cfg.default_project or _detect_default_project()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        engine = _get_engine()
        db = get_database()
        proj_repo = ProjectRepository(db)
        if not proj_repo.exists(resolved_project):
            proj_repo.create(project_id=resolved_project, name=resolved_project)

        mem = engine.remember(
            content=content,
            project_id=resolved_project,
            memory_type=type_,
            tags=tag_list,
            importance=importance,
            source=source,
        )

        if formatter.json_mode:
            formatter.json_output(mem)
        else:
            formatter.success(
                f"Remembered memory [{mem['id']}] for project '{resolved_project}'"
            )
    except Exception as exc:
        logger.exception("Error saving memory: %s", exc)
        formatter.error(f"Failed to remember: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: search
# ----------------------------------------------------------------------
@app.command("search")
def search_cmd(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Query string to search memories."),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Filter search results by project identifier.",
    ),
    type_: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by memory type (decision, bug_solution, etc.).",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        min=1,
        max=500,
        help="Maximum results to return.",
    ),
) -> None:
    """Search stored memories by query string with relevance ranking."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        results = engine.recall(
            query=query,
            project_id=project,
            memory_type=type_,
            limit=limit,
        )
        formatter.search_results(results)
    except Exception as exc:
        logger.exception("Error searching memories: %s", exc)
        formatter.error(f"Search failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: list / list-memories
# ----------------------------------------------------------------------
@app.command("list")
def list_cmd(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Filter memories by project identifier.",
    ),
    type_: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by memory type.",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        min=1,
        max=1000,
        help="Maximum memories to list.",
    ),
    offset: int = typer.Option(
        0,
        "--offset",
        min=0,
        help="Offset for pagination.",
    ),
    pinned: bool = typer.Option(
        False,
        "--pinned",
        help="Show only pinned memories.",
    ),
    archived: bool = typer.Option(
        False,
        "--archived",
        help="Include archived memories.",
    ),
) -> None:
    """List stored memories with filtering and pagination."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        memories = engine.list_memories(
            project_id=project,
            memory_type=type_,
            is_archived=archived,
            limit=limit,
            offset=offset,
            pinned_only=pinned,
        )
        formatter.memory_table(memories, show_content=True)
    except Exception as exc:
        logger.exception("Error listing memories: %s", exc)
        formatter.error(f"List failed: {exc}")
        raise typer.Exit(code=1)


@app.command("list-memories", hidden=True)
def list_memories_alias(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Filter memories by project identifier.",
    ),
    type_: Optional[str] = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by memory type.",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        min=1,
        max=1000,
        help="Maximum memories to list.",
    ),
    offset: int = typer.Option(
        0,
        "--offset",
        min=0,
        help="Offset for pagination.",
    ),
    pinned: bool = typer.Option(
        False,
        "--pinned",
        help="Show only pinned memories.",
    ),
    archived: bool = typer.Option(
        False,
        "--archived",
        help="Include archived memories.",
    ),
) -> None:
    """Alias for 'recallx list' command."""
    list_cmd(
        ctx=ctx,
        project=project,
        type_=type_,
        limit=limit,
        offset=offset,
        pinned=pinned,
        archived=archived,
    )


# ----------------------------------------------------------------------
# Command: show
# ----------------------------------------------------------------------
@app.command("show")
def show_cmd(
    ctx: typer.Context,
    memory_id: str = typer.Argument(..., help="Short unique memory ID."),
) -> None:
    """Display full details of a specific memory record."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        mem = engine.get(memory_id)
        if mem is None:
            formatter.error(f"Memory '{memory_id}' not found.")
            raise typer.Exit(code=1)
        formatter.memory_detail(mem)
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("Error showing memory %s: %s", memory_id, exc)
        formatter.error(f"Failed to display memory: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: update
# ----------------------------------------------------------------------
@app.command("update")
def update_cmd(
    ctx: typer.Context,
    memory_id: str = typer.Argument(..., help="Memory identifier to update."),
    content: Optional[str] = typer.Option(
        None,
        "--content",
        help="New replacement content.",
    ),
    tags: Optional[str] = typer.Option(
        None,
        "--tags",
        help="New comma-separated tags.",
    ),
    importance: Optional[float] = typer.Option(
        None,
        "--importance",
        "-i",
        min=0.0,
        max=1.0,
        help="New importance score (0.0 - 1.0).",
    ),
) -> None:
    """Update fields of an existing memory."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        tag_list = (
            [t.strip() for t in tags.split(",") if t.strip()]
            if tags is not None
            else None
        )
        updated = engine.update(
            memory_id=memory_id,
            content=content,
            tags=tag_list,
            importance=importance,
        )
        if updated is None:
            formatter.error(f"Memory '{memory_id}' not found.")
            raise typer.Exit(code=1)

        if formatter.json_mode:
            formatter.json_output(updated)
        else:
            formatter.success(f"Memory '{memory_id}' updated successfully.")
            formatter.memory_detail(updated)
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("Error updating memory %s: %s", memory_id, exc)
        formatter.error(f"Failed to update memory: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: delete
# ----------------------------------------------------------------------
@app.command("delete")
def delete_cmd(
    ctx: typer.Context,
    memory_id: str = typer.Argument(..., help="Memory identifier to delete."),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Delete a memory from storage."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        mem = engine.get(memory_id)
        if mem is None:
            formatter.error(f"Memory '{memory_id}' not found.")
            raise typer.Exit(code=1)

        if not force:
            confirmed = formatter.confirm(
                f"Are you sure you want to delete memory '{memory_id}'?"
            )
            if not confirmed:
                formatter.info("Deletion cancelled.")
                raise typer.Exit(code=0)

        success = engine.forget(memory_id)
        if success:
            formatter.success(f"Deleted memory '{memory_id}'.")
        else:
            formatter.error(f"Could not delete memory '{memory_id}'.")
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("Error deleting memory %s: %s", memory_id, exc)
        formatter.error(f"Failed to delete memory: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: export
# ----------------------------------------------------------------------
@app.command("export")
def export_cmd(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Optional project identifier to filter export.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination JSON file path (defaults to stdout).",
    ),
) -> None:
    """Export memories as JSON to a file or stdout."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        json_str = engine.export_memories(
            project_id=project,
            output_path=output,
        )
        if output:
            formatter.success(f"Memories exported to: {output.resolve()}")
        else:
            if formatter.json_mode:
                formatter.json_output(json.loads(json_str))
            else:
                formatter.console.print(json_str)
    except Exception as exc:
        logger.exception("Error exporting memories: %s", exc)
        formatter.error(f"Export failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: import-memories / import
# ----------------------------------------------------------------------
@app.command("import")
def import_cmd(
    ctx: typer.Context,
    file: Path = typer.Argument(
        ...,
        help="Path to JSON file containing memories to import.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Project override for imported memories.",
    ),
) -> None:
    """Import memories from a JSON export file."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        raw_text = file.read_text(encoding="utf-8")
        results = engine.import_memories(
            data=raw_text,
            project_id=project,
        )
        if formatter.json_mode:
            formatter.json_output(results)
        else:
            formatter.success(
                f"Import complete: {results.get('imported', 0)} imported, "
                f"{results.get('skipped', 0)} skipped, {results.get('errors', 0)} errors."
            )
    except Exception as exc:
        logger.exception("Error importing memories from %s: %s", file, exc)
        formatter.error(f"Import failed: {exc}")
        raise typer.Exit(code=1)


@app.command("import-memories", hidden=True)
def import_memories_alias(
    ctx: typer.Context,
    file: Path = typer.Argument(
        ...,
        help="Path to JSON file containing memories to import.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Project override for imported memories.",
    ),
) -> None:
    """Alias for 'recallx import' command."""
    import_cmd(ctx=ctx, file=file, project=project)


# ----------------------------------------------------------------------
# Command: backup
# ----------------------------------------------------------------------
@app.command("backup")
def backup_cmd(
    ctx: typer.Context,
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional destination path for backup database file.",
    ),
) -> None:
    """Create a hot backup of the RecallX database."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        dest = engine.backup(dest_path=output)
        if formatter.json_mode:
            formatter.json_output({"status": "success", "backup_path": str(dest)})
        else:
            formatter.success(f"Database backup created at: {dest}")
    except Exception as exc:
        logger.exception("Error creating database backup: %s", exc)
        formatter.error(f"Backup failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: stats
# ----------------------------------------------------------------------
@app.command("stats")
def stats_cmd(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Optional project identifier to filter statistics.",
    ),
) -> None:
    """Display memory storage metrics and category breakdown."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        stats = engine.get_stats(project_id=project)
        formatter.stats_display(stats)
    except Exception as exc:
        logger.exception("Error fetching stats: %s", exc)
        formatter.error(f"Stats failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: integrate
# ----------------------------------------------------------------------
@app.command("integrate")
def integrate_cmd(
    ctx: typer.Context,
    agent: Optional[str] = typer.Argument(
        None,
        help="Agent identifier: claude-code, cursor, gemini-cli, codex, opencode.",
    ),
    list_: bool = typer.Option(
        False,
        "--list",
        help="List all supported AI agent integrations.",
    ),
) -> None:
    """Generate and display agent configuration blocks for MCP integration."""
    formatter = _get_formatter(ctx)
    try:
        from recallx.integrations.registry import (
            CANONICAL_INTEGRATIONS,
            get_all_configs,
            get_integration,
        )

        if list_ or agent is None:
            if formatter.json_mode:
                formatter.json_output(get_all_configs())
                return

            from rich import box
            from rich.table import Table

            table = Table(
                title="Supported Agent Integrations",
                box=box.ROUNDED,
                header_style="bold cyan",
            )
            table.add_column("Agent Identifier", style="bold cyan")
            table.add_column("Description", style="white")
            table.add_column("Integration Command", style="green")

            descriptions = {
                "claude-code": "Anthropic Claude Code CLI (~/.claude.json)",
                "cursor": "Cursor AI IDE (.cursor/mcp.json)",
                "gemini-cli": "Google Gemini CLI / Antigravity integration",
                "codex": "OpenAI Codex agent environment",
                "opencode": "OpenCode agent configuration",
            }

            for name in CANONICAL_INTEGRATIONS:
                table.add_row(
                    name,
                    descriptions.get(name, "MCP agent integration"),
                    f"recallx integrate {name}",
                )

            formatter.console.print(table)
            formatter.console.print(
                "\nRun [bold green]recallx integrate <agent>[/bold green] to view specific setup configuration."
            )
            return

        try:
            mod = get_integration(agent)
        except ValueError as ve:
            formatter.error(str(ve))
            raise typer.Exit(code=1)

        cfg_dict = mod.get_config()
        instructions = mod.get_instructions() if hasattr(mod, "get_instructions") else ""

        if formatter.json_mode:
            formatter.json_output(cfg_dict)
            return

        from rich import box
        from rich.panel import Panel
        from rich.syntax import Syntax

        formatted_json = json.dumps(cfg_dict, indent=2)
        syntax = Syntax(formatted_json, "json", theme="monokai", line_numbers=False)

        panel = Panel(
            syntax,
            title=f"Configuration for {agent}",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        formatter.console.print(panel)

        if instructions:
            formatter.console.print("\n[bold cyan]Setup Instructions:[/bold cyan]")
            formatter.console.print(instructions.strip())
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("Error in integrate command: %s", exc)
        formatter.error(f"Integration command failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Command: setup
# ----------------------------------------------------------------------
@app.command("setup")
def setup_cmd(
    ctx: typer.Context,
    agent: Optional[str] = typer.Option(
        None,
        "--agent",
        "-a",
        help="Target agent to configure (e.g. claude-code, cursor, gemini, or all).",
    ),
) -> None:
    """Automatically configure detected AI coding agents with RecallX MCP server and skills."""
    formatter = _get_formatter(ctx)
    try:
        from recallx.integrations.installer import (
            setup_all_agents,
            setup_claude_code,
            setup_cursor,
            setup_gemini_antigravity,
        )

        target = agent.lower().strip() if agent else "all"
        if target in ("claude", "claude-code"):
            results = [setup_claude_code()]
        elif target == "cursor":
            results = [setup_cursor()]
        elif target in ("gemini", "antigravity"):
            results = [setup_gemini_antigravity()]
        else:
            results = setup_all_agents()

        if formatter.json_mode:
            formatter.json_output([
                {
                    "agent": r.agent_name,
                    "configured": r.configured,
                    "config_file": str(r.config_file) if r.config_file else None,
                    "skills": r.skills_installed,
                    "message": r.message,
                }
                for r in results
            ])
            return

        formatter.success("RecallX agent auto-configuration completed.")
        for res in results:
            if res.configured:
                formatter.info(f"{res.agent_name}: {res.message}")
            else:
                formatter.warning(f"{res.agent_name}: Skipped / Not detected")
    except Exception as exc:
        logger.exception("Error during agent setup: %s", exc)
        formatter.error(f"Setup failed: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# Project Sub-Commands
# ----------------------------------------------------------------------
@project_app.command("init")
def project_init_cmd(
    ctx: typer.Context,
    project_id: str = typer.Argument(
        ...,
        help="Unique project identifier (e.g. 'my-api', 'frontend-app').",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        help="Human-readable project display name.",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="Brief description of the project.",
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        help="Filesystem root path of the project workspace.",
    ),
) -> None:
    """Initialize or register a project namespace."""
    formatter = _get_formatter(ctx)
    try:
        db = get_database()
        repo = ProjectRepository(db)
        display_name = name or project_id
        resolved_path = path.resolve().as_posix() if path else None

        if repo.exists(project_id):
            proj = repo.update(
                project_id,
                {
                    "name": display_name,
                    "description": description,
                    "path": resolved_path,
                },
            )
            action = "Updated existing"
        else:
            proj = repo.create(
                project_id=project_id,
                name=display_name,
                description=description,
                path=resolved_path,
            )
            action = "Initialized"

        if formatter.json_mode:
            formatter.json_output(proj)
        else:
            formatter.success(f"{action} project '{project_id}'.")
    except Exception as exc:
        logger.exception("Error initializing project %s: %s", project_id, exc)
        formatter.error(f"Failed to initialize project: {exc}")
        raise typer.Exit(code=1)


@project_app.command("context")
def project_context_cmd(
    ctx: typer.Context,
    project_id: str = typer.Argument(
        ...,
        help="Project identifier to inspect context for.",
    ),
) -> None:
    """Display comprehensive memory context for a project."""
    formatter = _get_formatter(ctx)
    try:
        engine = _get_engine()
        context_data = engine.get_project_context(project_id)
        formatter.project_context(context_data)
    except Exception as exc:
        logger.exception("Error retrieving context for %s: %s", project_id, exc)
        formatter.error(f"Failed to retrieve project context: {exc}")
        raise typer.Exit(code=1)


@project_app.command("list")
def project_list_cmd(ctx: typer.Context) -> None:
    """List all registered project namespaces."""
    formatter = _get_formatter(ctx)
    try:
        db = get_database()
        repo = ProjectRepository(db)
        projects = repo.list()

        if formatter.json_mode:
            formatter.json_output(projects)
            return

        if not projects:
            formatter.info(
                "No projects registered yet. Use 'recallx project init <id>' to create one."
            )
            return

        from rich import box
        from rich.table import Table

        table = Table(
            title="Registered Projects",
            box=box.ROUNDED,
            header_style="bold cyan",
        )
        table.add_column("Project ID", style="bold cyan")
        table.add_column("Name", style="white")
        table.add_column("Description", style="dim")
        table.add_column("Path", style="blue")
        table.add_column("Created", style="dim")

        for p in projects:
            created_val = str(p.get("created_at") or "")
            if "T" in created_val:
                created_date = created_val.split("T")[0]
            else:
                created_date = created_val[:10]

            table.add_row(
                str(p.get("id", "")),
                str(p.get("name", "")),
                str(p.get("description") or "-"),
                str(p.get("path") or "-"),
                created_date,
            )

        formatter.console.print(table)
    except Exception as exc:
        logger.exception("Error listing projects: %s", exc)
        formatter.error(f"Failed to list projects: {exc}")
        raise typer.Exit(code=1)


# ----------------------------------------------------------------------
# MCP Sub-Commands
# ----------------------------------------------------------------------
@mcp_app.command("serve")
def mcp_serve_cmd(ctx: typer.Context) -> None:
    """Start the RecallX MCP server over stdio transport."""
    formatter = _get_formatter(ctx)
    try:
        try:
            from recallx.mcp.server import main as mcp_main

            mcp_main()
        except ImportError:
            try:
                from recallx.mcp.server import mcp

                mcp.run(transport="stdio")
            except ImportError as ie:
                formatter.error(f"RecallX MCP server module is not available: {ie}")
                raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as exc:
        logger.exception("MCP server run failure: %s", exc)
        formatter.error(f"MCP server execution failed: {exc}")
        raise typer.Exit(code=1)


@mcp_app.command("info")
def mcp_info_cmd(ctx: typer.Context) -> None:
    """Show Model Context Protocol (MCP) server configuration and capabilities."""
    formatter = _get_formatter(ctx)
    try:
        info_data: dict[str, Any] = {
            "name": "RecallX",
            "version": __version__,
            "protocol": "Model Context Protocol (MCP)",
            "transport": "stdio",
            "command": "recallx mcp serve",
            "tools": [
                {"name": "remember", "description": "Save persistent memory to project"},
                {"name": "recall", "description": "Search relevant memories via hybrid retrieval"},
                {"name": "get", "description": "Retrieve specific memory by ID"},
                {"name": "update", "description": "Update an existing memory"},
                {"name": "forget", "description": "Delete a memory by ID"},
                {"name": "list_memories", "description": "List memories by project/type"},
                {"name": "get_project_context", "description": "Retrieve prioritized project context"},
                {"name": "save_session_summary", "description": "Record session summary memory"},
            ],
            "resources": [
                {"uri": "project://{project_id}/context", "description": "Project context"},
                {"uri": "memory://{memory_id}", "description": "Memory item"},
            ],
        }

        if formatter.json_mode:
            formatter.json_output(info_data)
            return

        from rich import box
        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Property", style="bold cyan", width=18)
        table.add_column("Value", style="white")

        table.add_row("Server Name", "RecallX")
        table.add_row("Version", f"v{__version__}")
        table.add_row("Transport", "Standard I/O (stdio)")
        table.add_row("Launch Command", "[bold green]recallx mcp serve[/bold green]")

        tools_str = ", ".join(t["name"] for t in info_data["tools"])
        table.add_row("Tools", tools_str)

        panel = Panel(
            table,
            title="RecallX MCP Configuration",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        formatter.console.print(panel)
    except Exception as exc:
        logger.exception("Error displaying MCP info: %s", exc)
        formatter.error(f"Failed to display MCP info: {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
