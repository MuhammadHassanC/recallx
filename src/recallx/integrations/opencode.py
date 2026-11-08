"""OpenCode integration for RecallX MCP server."""

from __future__ import annotations

from typing import Any


def get_config(
    *,
    use_uvx: bool = False,
    use_pipx: bool = False,
    runner: str | None = None,
) -> dict[str, Any]:
    """Generate configuration dictionary for OpenCode.

    Args:
        use_uvx: Whether to invoke recallx via uvx.
        use_pipx: Whether to invoke recallx via pipx.
        runner: Explicit runner string ('uvx', 'pipx', or 'direct').

    Returns:
        Configuration dictionary suitable for OpenCode MCP server configuration.
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
    """Return markdown setup instructions for integrating RecallX with OpenCode.

    Returns:
        Step-by-step setup and verification instructions.
    """
    return """# RecallX Integration with OpenCode

Connect RecallX persistent memory infrastructure to your OpenCode environment.

## OpenCode Configuration
Add RecallX to your OpenCode MCP settings file (`opencode.json` or `.opencode/settings.json`):
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

## Global Command Line Setup
Ensure RecallX is installed on your PATH:
```bash
pip install recallx
```
or run directly via:
```bash
uvx recallx mcp serve
```

## Verification
In OpenCode, run the tool check command:
`opencode tools list`
You should see `remember`, `recall`, and `get_project_context` listed.
"""
