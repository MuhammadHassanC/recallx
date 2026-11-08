"""Central memory orchestration engine for RecallX."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from recallx.core.deduplication import DeduplicationEngine
from recallx.core.ranking import RelevanceRanker
from recallx.core.retrieval import RetrievalEngine
from recallx.storage.database import DatabaseManager
from recallx.storage.repositories import MemoryCreate, MemoryRepository, ProjectRepository
from recallx.utils.hashing import content_hash
from recallx.utils.logging import get_logger
from recallx.utils.validation import (
    redact_secrets,
    sanitize_for_storage,
    validate_memory_content,
    validate_project_id,
    validate_tags,
)

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone

    UTC = timezone.utc  # type: ignore[attr-defined]

logger = get_logger("recallx.core.memory")


class MemoryEngine:
    """The central memory orchestrator for RecallX."""

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize MemoryEngine with database manager and dependent subsystems.

        Args:
            db: Initialized DatabaseManager instance.
        """
        self.db = db
        self.repo = MemoryRepository(db)
        self.project_repo = ProjectRepository(db)
        self.ranker = RelevanceRanker()
        self.retrieval = RetrievalEngine(self.repo, self.ranker)
        self.dedup = DeduplicationEngine(self.repo)

    def remember(
        self,
        content: str,
        project_id: str,
        memory_type: str = "project",
        tags: list[str] | None = None,
        source: str | None = None,
        importance: float = 0.5,
        confidence: float = 0.7,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        """Record a new memory with validation, secret redaction, and deduplication.

        Args:
            content: Text body of the memory.
            project_id: Associated project identifier.
            memory_type: Category ('project', 'decision', 'bug_solution', 'preference', 'session').
            tags: Optional category tags.
            source: Source identifier (e.g. claude-code, gemini, cli).
            importance: Subjective importance rating (0.0 to 1.0).
            confidence: Confidence score (0.0 to 1.0).
            metadata: Structured arbitrary metadata.
            expires_at: Optional expiration timestamp.

        Returns:
            Dictionary representation of the saved or existing duplicate memory.
        """
        # Validate inputs
        clean_content = validate_memory_content(content)
        clean_project_id = validate_project_id(project_id)
        clean_tags = validate_tags(tags or [])

        # Sanitize and redact credentials
        clean_content = sanitize_for_storage(clean_content)
        clean_content = redact_secrets(clean_content)

        # Parse expires_at if string
        exp_dt: datetime | None = None
        if isinstance(expires_at, str):
            cleaned = expires_at.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(cleaned)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=UTC)
        elif isinstance(expires_at, datetime):
            exp_dt = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)

        # Compute content hash
        c_hash = content_hash(clean_content)

        # Duplicate detection (same hash + project)
        existing = self.repo.find_by_hash(content_hash=c_hash, project_id=clean_project_id)
        if existing is not None:
            self.repo.update_accessed(existing["id"])
            existing["accessed_at"] = datetime.now(UTC).isoformat()
            logger.debug(
                "Duplicate memory found for hash %s in project %s; updated accessed_at.",
                c_hash[:8],
                clean_project_id,
            )
            return existing

        # Create new memory
        create_payload = MemoryCreate(
            content=clean_content,
            project_id=clean_project_id,
            memory_type=memory_type,
            tags=clean_tags,
            source=source,
            importance=max(0.0, min(1.0, float(importance))),
            confidence=max(0.0, min(1.0, float(confidence))),
            metadata=dict(metadata or {}),
            expires_at=exp_dt,
        )

        saved = self.repo.create(create_payload)
        logger.info("Remembered new memory %s (type=%s, project=%s)", saved["id"], memory_type, clean_project_id)
        return saved

    def recall(
        self,
        query: str,
        project_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search and rank memories by relevance, updating accessed_at timestamps.

        Args:
            query: User search query.
            project_id: Optional project filter.
            memory_type: Optional category filter.
            limit: Maximum results to return.
            min_relevance: Minimum score threshold (0.0 to 1.0).

        Returns:
            Ranked list of memory dictionaries with 'relevance' attribute.
        """
        results = self.retrieval.search(
            query=query,
            project_id=project_id,
            memory_type=memory_type,
            limit=limit,
            min_relevance=min_relevance,
        )

        # Update accessed_at for retrieved results
        for mem in results:
            self.repo.update_accessed(mem["id"])

        return results

    def get(self, memory_id: str) -> dict[str, Any] | None:
        """Retrieve a specific memory by unique identifier.

        Args:
            memory_id: 12-character memory identifier.

        Returns:
            Memory dictionary if found, None otherwise.
        """
        return self.repo.get(memory_id)

    def update(
        self,
        memory_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
        importance: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Update fields of an existing memory record.

        Args:
            memory_id: Identifier of memory to update.
            content: Optional new text content.
            tags: Optional new tags list.
            importance: Optional updated importance score.
            metadata: Optional metadata dictionary.

        Returns:
            Updated memory dictionary, or None if not found.
        """
        existing = self.repo.get(memory_id)
        if not existing:
            return None

        updates: dict[str, Any] = {}

        if content is not None:
            clean_content = validate_memory_content(content)
            clean_content = sanitize_for_storage(clean_content)
            clean_content = redact_secrets(clean_content)
            updates["content"] = clean_content
            updates["content_hash"] = content_hash(clean_content)

        if tags is not None:
            updates["tags"] = validate_tags(tags)

        if importance is not None:
            updates["importance"] = max(0.0, min(1.0, float(importance)))

        if metadata is not None:
            merged_meta = dict(existing.get("metadata") or {})
            merged_meta.update(metadata)
            updates["metadata"] = merged_meta

        updated = self.repo.update(memory_id, updates)

        if updated and content is not None:
            self.repo.sync_fts(
                memory_id=updated["id"],
                content=updated["content"],
                tags=updated.get("tags", []),
                memory_type=updated.get("memory_type", "project"),
                project_id=updated.get("project_id", ""),
            )

        return updated

    def forget(self, memory_id: str) -> bool:
        """Permanently remove a memory record.

        Args:
            memory_id: Target memory identifier.

        Returns:
            True if memory was deleted, False if not found.
        """
        return self.repo.delete(memory_id)

    def list_memories(
        self,
        project_id: str | None = None,
        memory_type: str | None = None,
        is_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
        pinned_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List stored memories with pagination and filters.

        Args:
            project_id: Filter by project.
            memory_type: Filter by category.
            is_archived: Whether to include archived memories.
            limit: Maximum items to return.
            offset: Number of items to skip.
            pinned_only: Return only pinned memories.

        Returns:
            List of memory dictionaries.
        """
        return self.repo.list(
            project_id=project_id,
            memory_type=memory_type,
            is_archived=is_archived,
            limit=limit,
            offset=offset,
            pinned_only=pinned_only,
        )

    def pin(self, memory_id: str) -> bool:
        """Pin a memory to preserve it and rank it higher.

        Args:
            memory_id: Target memory identifier.

        Returns:
            True if updated, False if memory not found.
        """
        updated = self.repo.update(memory_id, {"is_pinned": True})
        return updated is not None

    def unpin(self, memory_id: str) -> bool:
        """Unpin a previously pinned memory.

        Args:
            memory_id: Target memory identifier.

        Returns:
            True if updated, False if memory not found.
        """
        updated = self.repo.update(memory_id, {"is_pinned": False})
        return updated is not None

    def archive(self, memory_id: str) -> bool:
        """Archive a memory record (soft deletion).

        Args:
            memory_id: Target memory identifier.

        Returns:
            True if updated, False if memory not found.
        """
        updated = self.repo.update(memory_id, {"is_archived": True})
        return updated is not None

    def get_project_context(self, project_id: str, limit: int = 10) -> dict[str, Any]:
        """Compile structured project context starting with pinned items and top memories per category.

        Args:
            project_id: Project identifier.
            limit: Max memories per type to include.

        Returns:
            Structured context dictionary: {project_id, memories_by_type, total_memories}.
        """
        pinned = self.repo.list(
            project_id=project_id,
            is_archived=False,
            pinned_only=True,
            limit=limit,
        )

        all_memories = self.repo.list(
            project_id=project_id,
            is_archived=False,
            limit=200,
        )

        # Categorize by memory type
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        seen_ids: set[str] = set()

        # Add pinned first
        for mem in pinned:
            m_type = str(mem.get("memory_type", "project"))
            by_type[m_type].append(mem)
            seen_ids.add(mem["id"])

        # Then sort remaining by importance
        remaining = [m for m in all_memories if m["id"] not in seen_ids]
        remaining.sort(key=lambda x: float(x.get("importance", 0.0)), reverse=True)

        for mem in remaining:
            m_type = str(mem.get("memory_type", "project"))
            if len(by_type[m_type]) < limit:
                by_type[m_type].append(mem)
                seen_ids.add(mem["id"])

        return {
            "project_id": project_id,
            "memories_by_type": dict(by_type),
            "total_memories": len(all_memories),
        }

    def save_session_summary(
        self,
        project_id: str,
        summary: str,
        tasks_completed: list[str] | None = None,
        tasks_pending: list[str] | None = None,
        issues: list[str] | None = None,
    ) -> dict[str, Any]:
        """Save a structured agent working session summary.

        Args:
            project_id: Associated project identifier.
            summary: Textual summary of the session.
            tasks_completed: List of tasks completed during session.
            tasks_pending: List of remaining or pending tasks.
            issues: List of discovered issues or blockers.

        Returns:
            Created session memory dictionary.
        """
        meta: dict[str, Any] = {
            "tasks_completed": list(tasks_completed or []),
            "tasks_pending": list(tasks_pending or []),
            "issues": list(issues or []),
            "session_saved_at": datetime.now(UTC).isoformat(),
        }

        return self.remember(
            content=summary,
            project_id=project_id,
            memory_type="session",
            tags=["session", "progress"],
            source="session_summary",
            importance=0.60,
            metadata=meta,
        )

    def get_stats(self, project_id: str | None = None) -> dict[str, Any]:
        """Retrieve aggregated memory statistics.

        Args:
            project_id: Optional project filter.

        Returns:
            Statistics dictionary.
        """
        return self.repo.get_stats(project_id)

    def export_memories(
        self,
        project_id: str | None = None,
        output_path: Path | str | None = None,
    ) -> str:
        """Export stored memories to a JSON string and optionally write to disk.

        Args:
            project_id: Optional project filter.
            output_path: Optional filesystem path to save the export.

        Returns:
            Serialized JSON export string.
        """
        memories = self.repo.list(
            project_id=project_id,
            is_archived=False,
            limit=100_000,
        )

        export_data: dict[str, Any] = {
            "version": "1.0.0",
            "timestamp": datetime.now(UTC).isoformat(),
            "project_id": project_id,
            "count": len(memories),
            "memories": memories,
        }

        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)

        if output_path:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
            logger.info("Exported %d memories to %s", len(memories), p)

        return json_str

    def import_memories(
        self,
        data: str | dict[str, Any],
        project_id: str | None = None,
    ) -> dict[str, int]:
        """Import memories from a serialized JSON string or dictionary.

        Args:
            data: JSON string or parsed dictionary.
            project_id: Optional target project identifier override.

        Returns:
            Summary count dict: {imported: int, skipped: int, errors: int}.
        """
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
            except Exception as exc:
                logger.error("Failed to parse JSON for memory import: %s", exc)
                raise ValueError(f"Invalid JSON provided for memory import: {exc}") from exc
        elif isinstance(data, dict):
            parsed = data
        else:
            raise ValueError(f"Import data must be a JSON string or dict, got {type(data).__name__}")

        raw_memories = parsed.get("memories", [])
        if not isinstance(raw_memories, list):
            return {"imported": 0, "skipped": 0, "errors": 1}

        imported = 0
        skipped = 0
        errors = 0

        for item in raw_memories:
            if not isinstance(item, dict):
                errors += 1
                continue

            target_project = project_id or item.get("project_id")
            content = item.get("content")

            if not target_project or not content:
                errors += 1
                continue

            try:
                c_hash = content_hash(str(content))
                existing = self.repo.find_by_hash(content_hash=c_hash, project_id=str(target_project))
                if existing:
                    skipped += 1
                    continue

                self.remember(
                    content=str(content),
                    project_id=str(target_project),
                    memory_type=str(item.get("memory_type", "project")),
                    tags=item.get("tags") or [],
                    source=item.get("source"),
                    importance=float(item.get("importance", 0.5)),
                    confidence=float(item.get("confidence", 0.7)),
                    metadata=item.get("metadata") or {},
                )
                imported += 1
            except Exception as exc:
                logger.warning("Error importing individual memory item: %s", exc)
                errors += 1

        logger.info("Memory import completed: imported=%d, skipped=%d, errors=%d", imported, skipped, errors)
        return {"imported": imported, "skipped": skipped, "errors": errors}

    def backup(self, dest_path: Path | str | None = None) -> Path:
        """Create a timestamped SQLite database backup.

        Args:
            dest_path: Optional target backup path.

        Returns:
            Path of the generated backup file.
        """
        if dest_path is not None:
            out_path = Path(dest_path).resolve()
        else:
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"recallx_backup_{timestamp}.db"
            if self.db.db_path != Path(":memory:"):
                out_path = self.db.db_path.parent / "backups" / filename
            else:
                out_path = Path.cwd() / "backups" / filename

        out_path.parent.mkdir(parents=True, exist_ok=True)
        self.db.backup(out_path)
        return out_path
