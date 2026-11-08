"""SQLAlchemy 2.0 ORM models for RecallX persistence layer.

Defines declarative mappings for Memory and Project entities, with integrity
check constraints, composite indexing, and serialization helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from recallx.utils.hashing import content_hash as compute_content_hash
from recallx.utils.hashing import short_id


def _utc_now() -> datetime:
    """Return the current timestamp in UTC timezone.

    Returns:
        Timezone-aware datetime object representing now in UTC.
    """
    return datetime.now(timezone.utc)


def _parse_dt(val: Any) -> datetime | None:
    """Parse an arbitrary value into a UTC datetime instance.

    Args:
        val: Datetime object, ISO 8601 string, or None.

    Returns:
        Timezone-aware datetime in UTC, or None if input was None.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        cleaned = val.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _format_iso(dt: datetime | None) -> str | None:
    """Format a datetime as an ISO 8601 string in UTC.

    Args:
        dt: Datetime object or None.

    Returns:
        ISO 8601 string representation or None.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


class Base(DeclarativeBase):
    """Declarative base class for all RecallX SQLAlchemy models."""

    pass


class Memory(Base):
    """Persistent representation of an atomic memory item.

    Captures agent learnings, decisions, code patterns, preferences,
    and session state scoped to a project.
    """

    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(
        String(12),
        primary_key=True,
        default=lambda: short_id(12),
        doc="Short 12-character unique identifier.",
    )
    memory_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        doc="Category enum: project, decision, bug_solution, preference, session.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Textual body of the memory record.",
    )
    project_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        doc="Identifier of the associated project workspace.",
    )
    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        doc="List of normalized category tags.",
    )
    source: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        default=None,
        doc="Origin agent or CLI invocation (e.g. claude-code, manual, cli).",
    )
    importance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        doc="Subjective significance score between 0.0 and 1.0.",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.7,
        doc="Reliability / confidence score between 0.0 and 1.0.",
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this memory is pinned to avoid eviction and rank higher.",
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        doc="Soft-deletion / archival status.",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Deterministic SHA-256 hash of normalized content.",
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Arbitrary structured metadata dictionary.",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        doc="Optional expiration timestamp for ephemeral memories.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        doc="Creation timestamp in UTC.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
        doc="Last modification timestamp in UTC.",
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        doc="Last read or retrieval timestamp in UTC.",
    )

    __table_args__ = (
        CheckConstraint(
            "importance >= 0.0 AND importance <= 1.0",
            name="ck_memory_importance",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_memory_confidence",
        ),
        CheckConstraint(
            "memory_type IN ('project', 'decision', 'bug_solution', 'preference', 'session')",
            name="ck_memory_type",
        ),
        Index("ix_memory_project_type", "project_id", "memory_type"),
        Index("ix_memory_project_archived", "project_id", "is_archived"),
        Index("ix_memory_hash_project", "content_hash", "project_id"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize memory record to a JSON-compatible dictionary.

        Returns:
            Dictionary containing all model attributes with ISO 8601 UTC dates.
        """
        return {
            "id": self.id,
            "memory_type": self.memory_type,
            "content": self.content,
            "project_id": self.project_id,
            "tags": list(self.tags or []),
            "source": self.source,
            "importance": float(self.importance),
            "confidence": float(self.confidence),
            "is_pinned": bool(self.is_pinned),
            "is_archived": bool(self.is_archived),
            "content_hash": self.content_hash,
            "metadata": dict(self.metadata_json or {}),
            "metadata_json": dict(self.metadata_json or {}),
            "expires_at": _format_iso(self.expires_at),
            "created_at": _format_iso(self.created_at),
            "updated_at": _format_iso(self.updated_at),
            "accessed_at": _format_iso(self.accessed_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Instantiate a Memory entity from dictionary data.

        Args:
            data: Dictionary containing memory attributes.

        Returns:
            Instantiated Memory model.
        """
        raw_content = str(data["content"])
        meta = data.get("metadata_json") or data.get("metadata") or {}
        c_hash = str(data.get("content_hash") or compute_content_hash(raw_content))
        memory_id = str(data.get("id") or short_id(12))

        return cls(
            id=memory_id,
            memory_type=str(data.get("memory_type", "project")),
            content=raw_content,
            project_id=str(data["project_id"]),
            tags=list(data.get("tags") or []),
            source=str(data["source"]) if data.get("source") is not None else None,
            importance=float(data.get("importance", 0.5)),
            confidence=float(data.get("confidence", 0.7)),
            is_pinned=bool(data.get("is_pinned", False)),
            is_archived=bool(data.get("is_archived", False)),
            content_hash=c_hash,
            metadata_json=dict(meta),
            expires_at=_parse_dt(data.get("expires_at")),
            created_at=_parse_dt(data.get("created_at")) or _utc_now(),
            updated_at=_parse_dt(data.get("updated_at")) or _utc_now(),
            accessed_at=_parse_dt(data.get("accessed_at")) or _utc_now(),
        )


class Project(Base):
    """Persistent representation of a project workspace.

    Stores project identifiers, display names, filesystem paths,
    and associated workspace configuration metadata.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        doc="Unique project identifier (alphanumeric, hyphens, underscores).",
    )
    name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        doc="Human-readable project display name.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        doc="Optional project description or purpose summary.",
    )
    path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        default=None,
        doc="Absolute filesystem path to the project root directory.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        doc="Creation timestamp in UTC.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
        doc="Last modification timestamp in UTC.",
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        doc="Arbitrary structured metadata dictionary for project settings.",
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize project record to a JSON-compatible dictionary.

        Returns:
            Dictionary containing all model attributes with ISO 8601 UTC dates.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "created_at": _format_iso(self.created_at),
            "updated_at": _format_iso(self.updated_at),
            "metadata": dict(self.metadata_json or {}),
            "metadata_json": dict(self.metadata_json or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        """Instantiate a Project entity from dictionary data.

        Args:
            data: Dictionary containing project attributes.

        Returns:
            Instantiated Project model.
        """
        meta = data.get("metadata_json") or data.get("metadata") or {}
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data["description"]) if data.get("description") is not None else None,
            path=str(data["path"]) if data.get("path") is not None else None,
            created_at=_parse_dt(data.get("created_at")) or _utc_now(),
            updated_at=_parse_dt(data.get("updated_at")) or _utc_now(),
            metadata_json=dict(meta),
        )
