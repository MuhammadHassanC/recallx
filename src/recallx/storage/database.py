"""Database connection and engine management for RecallX.

Provides the DatabaseManager class managing SQLite with WAL mode, foreign keys,
session factory, FTS5 virtual tables, integrity checks, and online backups.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from recallx.storage.models import Base
from recallx.utils.logging import get_logger

logger = get_logger("recallx.storage.database")


class DatabaseManager:
    """Manages SQLite engine lifecycle, connection pooling, and FTS5 search tables."""

    def __init__(self, db_path: Path | str) -> None:
        """Initialize SQLite engine with WAL mode and foreign key enforcement.

        Args:
            db_path: Filesystem path to the SQLite database file, or ':memory:'.
        """
        if str(db_path) == ":memory:":
            self.db_path: Path = Path(":memory:")
            engine_url = "sqlite:///:memory:"
        else:
            self.db_path = Path(db_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            engine_url = f"sqlite:///{self.db_path.as_posix()}"

        self.engine: Engine = create_engine(
            engine_url,
            echo=False,
            future=True,
        )

        self._attach_sqlite_pragmas()

        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    def _attach_sqlite_pragmas(self) -> None:
        """Register engine connect listeners to enforce SQLite pragmas."""

        @event.listens_for(self.engine, "connect")
        def _on_connect(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            try:
                # Foreign key enforcement
                cursor.execute("PRAGMA foreign_keys=ON")
                # Busy timeout in ms to handle concurrent agent access
                cursor.execute("PRAGMA busy_timeout=5000")
                # Synchronous mode for balanced safety and performance
                cursor.execute("PRAGMA synchronous=NORMAL")
                # Enable Write-Ahead Logging for file-backed databases
                if str(self.db_path) != ":memory:":
                    cursor.execute("PRAGMA journal_mode=WAL")
            finally:
                cursor.close()

    @contextmanager
    def create_session(self) -> Generator[Session, None, None]:
        """Provide a transactional database session scope.

        Yields:
            SQLAlchemy Session instance.

        Raises:
            Exception: Re-raises any error occurring in the block after rolling back.
        """
        session: Session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Database transaction rolled back due to error: %s", exc)
            raise
        finally:
            session.close()

    def initialize(self) -> None:
        """Create all declarative tables and initialize FTS5 search index."""
        try:
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            Base.metadata.create_all(self.engine)
            self.setup_fts()
            logger.debug("Database initialized successfully at %s", self.db_path)
        except Exception as exc:
            logger.error("Failed to initialize database at %s: %s", self.db_path, exc)
            raise

    def setup_fts(self) -> None:
        """Create FTS5 virtual table for memory full-text indexing."""
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
                        "id, content, tags, memory_type, project_id"
                        ")"
                    )
                )
            logger.debug("FTS5 table memory_fts ready.")
        except Exception as exc:
            logger.error("Failed to setup FTS5 table: %s", exc)
            raise

    def rebuild_fts(self) -> None:
        """Rebuild the full FTS5 index from the memories table."""
        try:
            with self.engine.begin() as conn:
                conn.execute(text("DELETE FROM memory_fts"))
                conn.execute(
                    text(
                        "INSERT INTO memory_fts(id, content, tags, memory_type, project_id) "
                        "SELECT id, content, tags, memory_type, project_id "
                        "FROM memories WHERE is_archived = 0"
                    )
                )
            logger.info("FTS5 memory index rebuilt successfully.")
        except Exception as exc:
            logger.error("Failed to rebuild FTS5 index: %s", exc)
            raise

    def verify_integrity(self) -> bool:
        """Run SQLite integrity check to verify database health.

        Returns:
            True if the database integrity is confirmed intact, False otherwise.
        """
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(text("PRAGMA integrity_check")).fetchall()
                return len(rows) == 1 and rows[0][0] == "ok"
        except Exception as exc:
            logger.error("Database integrity check failed: %s", exc)
            return False

    def get_db_size(self) -> int:
        """Calculate the primary database file size in bytes.

        Returns:
            File size in bytes, or 0 if in-memory or not yet created.
        """
        if str(self.db_path) == ":memory:":
            return 0
        try:
            if self.db_path.is_file():
                return self.db_path.stat().st_size
            return 0
        except OSError as exc:
            logger.warning("Could not determine file size for %s: %s", self.db_path, exc)
            return 0

    def vacuum(self) -> None:
        """Run VACUUM to defragment storage and reclaim space."""
        try:
            with self.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("VACUUM"))
            logger.info("Database VACUUM completed successfully.")
        except Exception as exc:
            logger.error("Database VACUUM execution failed: %s", exc)
            raise

    def backup(self, dest_path: Path) -> None:
        """Create an online hot backup of the SQLite database.

        Args:
            dest_path: Destination filesystem path for the backup database.
        """
        dest = Path(dest_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        raw_src = self.engine.raw_connection()
        try:
            if hasattr(raw_src, "driver_connection"):
                src_dbapi = raw_src.driver_connection
            else:
                src_dbapi = raw_src.connection
            dest_conn = sqlite3.connect(str(dest))
            try:
                src_dbapi.backup(dest_conn)
                logger.info("Database hot backup created successfully at %s", dest)
            finally:
                dest_conn.close()
        except Exception as exc:
            logger.error("Failed to backup database to %s: %s", dest, exc)
            raise
        finally:
            raw_src.close()

    def close(self) -> None:
        """Close connection pools and dispose engine resources."""
        try:
            self.engine.dispose()
            logger.debug("DatabaseManager closed for %s", self.db_path)
        except Exception as exc:
            logger.warning("Error disposing engine for %s: %s", self.db_path, exc)


_global_db_manager: DatabaseManager | None = None


def get_database(db_path: Path | None = None) -> DatabaseManager:
    """Obtain or initialize the global DatabaseManager singleton instance.

    Uses path resolution from recallx.paths by default unless an explicit
    path is provided.

    Args:
        db_path: Optional explicit database path override.

    Returns:
        Configured and initialized DatabaseManager instance.
    """
    global _global_db_manager

    if db_path is not None:
        resolved_path = Path(db_path).resolve()
    else:
        try:
            from recallx.paths import get_database_path

            resolved_path = get_database_path()
        except Exception as exc:
            logger.warning(
                "Could not load database path from paths module (%s); using platform data directory.",
                exc,
            )
            from recallx.paths import get_default_data_dir

            resolved_path = get_default_data_dir() / "recallx.db"

    if _global_db_manager is not None and _global_db_manager.db_path == resolved_path:
        return _global_db_manager

    if _global_db_manager is not None:
        _global_db_manager.close()

    manager = DatabaseManager(resolved_path)
    manager.initialize()
    _global_db_manager = manager
    return manager
