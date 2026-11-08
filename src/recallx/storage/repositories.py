"""Repository layer for RecallX persistence entities.

Implements MemoryRepository and ProjectRepository patterns with CRUD operations,
FTS5 full-text search integration, statistical summaries, and Pydantic validation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, text, update

from recallx.storage.database import DatabaseManager
from recallx.storage.models import Memory, Project
from recallx.utils.hashing import content_hash as compute_content_hash
from recallx.utils.hashing import short_id
from recallx.utils.logging import get_logger

logger = get_logger("recallx.storage.repositories")

VALID_MEMORY_TYPES = frozenset(
    {"project", "decision", "bug_solution", "preference", "session"}
)


class MemoryCreate(BaseModel):
    """Pydantic model for validating memory creation payloads."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    content: str = Field(
        ...,
        min_length=1,
        description="Text content of the memory record.",
    )
    project_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Project workspace identifier.",
    )
    memory_type: str = Field(
        default="project",
        description="Category: project, decision, bug_solution, preference, session.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="List of associated descriptive tags.",
    )
    source: str | None = Field(
        default=None,
        max_length=256,
        description="Optional source identifier (e.g. claude-code, manual, cli).",
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Significance score between 0.0 and 1.0.",
    )
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence rating between 0.0 and 1.0.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured metadata.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiration timestamp in UTC.",
    )

    @field_validator("content")
    @classmethod
    def _validate_content(cls, val: str) -> str:
        trimmed = val.strip()
        if not trimmed:
            raise ValueError("Memory content cannot be empty or blank.")
        return trimmed

    @field_validator("project_id")
    @classmethod
    def _validate_project_id(cls, val: str) -> str:
        trimmed = val.strip()
        if not trimmed:
            raise ValueError("project_id cannot be empty.")
        return trimmed

    @field_validator("memory_type")
    @classmethod
    def _validate_memory_type(cls, val: str) -> str:
        normalized = val.strip().lower()
        if normalized not in VALID_MEMORY_TYPES:
            allowed = ", ".join(sorted(VALID_MEMORY_TYPES))
            raise ValueError(f"Invalid memory_type '{val}'. Must be one of: {allowed}")
        return normalized

    @field_validator("tags")
    @classmethod
    def _validate_tags(cls, val: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for tag in val:
            if isinstance(tag, str):
                cleaned = tag.strip().lower()
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    deduped.append(cleaned)
        return deduped

    @field_validator("expires_at")
    @classmethod
    def _ensure_utc(cls, val: datetime | None) -> datetime | None:
        if val is None:
            return None
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)


def _format_raw_dt(val: Any) -> str | None:
    """Format a raw column value into an ISO 8601 UTC string.

    Args:
        val: Datetime object, ISO-like string, or None.

    Returns:
        ISO 8601 formatted string or None.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc).isoformat()
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.strip().replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return val
    return str(val)


def _sanitize_fts_query(query: str) -> str:
    """Sanitize user query for SQLite FTS5 MATCH expression.

    Extracts word tokens and formats them as prefix match tokens to prevent
    syntax crashes on raw quotes or symbols.

    Args:
        query: Raw search query string.

    Returns:
        Sanitized FTS5 query string, or empty string if no valid tokens.
    """
    cleaned = query.strip()
    if not cleaned:
        return ""

    tokens = [t for t in re.findall(r"[\w\-]+", cleaned) if t]
    if not tokens:
        return ""

    # Quote each token safely and enable prefix matching
    safe_terms = [f'"{tok}"*' for tok in tokens]
    return " ".join(safe_terms)


class MemoryRepository:
    """Data access repository for managing Memory entities and FTS5 search."""

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize repository with DatabaseManager instance.

        Args:
            db: Initialized DatabaseManager instance.
        """
        self.db = db

    def create(self, memory: MemoryCreate) -> dict[str, Any]:
        """Create and persist a new Memory record, indexing it into FTS5.

        Args:
            memory: Validated MemoryCreate payload.

        Returns:
            Dictionary representation of the created memory record.
        """
        now = datetime.now(timezone.utc)
        mem_id = short_id(12)
        c_hash = compute_content_hash(memory.content)

        orm_mem = Memory(
            id=mem_id,
            memory_type=memory.memory_type,
            content=memory.content,
            project_id=memory.project_id,
            tags=list(memory.tags),
            source=memory.source,
            importance=memory.importance,
            confidence=memory.confidence,
            is_pinned=False,
            is_archived=False,
            content_hash=c_hash,
            metadata_json=dict(memory.metadata),
            expires_at=memory.expires_at,
            created_at=now,
            updated_at=now,
            accessed_at=now,
        )

        with self.db.create_session() as session:
            session.add(orm_mem)
            self.sync_fts(
                memory_id=mem_id,
                content=memory.content,
                tags=memory.tags,
                memory_type=memory.memory_type,
                project_id=memory.project_id,
                session=session,
            )

        return orm_mem.to_dict()

    def get(self, memory_id: str) -> dict[str, Any] | None:
        """Retrieve a memory record by unique identifier.

        Args:
            memory_id: Short unique identifier.

        Returns:
            Dictionary representation if found, None otherwise.
        """
        with self.db.create_session() as session:
            mem = session.get(Memory, memory_id)
            if mem is None:
                return None
            return mem.to_dict()

    def update(self, memory_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update fields of an existing memory record.

        Args:
            memory_id: Unique identifier of target memory.
            updates: Dictionary of fields to update.

        Returns:
            Updated memory dictionary, or None if not found.
        """
        with self.db.create_session() as session:
            mem = session.get(Memory, memory_id)
            if mem is None:
                return None

            if "content" in updates:
                new_content = str(updates["content"]).strip()
                if new_content:
                    mem.content = new_content
                    mem.content_hash = compute_content_hash(new_content)

            if "memory_type" in updates:
                mtype = str(updates["memory_type"]).strip().lower()
                if mtype in VALID_MEMORY_TYPES:
                    mem.memory_type = mtype

            if "tags" in updates:
                raw_tags = updates["tags"]
                if isinstance(raw_tags, (list, tuple, set)):
                    cleaned_tags = [
                        t.strip().lower() for t in raw_tags if isinstance(t, str) and t.strip()
                    ]
                    mem.tags = list(dict.fromkeys(cleaned_tags))

            if "source" in updates:
                mem.source = str(updates["source"]) if updates["source"] is not None else None

            if "importance" in updates:
                mem.importance = max(0.0, min(1.0, float(updates["importance"])))

            if "confidence" in updates:
                mem.confidence = max(0.0, min(1.0, float(updates["confidence"])))

            if "is_pinned" in updates:
                mem.is_pinned = bool(updates["is_pinned"])

            if "is_archived" in updates:
                mem.is_archived = bool(updates["is_archived"])

            if "metadata" in updates:
                mem.metadata_json = dict(updates["metadata"] or {})
            elif "metadata_json" in updates:
                mem.metadata_json = dict(updates["metadata_json"] or {})

            if "expires_at" in updates:
                exp = updates["expires_at"]
                if isinstance(exp, str):
                    exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if isinstance(exp, datetime) and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                mem.expires_at = exp

            mem.updated_at = datetime.now(timezone.utc)
            session.flush()

            # Synchronize full text index state
            if mem.is_archived:
                self.delete_fts(mem.id, session=session)
            else:
                self.sync_fts(
                    memory_id=mem.id,
                    content=mem.content,
                    tags=mem.tags,
                    memory_type=mem.memory_type,
                    project_id=mem.project_id,
                    session=session,
                )

            return mem.to_dict()

    def delete(self, memory_id: str) -> bool:
        """Permanently delete a memory record and its FTS5 index entry.

        Args:
            memory_id: Unique identifier of target memory.

        Returns:
            True if memory was found and deleted, False otherwise.
        """
        with self.db.create_session() as session:
            mem = session.get(Memory, memory_id)
            if mem is None:
                return False
            session.delete(mem)
            self.delete_fts(memory_id, session=session)

        return True

    def list(
        self,
        project_id: str | None = None,
        memory_type: str | None = None,
        is_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
        pinned_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List memories matching filters, ordered by pinned status and recency.

        Args:
            project_id: Filter by project workspace.
            memory_type: Filter by category enum.
            is_archived: Include archived memories if True, defaults to False.
            limit: Maximum items to return.
            offset: Number of items to skip.
            pinned_only: Return only pinned memories if True.

        Returns:
            List of memory record dictionaries.
        """
        with self.db.create_session() as session:
            stmt = select(Memory).where(Memory.is_archived == is_archived)

            if project_id is not None:
                stmt = stmt.where(Memory.project_id == project_id)

            if memory_type is not None:
                stmt = stmt.where(Memory.memory_type == memory_type)

            if pinned_only:
                stmt = stmt.where(Memory.is_pinned.is_(True))

            stmt = stmt.order_by(Memory.is_pinned.desc(), Memory.created_at.desc())
            stmt = stmt.offset(max(0, offset)).limit(max(1, limit))

            rows = session.execute(stmt).scalars().all()
            return [row.to_dict() for row in rows]

    def search_fts(
        self,
        query: str,
        project_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search non-archived memories via FTS5 full-text match ranked by BM25.

        Args:
            query: User text search query.
            project_id: Optional project filter.
            memory_type: Optional category filter.
            limit: Maximum search results.

        Returns:
            List of matching memory record dictionaries.
        """
        safe_query = _sanitize_fts_query(query)
        if not safe_query:
            return []

        where_clauses = ["memory_fts MATCH :query", "m.is_archived = 0"]
        params: dict[str, Any] = {"query": safe_query, "limit": max(1, limit)}

        if project_id is not None:
            where_clauses.append("m.project_id = :project_id")
            params["project_id"] = project_id

        if memory_type is not None:
            where_clauses.append("m.memory_type = :memory_type")
            params["memory_type"] = memory_type

        where_sql = " AND ".join(where_clauses)
        sql = (
            f"SELECT m.id, m.memory_type, m.content, m.project_id, m.tags, "
            f"m.source, m.importance, m.confidence, m.is_pinned, m.is_archived, "
            f"m.content_hash, m.metadata_json, m.expires_at, m.created_at, "
            f"m.updated_at, m.accessed_at "
            f"FROM memories m "
            f"JOIN memory_fts ON m.id = memory_fts.id "
            f"WHERE {where_sql} "
            f"ORDER BY bm25(memory_fts) "
            f"LIMIT :limit"
        )

        try:
            with self.db.engine.connect() as conn:
                result = conn.execute(text(sql), params)
                records: list[dict[str, Any]] = []
                for row in result:
                    mapping = row._mapping
                    tags_val = mapping["tags"]
                    if isinstance(tags_val, str):
                        try:
                            tags_val = json.loads(tags_val)
                        except Exception:
                            tags_val = [tags_val]

                    meta_val = mapping["metadata_json"]
                    if isinstance(meta_val, str):
                        try:
                            meta_val = json.loads(meta_val)
                        except Exception:
                            meta_val = {}

                    records.append(
                        {
                            "id": mapping["id"],
                            "memory_type": mapping["memory_type"],
                            "content": mapping["content"],
                            "project_id": mapping["project_id"],
                            "tags": list(tags_val or []),
                            "source": mapping["source"],
                            "importance": float(mapping["importance"]),
                            "confidence": float(mapping["confidence"]),
                            "is_pinned": bool(mapping["is_pinned"]),
                            "is_archived": bool(mapping["is_archived"]),
                            "content_hash": mapping["content_hash"],
                            "metadata": dict(meta_val or {}),
                            "metadata_json": dict(meta_val or {}),
                            "expires_at": _format_raw_dt(mapping["expires_at"]),
                            "created_at": _format_raw_dt(mapping["created_at"]),
                            "updated_at": _format_raw_dt(mapping["updated_at"]),
                            "accessed_at": _format_raw_dt(mapping["accessed_at"]),
                        }
                    )
                return records
        except Exception as exc:
            logger.warning("FTS search failed (%s); falling back to LIKE query.", exc)
            return self._search_like_fallback(
                query=query,
                project_id=project_id,
                memory_type=memory_type,
                limit=limit,
            )

    def _search_like_fallback(
        self,
        query: str,
        project_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fallback search using SQL LIKE in case of FTS syntax issues."""
        with self.db.create_session() as session:
            stmt = select(Memory).where(
                Memory.is_archived.is_(False),
                Memory.content.icontains(query),
            )
            if project_id is not None:
                stmt = stmt.where(Memory.project_id == project_id)
            if memory_type is not None:
                stmt = stmt.where(Memory.memory_type == memory_type)
            stmt = stmt.order_by(Memory.is_pinned.desc(), Memory.created_at.desc())
            stmt = stmt.limit(max(1, limit))
            rows = session.execute(stmt).scalars().all()
            return [r.to_dict() for r in rows]

    def find_by_hash(self, content_hash: str, project_id: str) -> dict[str, Any] | None:
        """Find non-archived memory by exact content hash and project identifier.

        Args:
            content_hash: SHA-256 hash string.
            project_id: Project identifier.

        Returns:
            Dictionary representation if found, None otherwise.
        """
        with self.db.create_session() as session:
            stmt = select(Memory).where(
                Memory.content_hash == content_hash,
                Memory.project_id == project_id,
                Memory.is_archived.is_(False),
            )
            mem = session.execute(stmt).scalars().first()
            return mem.to_dict() if mem is not None else None

    def count(self, project_id: str | None = None) -> int:
        """Count active non-archived memories.

        Args:
            project_id: Optional project filter.

        Returns:
            Total count of active memories.
        """
        with self.db.create_session() as session:
            stmt = select(func.count(Memory.id)).where(Memory.is_archived.is_(False))
            if project_id is not None:
                stmt = stmt.where(Memory.project_id == project_id)
            return int(session.execute(stmt).scalar_one() or 0)

    def update_accessed(self, memory_id: str) -> None:
        """Update the accessed_at timestamp to current UTC time.

        Args:
            memory_id: Target memory identifier.
        """
        now = datetime.now(timezone.utc)
        with self.db.create_session() as session:
            stmt = update(Memory).where(Memory.id == memory_id).values(accessed_at=now)
            session.execute(stmt)

    def sync_fts(
        self,
        memory_id: str,
        content: str,
        tags: list[str],
        memory_type: str,
        project_id: str,
        session: Any = None,
    ) -> None:
        """Synchronize an individual memory entry into the FTS5 virtual table.

        Args:
            memory_id: Memory identifier.
            content: Textual content body.
            tags: List of tags.
            memory_type: Category identifier.
            project_id: Project workspace identifier.
            session: Optional existing active database session.
        """
        tags_str = " ".join(tags) if isinstance(tags, (list, tuple, set)) else str(tags or "")
        delete_sql = text("DELETE FROM memory_fts WHERE id = :id")
        insert_sql = text(
            "INSERT INTO memory_fts(id, content, tags, memory_type, project_id) "
            "VALUES (:id, :content, :tags, :memory_type, :project_id)"
        )
        params = {
            "id": memory_id,
            "content": content,
            "tags": tags_str,
            "memory_type": memory_type,
            "project_id": project_id,
        }
        try:
            if session is not None:
                session.execute(delete_sql, {"id": memory_id})
                session.execute(insert_sql, params)
            else:
                with self.db.engine.begin() as conn:
                    conn.execute(delete_sql, {"id": memory_id})
                    conn.execute(insert_sql, params)
        except Exception as exc:
            logger.error("Failed to sync FTS entry for memory %s: %s", memory_id, exc)

    def delete_fts(self, memory_id: str, session: Any = None) -> None:
        """Remove a memory entry from the FTS5 virtual index.

        Args:
            memory_id: Memory identifier to remove.
            session: Optional existing active database session.
        """
        stmt = text("DELETE FROM memory_fts WHERE id = :id")
        try:
            if session is not None:
                session.execute(stmt, {"id": memory_id})
            else:
                with self.db.engine.begin() as conn:
                    conn.execute(stmt, {"id": memory_id})
        except Exception as exc:
            logger.error("Failed to delete FTS entry for memory %s: %s", memory_id, exc)

    def get_stats(self, project_id: str | None = None) -> dict[str, Any]:
        """Aggregate memory repository statistics.

        Args:
            project_id: Optional project filter.

        Returns:
            Dictionary containing totals, counts by category, pinned/archived counts,
            and distinct projects.
        """
        with self.db.create_session() as session:
            # Active total
            total_stmt = select(func.count(Memory.id)).where(Memory.is_archived.is_(False))
            if project_id is not None:
                total_stmt = total_stmt.where(Memory.project_id == project_id)
            total = int(session.execute(total_stmt).scalar_one() or 0)

            # Counts by type
            type_stmt = (
                select(Memory.memory_type, func.count(Memory.id))
                .where(Memory.is_archived.is_(False))
            )
            if project_id is not None:
                type_stmt = type_stmt.where(Memory.project_id == project_id)
            type_stmt = type_stmt.group_by(Memory.memory_type)
            counts_by_type = {m_type: int(cnt) for m_type, cnt in session.execute(type_stmt).all()}

            # Pinned count
            pinned_stmt = select(func.count(Memory.id)).where(
                Memory.is_archived.is_(False),
                Memory.is_pinned.is_(True),
            )
            if project_id is not None:
                pinned_stmt = pinned_stmt.where(Memory.project_id == project_id)
            pinned = int(session.execute(pinned_stmt).scalar_one() or 0)

            # Archived count
            archived_stmt = select(func.count(Memory.id)).where(Memory.is_archived.is_(True))
            if project_id is not None:
                archived_stmt = archived_stmt.where(Memory.project_id == project_id)
            archived = int(session.execute(archived_stmt).scalar_one() or 0)

            # Distinct project IDs
            proj_stmt = select(Memory.project_id).distinct()
            projects = [p for p in session.execute(proj_stmt).scalars().all() if p]

            return {
                "total": total,
                "total_memories": total,
                "active_memories": total,
                "counts_by_type": counts_by_type,
                "by_type": counts_by_type,
                "pinned": pinned,
                "pinned_memories": pinned,
                "archived": archived,
                "archived_memories": archived,
                "projects": sorted(projects),
            }


class ProjectRepository:
    """Data access repository for managing Project entities."""

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize repository with DatabaseManager instance.

        Args:
            db: Initialized DatabaseManager instance.
        """
        self.db = db

    def create(
        self,
        project_id: str,
        name: str,
        description: str | None = None,
        path: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and persist a new Project workspace record.

        Args:
            project_id: Unique project identifier.
            name: Human-readable display name.
            description: Optional summary description.
            path: Optional filesystem workspace directory path.
            metadata: Optional metadata dictionary.

        Returns:
            Dictionary representation of the created project.
        """
        now = datetime.now(timezone.utc)
        proj = Project(
            id=project_id.strip(),
            name=name.strip(),
            description=description.strip() if description else None,
            path=path.strip() if path else None,
            created_at=now,
            updated_at=now,
            metadata_json=dict(metadata or {}),
        )

        with self.db.create_session() as session:
            session.add(proj)

        return proj.to_dict()

    def get(self, project_id: str) -> dict[str, Any] | None:
        """Retrieve a project by unique identifier.

        Args:
            project_id: Target project identifier.

        Returns:
            Project dictionary if found, None otherwise.
        """
        with self.db.create_session() as session:
            proj = session.get(Project, project_id.strip())
            return proj.to_dict() if proj is not None else None

    def update(self, project_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing project workspace record.

        Args:
            project_id: Target project identifier.
            updates: Dictionary of fields to update.

        Returns:
            Updated project dictionary, or None if not found.
        """
        with self.db.create_session() as session:
            proj = session.get(Project, project_id.strip())
            if proj is None:
                return None

            if "name" in updates:
                name_str = str(updates["name"]).strip()
                if name_str:
                    proj.name = name_str

            if "description" in updates:
                desc = updates["description"]
                proj.description = str(desc).strip() if desc is not None else None

            if "path" in updates:
                p_val = updates["path"]
                proj.path = str(p_val).strip() if p_val is not None else None

            if "metadata" in updates:
                proj.metadata_json = dict(updates["metadata"] or {})
            elif "metadata_json" in updates:
                proj.metadata_json = dict(updates["metadata_json"] or {})

            proj.updated_at = datetime.now(timezone.utc)
            session.flush()
            return proj.to_dict()

    def delete(self, project_id: str) -> bool:
        """Delete a project workspace record.

        Args:
            project_id: Target project identifier.

        Returns:
            True if project existed and was deleted, False otherwise.
        """
        with self.db.create_session() as session:
            proj = session.get(Project, project_id.strip())
            if proj is None:
                return False
            session.delete(proj)
            return True

    def list(self) -> list[dict[str, Any]]:
        """List all registered projects ordered alphabetically by name.

        Returns:
            List of project dictionaries.
        """
        with self.db.create_session() as session:
            stmt = select(Project).order_by(Project.name.asc())
            rows = session.execute(stmt).scalars().all()
            return [row.to_dict() for row in rows]

    def exists(self, project_id: str) -> bool:
        """Check whether a project identifier already exists.

        Args:
            project_id: Target project identifier.

        Returns:
            True if project exists, False otherwise.
        """
        with self.db.create_session() as session:
            stmt = select(func.count(Project.id)).where(Project.id == project_id.strip())
            cnt = session.execute(stmt).scalar_one() or 0
            return cnt > 0
