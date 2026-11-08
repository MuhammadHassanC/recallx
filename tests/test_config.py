"""Tests for configuration management."""

from __future__ import annotations

from pathlib import Path

from recallx.config import (
    RecallXConfig,
    get_config,
    load_config,
    save_config,
    set_config,
    update_config,
)


def test_config_defaults() -> None:
    cfg = RecallXConfig()
    assert cfg.database_name == "recallx.db"
    assert cfg.max_search_results == 20
    assert cfg.relevance_threshold == 0.3
    assert cfg.enable_semantic_search is False
    assert cfg.embedding_model == "all-MiniLM-L6-v2"
    assert cfg.embedding_dimensions == 384
    assert cfg.log_level == "WARNING"
    assert cfg.json_output is False
    assert cfg.quiet is False
    assert len(cfg.secret_patterns) > 0


def test_config_save_and_load(tmp_path: Path) -> None:
    cfg_file = tmp_path / "custom_config.toml"
    custom_cfg = RecallXConfig(
        database_name="custom_test.db",
        max_search_results=45,
        relevance_threshold=0.75,
        enable_semantic_search=True,
        log_level="DEBUG",
        json_output=True,
        quiet=True,
    )

    saved_path = save_config(custom_cfg, cfg_file)
    assert saved_path == cfg_file
    assert cfg_file.is_file()

    loaded = load_config(cfg_file)
    assert loaded.database_name == "custom_test.db"
    assert loaded.max_search_results == 45
    assert loaded.relevance_threshold == 0.75
    assert loaded.enable_semantic_search is True
    assert loaded.log_level == "DEBUG"
    assert loaded.json_output is True
    assert loaded.quiet is True


def test_update_config() -> None:
    set_config(RecallXConfig())
    updated = update_config(max_search_results=50, default_project="proj_main")
    assert updated.max_search_results == 50
    assert updated.default_project == "proj_main"
    assert get_config().max_search_results == 50
