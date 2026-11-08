"""Registry and resolution helpers for RecallX agent integrations."""

from __future__ import annotations

from types import ModuleType
from typing import Any

from recallx.integrations import claude_code, codex, cursor, gemini_cli, opencode

# Canonical integration names
CANONICAL_INTEGRATIONS: list[str] = [
    "claude-code",
    "cursor",
    "gemini-cli",
    "codex",
    "opencode",
]

# Mapping supporting both canonical names and common aliases
INTEGRATIONS: dict[str, ModuleType] = {
    "claude-code": claude_code,
    "claude_code": claude_code,
    "claude": claude_code,
    "cursor": cursor,
    "gemini-cli": gemini_cli,
    "gemini_cli": gemini_cli,
    "gemini": gemini_cli,
    "antigravity": gemini_cli,
    "codex": codex,
    "openai-codex": codex,
    "openai_codex": codex,
    "opencode": opencode,
    "open-code": opencode,
    "open_code": opencode,
}


def normalize_name(name: str) -> str:
    """Normalize integration identifier for case- and separator-insensitive matching.

    Args:
        name: Raw identifier (e.g. 'Claude_Code', 'gemini-cli').

    Returns:
        Normalized lowercase string.
    """
    return name.strip().lower().replace("_", "-")


def list_integrations() -> list[str]:
    """Return the list of canonical supported integration identifiers.

    Returns:
        List of standard integration names.
    """
    return list(CANONICAL_INTEGRATIONS)


def get_integration(name: str) -> ModuleType:
    """Resolve an integration module by name or alias.

    Args:
        name: Integration identifier (e.g., 'claude-code', 'cursor', 'gemini-cli').

    Returns:
        Module implementing get_config() and get_instructions().

    Raises:
        ValueError: If the integration name is unrecognized.
    """
    normalized = normalize_name(name)
    module = INTEGRATIONS.get(normalized) or INTEGRATIONS.get(name.strip().lower())
    if module is None:
        supported = ", ".join(f"'{k}'" for k in CANONICAL_INTEGRATIONS)
        raise ValueError(
            f"Unknown integration '{name}'. Supported integrations: {supported}."
        )
    return module


def get_all_configs(*, runner: str | None = None) -> dict[str, dict[str, Any]]:
    """Generate configuration blocks for all canonical integrations.

    Args:
        runner: Optional explicit runner ('direct', 'uvx', 'pipx') passed to get_config().

    Returns:
        Dictionary mapping canonical integration name to its configuration dictionary.
    """
    configs: dict[str, dict[str, Any]] = {}
    for name in CANONICAL_INTEGRATIONS:
        module = INTEGRATIONS[name]
        if hasattr(module, "get_config"):
            configs[name] = module.get_config(runner=runner) if runner else module.get_config()
    return configs
