"""OpenAI Codex and OpenAI Assistant CLI integration for RecallX MCP server."""

from __future__ import annotations

from typing import Any


def get_config(
    *,
    use_uvx: bool = False,
    use_pipx: bool = False,
    runner: str | None = None,
) -> dict[str, Any]:
    """Generate configuration dictionary for OpenAI Codex / Assistant environments.

    Args:
        use_uvx: Whether to invoke recallx via uvx.
        use_pipx: Whether to invoke recallx via pipx.
        runner: Explicit runner string ('uvx', 'pipx', or 'direct').

    Returns:
        Configuration dictionary suitable for Codex MCP integrations.
    """
    selected_runner = runner or ("uvx" if use_uvx else ("pipx" if use_pipx else "direct"))

    if selected_runner == "uvx":
        command = "uvx"
        args = ["recallx", "mcp", "serve"]
    elif selected_runner == "pipx":
        command = "pipx"
        args = ["run", "recallx", "mcp", "serve"]
    else:
        command = "recallx"
        args = ["mcp", "serve"]

    return {
        "mcpServers": {
            "recallx": {
                "command": command,
                "args": args,
            }
        }
    }


def get_instructions() -> str:
    """Return markdown setup instructions for integrating RecallX with OpenAI Codex.

    Returns:
        Step-by-step setup and verification instructions.
    """
    return """# RecallX Integration with OpenAI Codex & Assistant CLIs

Equip OpenAI Codex and autonomous coding agents with local persistent memory.

## MCP Configuration
Add RecallX to your agent environment configuration (e.g. `codex_config.json` or MCP settings):
```json
{
  "mcpServers": {
    "recallx": {
      "command": "recallx",
      "args": ["mcp", "serve"]
    }
  }
}
```

## Direct Python Runner
When embedding inside custom Python scripts or orchestration pipelines:
```bash
python -m recallx.cli.app mcp serve
```

## Verification
Query the server directly or initiate an agent run:
"Using your recall tools, find previous architectural decisions about database design."
"""
