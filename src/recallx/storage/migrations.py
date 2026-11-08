"""Schema versioning and database migration management for RecallX.

Maintains schema versions in a dedicated tracking table, validates pending
migrations, and sequentially executes registered migration scripts.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from recallx.storage.database import DatabaseManager
from recallx.storage.models import Base
from recallx.utils.logging import get_logger

logger = get_logger("recallx.storage.migrations")

SCHEMA_VERSION: int = 1

MigrationFunction = Callable[[DatabaseManager], None]


def _migration_v1(db: DatabaseManager) -> None:
    """Version 1 migration: create core tables and FTS5 search index."""
    logger.info("Running v1 migration: Creating core ORM tables and FTS5 index.")
    Base.metadata.create_all(db.engine)
    db.setup_fts()


_MIGRATION_REGISTRY: dict[int, MigrationFunction] = {
    1: _migration_v1,
}


class SchemaManager:
    """Manages schema version tracking, checks, and migrations."""

    def __init__(self, db: DatabaseManager) -> None:
        """Initialize SchemaManager with DatabaseManager.

        Args:
            db: Initialized DatabaseManager instance.
        """
        self.db = db
        self._ensure_version_table()

    def _ensure_version_table(self) -> None:
        """Ensure the schema_version tracking table exists."""
        try:
            with self.db.engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS schema_version ("
                        "version INTEGER PRIMARY KEY, "
                        "applied_at TEXT NOT NULL, "
                        "description TEXT"
                        ")"
                    )
                )
        except Exception as exc:
            logger.error("Failed to ensure schema_version table exists: %s", exc)
            raise

    def get_current_version(self) -> int:
        """Retrieve the currently applied schema version.

        Returns:
            Integer version number, or 0 if no migrations have been recorded.
        """
        self._ensure_version_table()
        try:
            with self.db.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT MAX(version) FROM schema_version")
                ).scalar()
                if result is None:
                    return 0
                return int(result)
        except Exception as exc:
            logger.error("Failed to query current schema version: %s", exc)
            return 0

    def set_version(self, version: int, description: str = "") -> None:
        """Record an applied schema version in the tracking table.

        Args:
            version: Applied version number.
            description: Optional note describing the migration.
        """
        self._ensure_version_table()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with self.db.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT OR REPLACE INTO schema_version (version, applied_at, description) "
                        "VALUES (:version, :applied_at, :description)"
                    ),
                    {
                        "version": version,
                        "applied_at": now_iso,
                        "description": description or f"Schema version {version}",
                    },
                )
            logger.debug("Schema version recorded as %d", version)
        except Exception as exc:
            logger.error("Failed to set schema version to %d: %s", version, exc)
            raise

    def needs_migration(self) -> bool:
        """Determine whether unapplied migrations exist.

        Returns:
            True if current version is less than target SCHEMA_VERSION.
        """
        return self.get_current_version() < SCHEMA_VERSION

    def migrate(self) -> int:
        """Execute all pending schema migrations sequentially up to SCHEMA_VERSION.

        Returns:
            New current schema version.

        Raises:
            RuntimeError: If a required migration step has no registered handler.
        """
        current_version = self.get_current_version()
        if current_version >= SCHEMA_VERSION:
            logger.debug(
                "Database schema is already up to date at version %d.",
                current_version,
            )
            return current_version

        for target_ver in range(current_version + 1, SCHEMA_VERSION + 1):
            if target_ver not in _MIGRATION_REGISTRY:
                raise RuntimeError(
                    f"No migration function registered for schema version {target_ver}."
                )

            logger.info(
                "Applying schema migration %d -> %d...",
                target_ver - 1,
                target_ver,
            )
            migration_fn = _MIGRATION_REGISTRY[target_ver]
            try:
                migration_fn(self.db)
                self.set_version(target_ver, f"Applied migration v{target_ver}")
            except Exception as exc:
                logger.error(
                    "Schema migration to version %d failed: %s",
                    target_ver,
                    exc,
                )
                raise

        final_ver = self.get_current_version()
        logger.info("All migrations completed. Active schema version: %d.", final_ver)
        return final_ver

    @classmethod
    def register_migration(cls, version: int, func: MigrationFunction) -> None:
        """Register a migration function for a future schema version.

        Args:
            version: Target version number.
            func: Callable accepting DatabaseManager.
        """
        _MIGRATION_REGISTRY[version] = func
