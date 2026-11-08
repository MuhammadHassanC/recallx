"""Context building and prompt distillation for AI coding agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from recallx.utils.logging import get_logger

if TYPE_CHECKING:
    from recallx.core.memory import MemoryEngine

logger = get_logger("recallx.core.context")


class ContextBuilder:
    """Constructs prompt-ready context windows from persistent project memories."""

    def __init__(self, engine: MemoryEngine) -> None:
        """Initialize ContextBuilder.

        Args:
            engine: Initialized MemoryEngine instance.
        """
        self.engine = engine

    def build_project_context(self, project_id: str, max_tokens: int = 4000) -> str:
        """Compile a structured text summary for agent system prompt context.

        Respects a token budget approximated as tokens = chars * 0.25 (i.e. ~4 characters per token).

        Args:
            project_id: Project identifier.
            max_tokens: Approximate maximum token limit for the context block.

        Returns:
            Formatted Markdown context block.
        """
        max_chars = max(500, int(max_tokens * 4))

        # Retrieve project record if available
        project_info = self.engine.project_repo.get(project_id)
        proj_name = project_info.get("name", project_id) if project_info else project_id
        proj_desc = project_info.get("description", "") if project_info else ""

        lines: list[str] = [
            f"# Project Context: {proj_name} (ID: {project_id})",
        ]
        if proj_desc:
            lines.append(f"Description: {proj_desc}")
        lines.append("")

        # Retrieve structured context
        ctx = self.engine.get_project_context(project_id, limit=8)
        by_type = ctx.get("memories_by_type", {})

        # Pinned memories
        pinned = self.engine.list_memories(project_id=project_id, pinned_only=True, limit=10)
        if pinned:
            lines.append("## Pinned Guidelines & Architectural Directives")
            for m in pinned:
                lines.append(f"- [{m['id']}] {m['content']}")
            lines.append("")

        # Section formatting order
        section_order = [
            ("project", "Project Overview & Tech Stack"),
            ("decision", "Key Decisions & Architecture"),
            ("bug_solution", "Troubleshooting & Bug Solutions"),
            ("preference", "Conventions & Standards"),
            ("session", "Recent Sessions & Progress"),
        ]

        for m_type, section_title in section_order:
            memories_list = by_type.get(m_type, [])
            # Filter out pinned items if already displayed above
            unpinned = [m for m in memories_list if not m.get("is_pinned")]
            if not unpinned:
                continue

            section_lines = [f"## {section_title}"]
            for m in unpinned:
                tags_str = f" [tags: {', '.join(m.get('tags', []))}]" if m.get("tags") else ""
                section_lines.append(f"- [{m['id']}]{tags_str} {m['content']}")
            section_lines.append("")

            # Check character budget before appending section
            tentative_text = "\n".join(lines + section_lines)
            if len(tentative_text) > max_chars:
                lines.append(f"## {section_title} (truncated)")
                for m in unpinned:
                    line = f"- [{m['id']}] {m['content']}"
                    if len("\n".join(lines + [line])) <= max_chars:
                        lines.append(line)
                    else:
                        break
                lines.append("")
                break
            else:
                lines.extend(section_lines)

        result = "\n".join(lines).strip()
        return result

    def build_query_context(self, query: str, project_id: str, limit: int = 5) -> str:
        """Search and format memories relevant to a specific user or agent query.

        Args:
            query: The query string to search.
            project_id: Project identifier.
            limit: Maximum memories to include.

        Returns:
            Formatted context block with memory IDs and relevance ratings.
        """
        results = self.engine.recall(
            query=query,
            project_id=project_id,
            limit=limit,
        )

        if not results:
            return f"### Relevant Memory Context\nNo specific past memories found for query: '{query}'."

        lines: list[str] = [
            f"### Relevant Project Memories for: \"{query}\"",
        ]

        for mem in results:
            m_id = mem.get("id", "unknown")
            m_type = mem.get("memory_type", "note")
            rel = mem.get("relevance", 0.0)
            content = mem.get("content", "").strip()
            tags = mem.get("tags", [])
            tag_str = f" | tags: {', '.join(tags)}" if tags else ""

            lines.append(f"- **[{m_id}]** ({m_type}, score: {rel:.2f}{tag_str}): {content}")

        return "\n".join(lines)
