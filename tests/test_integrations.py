"""Unit tests for RecallX integrations and MCP configuration generators."""

from __future__ import annotations

import pytest

from recallx.integrations import (
    INTEGRATIONS,
    claude_code,
    codex,
    cursor,
    gemini_cli,
    get_all_configs,
    get_integration,
    list_integrations,
    opencode,
)


def test_list_integrations() -> None:
    """Test listing canonical integrations."""
    canonical = list_integrations()
    assert "claude-code" in canonical
    assert "cursor" in canonical
    assert "gemini-cli" in canonical
    assert "codex" in canonical
    assert "opencode" in canonical


def test_claude_code_config() -> None:
    """Test Claude Code MCP configuration."""
    cfg = claude_code.get_config()
    assert "mcpServers" in cfg
    assert "recallx" in cfg["mcpServers"]
    assert cfg["mcpServers"]["recallx"]["command"] == "recallx"
    assert cfg["mcpServers"]["recallx"]["args"] == ["mcp", "serve"]

    # Test uvx runner
    cfg_uvx = claude_code.get_config(use_uvx=True)
    assert cfg_uvx["mcpServers"]["recallx"]["command"] == "uvx"
    assert cfg_uvx["mcpServers"]["recallx"]["args"] == ["recallx", "mcp", "serve"]

    # Test pipx runner
    cfg_pipx = claude_code.get_config(use_pipx=True)
    assert cfg_pipx["mcpServers"]["recallx"]["command"] == "pipx"
    assert cfg_pipx["mcpServers"]["recallx"]["args"] == ["run", "recallx", "mcp", "serve"]

    instructions = claude_code.get_instructions()
    assert "claude mcp add recallx" in instructions
    assert "mcpServers" in instructions


def test_cursor_config() -> None:
    """Test Cursor MCP configuration."""
    cfg = cursor.get_config()
    assert "mcpServers" in cfg
    assert cfg["mcpServers"]["recallx"]["command"] == "recallx"

    instructions = cursor.get_instructions()
    assert ".cursor/mcp.json" in instructions


def test_gemini_cli_config() -> None:
    """Test Gemini CLI / Antigravity MCP configuration."""
    cfg = gemini_cli.get_config()
    assert "mcpServers" in cfg
    assert cfg["mcpServers"]["recallx"]["command"] == "recallx"

    instructions = gemini_cli.get_instructions()
    assert ".gemini/settings.json" in instructions
    assert "recallx-remember" in instructions


def test_codex_config() -> None:
    """Test OpenAI Codex configuration."""
    cfg = codex.get_config()
    assert "mcpServers" in cfg
    assert cfg["mcpServers"]["recallx"]["command"] == "recallx"

    instructions = codex.get_instructions()
    assert "OpenAI Codex" in instructions


def test_opencode_config() -> None:
    """Test OpenCode configuration."""
    cfg = opencode.get_config()
    assert "mcpServers" in cfg
    assert cfg["mcpServers"]["recallx"]["command"] == "recallx"

    instructions = opencode.get_instructions()
    assert "OpenCode" in instructions


def test_get_integration_resolution() -> None:
    """Test resolving integrations by canonical name and aliases."""
    assert get_integration("claude-code") is claude_code
    assert get_integration("claude_code") is claude_code
    assert get_integration("claude") is claude_code

    assert get_integration("cursor") is cursor

    assert get_integration("gemini-cli") is gemini_cli
    assert get_integration("gemini_cli") is gemini_cli
    assert get_integration("antigravity") is gemini_cli

    assert get_integration("codex") is codex
    assert get_integration("opencode") is opencode

    with pytest.raises(ValueError, match="Unknown integration"):
        get_integration("non-existent-agent")


def test_get_all_configs() -> None:
    """Test retrieving all canonical configurations."""
    all_configs = get_all_configs()
    canonical = list_integrations()

    for name in canonical:
        assert name in all_configs
        assert "mcpServers" in all_configs[name]
        assert "recallx" in all_configs[name]["mcpServers"]
