"""Output formatting using Rich for RecallX CLI.

Provides clean, minimal, high-precision terminal presentation per institutional
developer standards without decorative emojis, sparkles, or artificial buzzwords.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text


def _format_size(size_bytes: int | float | None) -> str:
    """Format bytes into human-readable unit string.

    Args:
        size_bytes: Byte count or None.

    Returns:
        Formatted string (e.g. '24.0 KB').
    """
    if size_bytes is None or size_bytes <= 0:
        return "0 B"

    num = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024.0 or unit == "TB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} TB"


def _json_serial(obj: Any) -> Any:
    """JSON serializer helper for non-standard types."""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


class OutputFormatter:
    """Renders structured RecallX data using Rich console components or JSON."""

    def __init__(
        self,
        json_mode: bool = False,
        quiet: bool = False,
        console: Console | None = None,
    ) -> None:
        """Initialize the formatter.

        Args:
            json_mode: When True, structured data outputs as pure formatted JSON.
            quiet: When True, suppresses informational and success messages.
            console: Optional custom Rich Console instance.
        """
        self.json_mode: bool = json_mode
        self.quiet: bool = quiet
        self.console: Console = console or Console(highlight=False)
        self._stderr_console: Console = Console(stderr=True, highlight=False)

    def success(self, message: str) -> None:
        """Display a success message with green checkmark.

        Args:
            message: Informational success string.
        """
        if self.json_mode:
            return
        if not self.quiet:
            self.console.print(f"[bold green]✓[/bold green] {escape(message)}")

    def error(self, message: str) -> None:
        """Display an error message with red X to stderr.

        Args:
            message: Error description string.
        """
        if self.json_mode:
            self.json_output({"status": "error", "message": message})
        else:
            self._stderr_console.print(f"[bold red]✗[/bold red] {escape(message)}")

    def warning(self, message: str) -> None:
        """Display a warning message with yellow marker.

        Args:
            message: Warning text.
        """
        if self.json_mode:
            return
        if not self.quiet:
            self.console.print(f"[bold yellow]![/bold yellow] {escape(message)}")

    def info(self, message: str) -> None:
        """Display an informational message with blue indicator.

        Args:
            message: Information text.
        """
        if self.json_mode:
            return
        if not self.quiet:
            self.console.print(f"[bold blue]i[/bold blue] {escape(message)}")

    def json_output(self, data: Any) -> None:
        """Output raw formatted JSON to stdout.

        Args:
            data: Arbitrary serializable data object or structure.
        """
        formatted = json.dumps(data, indent=2, default=_json_serial)
        print(formatted)

    def confirm(self, message: str) -> bool:
        """Prompt the user for interactive confirmation.

        Args:
            message: Confirmation prompt question.

        Returns:
            True if confirmed by user, False otherwise.
        """
        if self.quiet:
            return False
        return bool(Confirm.ask(message, console=self.console, default=False))

    def memory_table(
        self,
        memories: list[dict[str, Any]],
        show_content: bool = True,
    ) -> None:
        """Display a collection of memories in a clean tabular view.

        Args:
            memories: List of memory dictionaries.
            show_content: Whether to include truncated content column.
        """
        if self.json_mode:
            self.json_output(memories)
            return

        if not memories:
            if not self.quiet:
                self.info("No memories found.")
            return

        table = Table(
            box=box.ROUNDED,
            header_style="bold cyan",
            row_styles=["none", "dim"],
            show_edge=True,
            pad_edge=True,
            padding=(0, 1),
        )

        table.add_column("ID", style="bold cyan", no_wrap=True, max_width=12)
        table.add_column("Type", style="magenta", no_wrap=True, max_width=14)
        table.add_column("Project", style="blue", no_wrap=True, max_width=14)
        if show_content:
            table.add_column("Content", style="white", no_wrap=True, max_width=45)
        table.add_column("Imp", justify="right", style="yellow", no_wrap=True, width=5)
        table.add_column("Tags", style="green", no_wrap=True, max_width=20)
        table.add_column("Created", style="dim", no_wrap=True, width=10)

        for mem in memories:
            mem_id = str(mem.get("id", ""))
            if mem.get("is_pinned"):
                mem_id = f"★ {mem_id}"

            m_type = str(mem.get("memory_type", "project")).replace("_", " ")

            project = str(mem.get("project_id", ""))

            importance_val = float(mem.get("importance", 0.5))
            importance = f"{importance_val:.2f}"

            tags_list = mem.get("tags") or []
            tags = ", ".join(str(t) for t in tags_list) if tags_list else "-"

            created_val = str(mem.get("created_at") or "")
            if "T" in created_val:
                created_date = created_val.split("T")[0]
            else:
                created_date = created_val[:10]

            row: list[str] = [mem_id, m_type, project]

            if show_content:
                raw_content = str(mem.get("content", "")).replace("\r", "").replace("\n", " ")
                if len(raw_content) > 65:
                    clean_content = raw_content[:62].rstrip() + "..."
                else:
                    clean_content = raw_content
                row.append(clean_content)

            row.extend([importance, tags, created_date])
            table.add_row(*row)

        self.console.print(table)

    def memory_detail(self, memory: dict[str, Any]) -> None:
        """Display exhaustive memory details inside a clean panel.

        Args:
            memory: Dictionary representing a single memory record.
        """
        if self.json_mode:
            self.json_output(memory)
            return

        mem_id = str(memory.get("id", "Unknown"))
        is_pinned = bool(memory.get("is_pinned", False))
        is_archived = bool(memory.get("is_archived", False))

        # Metadata grid
        meta_table = Table(
            show_header=False,
            box=None,
            pad_edge=False,
            collapse_padding=True,
            padding=(0, 2),
        )
        meta_table.add_column("Key", style="bold cyan", width=16)
        meta_table.add_column("Value", style="white")

        meta_table.add_row("ID", mem_id)
        meta_table.add_row("Type", str(memory.get("memory_type", "")).replace("_", " ").title())
        meta_table.add_row("Project", str(memory.get("project_id", "")))
        meta_table.add_row(
            "Importance",
            f"{float(memory.get('importance', 0.5)):.2f}",
        )
        meta_table.add_row(
            "Confidence",
            f"{float(memory.get('confidence', 0.7)):.2f}",
        )
        meta_table.add_row("Pinned", "Yes (★)" if is_pinned else "No")
        meta_table.add_row("Archived", "Yes" if is_archived else "No")

        tags = memory.get("tags") or []
        meta_table.add_row("Tags", ", ".join(str(t) for t in tags) if tags else "None")

        meta_table.add_row("Source", str(memory.get("source") or "None"))
        meta_table.add_row("Content Hash", str(memory.get("content_hash") or "n/a"))
        meta_table.add_row("Created At", str(memory.get("created_at") or "n/a"))
        meta_table.add_row("Updated At", str(memory.get("updated_at") or "n/a"))
        meta_table.add_row("Accessed At", str(memory.get("accessed_at") or "n/a"))

        expires = memory.get("expires_at")
        if expires:
            meta_table.add_row("Expires At", str(expires))

        custom_meta = memory.get("metadata") or memory.get("metadata_json") or {}
        if custom_meta:
            meta_table.add_row("Metadata", json.dumps(custom_meta, default=_json_serial))

        content_body = str(memory.get("content", "")).strip()

        detail_content = Text()
        detail_content.append("CONTENT\n", style="bold green")
        detail_content.append(content_body, style="white")

        title = f"Memory: {mem_id}" + (" [pinned]" if is_pinned else "")
        panel = Panel(
            self.console.render_str(
                f"{self._render_table_str(meta_table)}\n\n[bold green]CONTENT[/bold green]\n{content_body}"
            ),
            title=title,
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self.console.print(panel)

    def _render_table_str(self, table: Table) -> str:
        """Render a Rich Table to ANSI/Rich string for panel embedding."""
        with self.console.capture() as capture:
            self.console.print(table)
        return capture.get().rstrip()

    def search_results(self, results: list[dict[str, Any]]) -> None:
        """Display search results with relevance scores and matching content.

        Args:
            results: List of memory search result dictionaries with score fields.
        """
        if self.json_mode:
            self.json_output(results)
            return

        if not results:
            if not self.quiet:
                self.info("No matching memories found.")
            return

        self.console.print(f"[dim]Found {len(results)} matching results:[/dim]\n")

        for res in results:
            # Score resolution (score, relevance, or rank fallback)
            score_val = res.get("score")
            if score_val is None:
                score_val = res.get("relevance", 1.0)
            score = float(score_val)
            score_formatted = f"[{score:.2f}]"

            if score >= 0.8:
                score_badge = f"[bold green]{score_formatted}[/bold green]"
            elif score >= 0.5:
                score_badge = f"[bold yellow]{score_formatted}[/bold yellow]"
            else:
                score_badge = f"[dim]{score_formatted}[/dim]"

            content_text = str(res.get("content", "")).strip()
            first_line = content_text.split("\n")[0]
            if len(first_line) > 80:
                first_line = first_line[:77].rstrip() + "..."

            m_type = str(res.get("memory_type", "project")).replace("_", " ").title()
            project = str(res.get("project_id", "default"))
            mem_id = str(res.get("id", ""))

            self.console.print(f"{score_badge} [bold white]{first_line}[/bold white]")

            meta_line = (
                f"  Type: [magenta]{m_type}[/magenta] | "
                f"Project: [blue]{project}[/blue] | "
                f"ID: [dim]{mem_id}[/dim]"
            )
            tags = res.get("tags") or []
            if tags:
                meta_line += f" | Tags: [green]{', '.join(str(t) for t in tags)}[/green]"

            self.console.print(meta_line)
            self.console.print()

    def status_display(self, status: dict[str, Any]) -> None:
        """Render installation, storage, and system status panel.

        Args:
            status: Status information dictionary.
        """
        if self.json_mode:
            self.json_output(status)
            return

        version = str(status.get("version", "1.0.0"))
        db_path = str(status.get("database_path", "n/a"))
        db_size = status.get("database_size", 0)
        formatted_db_size = _format_size(db_size)

        table = Table(
            show_header=False,
            box=None,
            pad_edge=False,
            collapse_padding=True,
            padding=(0, 2),
        )
        table.add_column("Key", style="bold cyan", width=22)
        table.add_column("Value", style="white")

        table.add_row("RecallX Version", f"v{version}")
        table.add_row("Database Location", f"{db_path} ({formatted_db_size})")
        table.add_row("Data Directory", str(status.get("data_dir", "n/a")))
        table.add_row("Config Directory", str(status.get("config_dir", "n/a")))
        table.add_row("Projects Registered", str(status.get("total_projects", 0)))

        # Memory counts
        total_mem = status.get("total_memories", 0)
        pinned_mem = status.get("pinned_memories")
        archived_mem = status.get("archived_memories")
        mem_summary = f"{total_mem}"
        if pinned_mem is not None or archived_mem is not None:
            details = []
            if pinned_mem:
                details.append(f"{pinned_mem} pinned")
            if archived_mem:
                details.append(f"{archived_mem} archived")
            if details:
                mem_summary += f" ({', '.join(details)})"
        table.add_row("Total Memories", mem_summary)

        # Semantic search
        semantic_enabled = bool(status.get("semantic_search", False))
        embed_model = str(status.get("embedding_model", "all-MiniLM-L6-v2"))
        semantic_status = (
            f"[green]Enabled[/green] ({embed_model})"
            if semantic_enabled
            else f"[dim]Disabled[/dim] ({embed_model})"
        )
        table.add_row("Semantic Retrieval", semantic_status)

        # MCP status
        mcp_avail = status.get("mcp_server", "Available")
        table.add_row("MCP Server", str(mcp_avail))

        panel = Panel(
            table,
            title="RecallX Status",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self.console.print(panel)

    def stats_display(self, stats: dict[str, Any]) -> None:
        """Render detailed memory storage statistics table.

        Args:
            stats: Dictionary containing aggregate counts and category breakdowns.
        """
        if self.json_mode:
            self.json_output(stats)
            return

        total = stats.get("total_memories", stats.get("total", 0))
        pinned = stats.get("pinned_memories", stats.get("pinned", 0))
        archived = stats.get("archived_memories", stats.get("archived", 0))
        active = stats.get("active_memories", total - archived)

        table = Table(
            title="Memory Storage Statistics",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_edge=True,
        )
        table.add_column("Category", style="bold white")
        table.add_column("Count", justify="right", style="yellow")
        table.add_column("Notes", style="dim")

        table.add_row("Total Memories", str(total), "All recorded items")
        table.add_row(
            "Active Memories",
            str(active),
            "Available in default recall",
        )
        table.add_row("Pinned Memories", str(pinned), "Prioritized context")
        table.add_row("Archived Memories", str(archived), "Excluded from default recall")

        by_type = stats.get("by_type") or stats.get("counts_by_type") or {}
        if by_type:
            table.add_section()
            for m_type, count in sorted(by_type.items()):
                type_name = m_type.replace("_", " ").title()
                table.add_row(f"Type: {type_name}", str(count), "Category breakdown")

        by_project = stats.get("by_project") or stats.get("projects") or {}
        if isinstance(by_project, dict) and by_project:
            table.add_section()
            for project_id, count in sorted(by_project.items()):
                table.add_row(f"Project: {project_id}", str(count), "Workspace partition")
        elif isinstance(by_project, list) and by_project:
            table.add_section()
            for project_id in sorted(by_project):
                table.add_row(f"Project: {project_id}", "-", "Active workspace")

        self.console.print(table)

    def project_context(self, context: dict[str, Any]) -> None:
        """Render formatted project context overview.

        Args:
            context: Dictionary containing project_id, total_memories, and memories_by_type.
        """
        if self.json_mode:
            self.json_output(context)
            return

        project_id = str(context.get("project_id", "Unknown"))
        total = context.get("total_memories", 0)
        memories_by_type: dict[str, list[dict[str, Any]]] = context.get("memories_by_type", {})

        self.console.print(
            f"[bold cyan]Project Context:[/bold cyan] [bold white]{project_id}[/bold white] "
            f"([dim]{total} total memories[/dim])\n"
        )

        type_order = ["decision", "project", "bug_solution", "preference", "session"]
        type_labels = {
            "decision": "Technical Decisions",
            "project": "Project Knowledge & Architecture",
            "bug_solution": "Bug Solutions & Workarounds",
            "preference": "Developer Preferences",
            "session": "Recent Sessions",
        }

        # Include any extra types
        all_types = list(type_order)
        for t in memories_by_type:
            if t not in all_types:
                all_types.append(t)

        displayed_any = False
        for t in all_types:
            memories = memories_by_type.get(t, [])
            if not memories:
                continue

            displayed_any = True
            label = type_labels.get(t, t.replace("_", " ").title())
            self.console.print(f"[bold magenta]{label}[/bold magenta] ({len(memories)}):")

            for mem in memories:
                is_pinned = bool(mem.get("is_pinned", False))
                marker = "[bold yellow]★[/bold yellow] " if is_pinned else "• "
                content_text = str(mem.get("content", "")).strip()

                lines = content_text.split("\n")
                first_line = lines[0]

                tags = mem.get("tags") or []
                tag_str = f" [dim green]({', '.join(str(x) for x in tags)})[/dim green]" if tags else ""

                self.console.print(f"  {marker}[bold white]{first_line}[/bold white]{tag_str}")
                for extra_line in lines[1:4]:
                    self.console.print(f"    [dim]{extra_line}[/dim]")
                if len(lines) > 4:
                    self.console.print(f"    [dim]... (+{len(lines) - 4} lines)[/dim]")

            self.console.print()

        if not displayed_any:
            self.console.print("[dim]No memories recorded for this project yet.[/dim]\n")
