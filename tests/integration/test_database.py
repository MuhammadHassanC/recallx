"""Integration tests for DatabaseManager SQLite operations and lifecycle."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from recallx.storage.database import DatabaseManager


def test_initialize_creates_tables(db: DatabaseManager) -> None:
    """Ensure that initialize creates primary relational tables."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    assert "memories" in table_names, "Table 'memories' must exist after initialization"
    assert "projects" in table_names, "Table 'projects' must exist after initialization"


def test_initialize_creates_fts_table(db: DatabaseManager) -> None:
    """Ensure that initialize creates the FTS5 full-text search table."""
    with db.engine.connect() as conn:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_fts'")
        ).scalar()

    assert result == "memory_fts", "Virtual table 'memory_fts' must exist after initialization"


def test_verify_integrity(db: DatabaseManager) -> None:
    """Ensure that database integrity check passes on a valid database."""
    assert db.verify_integrity() is True, "Database integrity verification should succeed"


def test_backup_creates_file(db: DatabaseManager, tmp_path: Path) -> None:
    """Ensure online backup produces a non-empty SQLite database file."""
    backup_file = tmp_path / "backup.db"
    db.backup(backup_file)

    assert backup_file.is_file(), "Backup file should be created"
    assert backup_file.stat().st_size > 0, "Backup file should not be empty"

    # Verify backup database integrity
    backup_mgr = DatabaseManager(backup_file)
    try:
        assert backup_mgr.verify_integrity() is True
    finally:
        backup_mgr.close()


def test_wal_mode_enabled(db: DatabaseManager) -> None:
    """Ensure Write-Ahead Logging (WAL) journal mode is enabled for disk databases."""
    with db.engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()

    assert str(journal_mode).lower() == "wal", f"Expected WAL journal mode, got {journal_mode}"


def test_foreign_keys_enabled(db: DatabaseManager) -> None:
    """Ensure SQLite foreign key constraints are enabled."""
    with db.engine.connect() as conn:
        fk_status = conn.execute(text("PRAGMA foreign_keys")).scalar()

    assert fk_status == 1, "PRAGMA foreign_keys must be enabled (1)"


def test_db_size_positive(db: DatabaseManager) -> None:
    """Ensure get_db_size returns a positive byte size for initialized databases."""
    size = db.get_db_size()
    assert size > 0, f"Database size should be greater than 0, got {size}"
