"""Gemini CLI and Antigravity agent integration for RecallX MCP server."""

from __future__ import annotations

from typing import Any


def get_config(
    *,
    use_uvx: bool = False,
    use_pipx: bool = False,
    runner: str | None = None,
) -> dict[str, Any]:
    """Generate the MCP configuration dictionary for Gemini CLI / Antigravity.

    Args:
        use_uvx: Whether to invoke recallx via uvx.
        use_pipx: Whether to invoke recallx via pipx.
        runner: Explicit runner string ('uvx', 'pipx', or 'direct').

    Returns:
        Configuration dictionary suitable for .gemini/settings.json.
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
    """Return markdown setup instructions for Gemini CLI / Antigravity.

    Returns:
        Step-by-step setup and verification instructions.
    """
    return """# RecallX Integration with Gemini CLI & Antigravity

Integrate RecallX memory infrastructure with Gemini CLI and Antigravity autonomous workflows.

## Configuration File
Add the `mcpServers` entry to your settings file:
- User global: `~/.gemini/settings.json`
- Workspace local: `.gemini/settings.json`

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

## Running with isolated environments
If RecallX is installed in an isolated environment via `uvx`:
```json
{
  "mcpServers": {
    "recallx": {
      "command": "uvx",
      "args": ["recallx", "mcp", "serve"]
    }
  }
}
```

## Skills Integration
RecallX includes prebuilt agent skills that integrate seamlessly into Antigravity:
- `recallx-remember`: Triggered on major architectural decisions and bug resolutions
- `recallx-recall`: Triggered at session start to pull context
- `recallx-project-context`: Manages overall architecture and session summaries
"""
