"""Cursor IDE integration for RecallX MCP server."""

from __future__ import annotations

from typing import Any


def get_config(
    *,
    use_uvx: bool = False,
    use_pipx: bool = False,
    runner: str | None = None,
) -> dict[str, Any]:
    """Generate the MCP configuration dictionary for Cursor IDE.

    Args:
        use_uvx: Whether to invoke recallx via uvx.
        use_pipx: Whether to invoke recallx via pipx.
        runner: Explicit runner string ('uvx', 'pipx', or 'direct').

    Returns:
        Configuration dictionary suitable for Cursor's .cursor/mcp.json.
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
    """Return markdown setup instructions for integrating RecallX with Cursor IDE.

    Returns:
        Step-by-step setup and verification instructions.
    """
    return """# RecallX Integration with Cursor IDE

Enable persistent cross-session memory in Cursor Agent and Composer.

## Method 1: Project-level Configuration (Recommended)
Create or edit `.cursor/mcp.json` at the root of your project:
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

## Method 2: Global Cursor Settings
1. Open Cursor Settings (`Ctrl+Shift+J` or `Cmd+Shift+J`).
2. Navigate to **Features** > **MCP**.
3. Click **+ Add New MCP Server**.
4. Configure:
   - **Name**: `recallx`
   - **Type**: `command`
   - **Command**: `recallx mcp serve`
5. Click **Add**. The status indicator should turn green.

## Verification
Open Cursor Composer (`Ctrl+I` or `Cmd+I`) and ask:
"Check your memory using RecallX tools for this project."
"""
