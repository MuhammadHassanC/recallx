"""Platform-aware filesystem paths and directory management for RecallX."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from recallx.config import RecallXConfig

from recallx.utils.validation import validate_project_id


def get_default_data_dir() -> Path:
    """Determine the platform-standard default data storage directory.

    Returns:
        Path to default data directory:
        - Windows: %LOCALAPPDATA%/RecallX (or ~/.local/share/recallx fallback)
        - macOS: ~/Library/Application Support/RecallX
        - Linux/POSIX: $XDG_DATA_HOME/recallx or ~/.local/share/recallx
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "RecallX"
        return Path.home() / "AppData" / "Local" / "RecallX"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "RecallX"

    # Linux and Unix-like systems (XDG Base Directory Specification)
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "recallx"
    return Path.home() / ".local" / "share" / "recallx"


def get_default_config_dir() -> Path:
    """Determine the platform-standard default configuration directory.

    Returns:
        Path to default configuration directory:
        - Windows: %APPDATA%/RecallX (or %LOCALAPPDATA%/RecallX)
        - macOS: ~/Library/Application Support/RecallX (or ~/.config/recallx)
        - Linux/POSIX: $XDG_CONFIG_HOME/recallx or ~/.config/recallx
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "RecallX"
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "RecallX"
        return Path.home() / "AppData" / "Roaming" / "RecallX"

    if sys.platform == "darwin":
        # macOS convention allows ~/Library/Application Support/RecallX or ~/.config/recallx
        mac_config = Path.home() / "Library" / "Application Support" / "RecallX"
        return mac_config

    # Linux and POSIX standards
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "recallx"
    return Path.home() / ".config" / "recallx"


def get_config_dir() -> Path:
    """Return the active configuration directory.

    Returns:
        Path to configuration directory.
    """
    return get_default_config_dir()


def get_config_file_path() -> Path:
    """Return the standard path to the TOML configuration file.

    Returns:
        Path pointing to config.toml in the config directory.
    """
    return get_config_dir() / "config.toml"


def get_data_dir() -> Path:
    """Return the active data storage directory, respecting configuration overrides.

    Returns:
        Path to data directory.
    """
    from recallx.config import get_config

    config = get_config()
    if config.data_dir is not None:
        return Path(config.data_dir).expanduser().resolve()
    return get_default_data_dir()


def get_database_path(config: Optional[RecallXConfig] = None) -> Path:
    """Return the full filesystem path to the RecallX SQLite database file.

    Args:
        config: Optional configuration instance. If omitted, uses active singleton.

    Returns:
        Path to the primary database file.
    """
    if config is None:
        from recallx.config import get_config

        config = get_config()

    if config.data_dir is not None:
        base_dir = Path(config.data_dir).expanduser().resolve()
    else:
        base_dir = get_default_data_dir()

    return base_dir / config.database_name


def get_backup_dir() -> Path:
    """Return the directory designated for automated and manual database backups.

    Returns:
        Path to the backups directory within the active data directory.
    """
    return get_data_dir() / "backups"


def get_project_dir(project_id: str) -> Path:
    """Return the isolated storage directory for a specific project.

    Args:
        project_id: Validated project identifier.

    Returns:
        Path to project workspace folder.

    Raises:
        ValueError: If project_id is invalid.
    """
    valid_id = validate_project_id(project_id)
    return get_data_dir() / "projects" / valid_id


def ensure_directories() -> None:
    """Create all required RecallX system directories if they do not exist.

    Ensures data_dir, config_dir, backup_dir, and projects root are initialized
    with safe permissions.
    """
    data_dir = get_data_dir()
    config_dir = get_config_dir()
    backup_dir = get_backup_dir()
    projects_dir = data_dir / "projects"

    for directory in (data_dir, config_dir, backup_dir, projects_dir):
        directory.mkdir(parents=True, exist_ok=True)
