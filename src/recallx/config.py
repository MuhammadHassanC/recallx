"""Configuration management for RecallX.

Handles loading, validating, updating, and saving configuration settings
from TOML files and environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Support pydantic-settings if available; fall back to BaseModel
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _SETTINGS_BASE = BaseSettings
except ImportError:
    _SETTINGS_BASE = BaseModel  # type: ignore[misc,assignment]
    SettingsConfigDict = None  # type: ignore[misc,assignment]

# Toml loader compatibility (Python 3.11+ tomllib vs tomli)
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from recallx.utils.validation import DEFAULT_SECRET_PATTERNS


class RecallXConfig(_SETTINGS_BASE):
    """Configuration model for RecallX runtime and persistence settings."""

    # Storage and database
    data_dir: Optional[Path] = Field(
        default=None,
        description="Custom directory override for all persistent data storage.",
    )
    database_name: str = Field(
        default="recallx.db",
        description="Filename of the primary SQLite database.",
    )
    default_project: Optional[str] = Field(
        default=None,
        description="Default project identifier to use when none is explicitly specified.",
    )

    # Retrieval and semantic parameters
    max_search_results: int = Field(
        default=20,
        ge=1,
        le=1000,
        description="Default maximum number of search results to return.",
    )
    relevance_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum score threshold for semantic and hybrid similarity results.",
    )
    enable_semantic_search: bool = Field(
        default=False,
        description="Flag to enable vector embedding search (requires sentence-transformers).",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Local Hugging Face sentence transformer model name for vector embeddings.",
    )
    embedding_dimensions: int = Field(
        default=384,
        ge=1,
        description="Vector embedding dimension for the configured model.",
    )

    # Security and secrets
    secret_patterns: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SECRET_PATTERNS),
        description="Regular expression patterns evaluated to detect and redact sensitive credentials.",
    )

    # Logging and output formatting
    log_level: str = Field(
        default="WARNING",
        description="Application logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )
    json_output: bool = Field(
        default=False,
        description="Format all command and inspection output as raw structured JSON.",
    )
    quiet: bool = Field(
        default=False,
        description="Suppress non-essential console status messages and warnings.",
    )

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_prefix="RECALLX_",
            env_file_encoding="utf-8",
            extra="ignore",
        )
    else:
        model_config = ConfigDict(extra="ignore")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> RecallXConfig:
        """Load configuration from a TOML file with environment variable overrides.

        Args:
            path: Optional custom path to a config TOML file.

        Returns:
            Validated RecallXConfig instance.
        """
        return load_config(path)

    def save(self, path: Optional[Path] = None) -> Path:
        """Persist current configuration to a TOML file.

        Args:
            path: Target file path. Defaults to standard platform config.toml.

        Returns:
            Resolved Path of the saved file.
        """
        return save_config(self, path)


def _serialize_toml(config_dict: dict[str, Any]) -> str:
    """Serialize configuration dictionary to clean TOML text without external dependencies."""
    lines: list[str] = [
        "# RecallX Configuration",
        "# Universal local-first persistent memory for AI coding agents",
        "",
    ]

    scalars: dict[str, Any] = {}
    lists: dict[str, list[Any]] = {}

    for k, v in config_dict.items():
        if isinstance(v, list):
            lists[k] = v
        else:
            scalars[k] = v

    for k, v in scalars.items():
        if v is None:
            continue
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        elif isinstance(v, (str, Path)):
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{escaped}"')

    lines.append("")

    for k, items in lists.items():
        lines.append(f"{k} = [")
        for item in items:
            escaped_item = str(item).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  "{escaped_item}",')
        lines.append("]")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _read_env_overrides() -> dict[str, Any]:
    """Parse RECALLX_* environment variables into configuration dictionary keys."""
    overrides: dict[str, Any] = {}

    env_map = {
        "RECALLX_DATA_DIR": ("data_dir", lambda val: Path(val)),
        "RECALLX_DATABASE_NAME": ("database_name", str),
        "RECALLX_DEFAULT_PROJECT": ("default_project", str),
        "RECALLX_MAX_SEARCH_RESULTS": ("max_search_results", int),
        "RECALLX_RELEVANCE_THRESHOLD": ("relevance_threshold", float),
        "RECALLX_ENABLE_SEMANTIC_SEARCH": (
            "enable_semantic_search",
            lambda val: val.strip().lower() in ("1", "true", "yes", "on"),
        ),
        "RECALLX_EMBEDDING_MODEL": ("embedding_model", str),
        "RECALLX_EMBEDDING_DIMENSIONS": ("embedding_dimensions", int),
        "RECALLX_LOG_LEVEL": ("log_level", str),
        "RECALLX_JSON_OUTPUT": (
            "json_output",
            lambda val: val.strip().lower() in ("1", "true", "yes", "on"),
        ),
        "RECALLX_QUIET": (
            "quiet",
            lambda val: val.strip().lower() in ("1", "true", "yes", "on"),
        ),
    }

    for env_key, (field_name, converter) in env_map.items():
        val = os.environ.get(env_key)
        if val is not None and val != "":
            try:
                overrides[field_name] = converter(val)
            except (ValueError, TypeError):
                continue

    return overrides


def find_config_file(explicit_path: Optional[Path] = None) -> Optional[Path]:
    """Locate the configuration file if it exists.

    Checks explicit path, RECALLX_CONFIG environment variable, platform config directory,
    and standard ~/.config/recallx/config.toml.

    Args:
        explicit_path: Explicitly provided candidate path.

    Returns:
        Path to existing file, or None if not found.
    """
    if explicit_path is not None:
        p = Path(explicit_path).expanduser().resolve()
        return p if p.is_file() else None

    env_path = os.environ.get("RECALLX_CONFIG")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file():
            return p

    # Platform-specific location
    from recallx.paths import get_config_file_path

    platform_path = get_config_file_path()
    if platform_path.is_file():
        return platform_path

    # Posix fallback ~/.config/recallx/config.toml
    fallback_posix = Path.home() / ".config" / "recallx" / "config.toml"
    if fallback_posix.is_file():
        return fallback_posix

    return None


def load_config(path: Optional[Path] = None) -> RecallXConfig:
    """Load and validate configuration from TOML and environment variables.

    Args:
        path: Optional explicit configuration file path.

    Returns:
        Instantiated and validated RecallXConfig object.
    """
    data: dict[str, Any] = {}

    target_path = find_config_file(path)
    if target_path and target_path.is_file():
        try:
            with open(target_path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            data = {}

    # Layer environment variable overrides
    env_overrides = _read_env_overrides()
    data.update(env_overrides)

    return RecallXConfig.model_validate(data)


def save_config(config: RecallXConfig, path: Optional[Path] = None) -> Path:
    """Write configuration out to a TOML file, ensuring directory structure exists.

    Args:
        config: RecallXConfig instance to serialize.
        path: Optional destination path. Defaults to standard platform path.

    Returns:
        Resolved Path where the file was written.
    """
    if path is None:
        from recallx.paths import get_config_file_path

        dest_path = get_config_file_path()
    else:
        dest_path = Path(path).expanduser().resolve()

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    toml_content = _serialize_toml(config.model_dump())
    dest_path.write_text(toml_content, encoding="utf-8")
    return dest_path


# Global singleton instance cache
_GLOBAL_CONFIG: Optional[RecallXConfig] = None


def get_config(reload: bool = False) -> RecallXConfig:
    """Obtain the active RecallX configuration singleton.

    Args:
        reload: If True, force re-reading the configuration from disk and environment.

    Returns:
        Active RecallXConfig singleton.
    """
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None or reload:
        _GLOBAL_CONFIG = load_config()
    return _GLOBAL_CONFIG


def set_config(config: RecallXConfig) -> None:
    """Manually assign the active configuration singleton.

    Args:
        config: New RecallXConfig to set.
    """
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = config


def update_config(**kwargs: Any) -> RecallXConfig:
    """Update specific settings in the active configuration and return the updated instance.

    Args:
        **kwargs: Key-value configuration parameters to update.

    Returns:
        Updated RecallXConfig instance.
    """
    current = get_config()
    dumped = current.model_dump()
    dumped.update(kwargs)
    new_config = RecallXConfig.model_validate(dumped)
    set_config(new_config)
    return new_config
