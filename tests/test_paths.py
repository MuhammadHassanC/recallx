"""Tests for filesystem and path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from recallx.config import RecallXConfig, set_config
from recallx.paths import (
    ensure_directories,
    get_backup_dir,
    get_config_dir,
    get_config_file_path,
    get_data_dir,
    get_database_path,
    get_project_dir,
)


def test_paths_defaults() -> None:
    data_dir = get_data_dir()
    config_dir = get_config_dir()
    db_path = get_database_path()
    backup_dir = get_backup_dir()

    assert isinstance(data_dir, Path)
    assert isinstance(config_dir, Path)
    assert isinstance(db_path, Path)
    assert isinstance(backup_dir, Path)

    assert db_path.name == "recallx.db"
    assert backup_dir == data_dir / "backups"
    assert get_config_file_path().name == "config.toml"


def test_paths_config_override(tmp_path: Path) -> None:
    custom_data = tmp_path / "custom_recallx"
    cfg = RecallXConfig(data_dir=custom_data, database_name="custom.sqlite")
    set_config(cfg)

    try:
        assert get_data_dir() == custom_data.resolve()
        assert get_database_path() == custom_data.resolve() / "custom.sqlite"
        assert get_backup_dir() == custom_data.resolve() / "backups"

        proj_dir = get_project_dir("alpha-proj")
        assert proj_dir == custom_data.resolve() / "projects" / "alpha-proj"
    finally:
        # Reset config
        set_config(RecallXConfig())


def test_get_project_dir_validation() -> None:
    with pytest.raises(ValueError):
        get_project_dir("invalid/project/id")


def test_ensure_directories(tmp_path: Path) -> None:
    test_storage = tmp_path / "test_storage"
    cfg = RecallXConfig(data_dir=test_storage)
    set_config(cfg)

    try:
        ensure_directories()
        assert test_storage.is_dir()
        assert (test_storage / "backups").is_dir()
        assert (test_storage / "projects").is_dir()
    finally:
        set_config(RecallXConfig())
