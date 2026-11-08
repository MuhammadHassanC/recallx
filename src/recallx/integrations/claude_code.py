"""Claude Code integration for RecallX MCP server."""

from __future__ import annotations

from typing import Any


def get_config(
    *,
    use_uvx: bool = False,
    use_pipx: bool = False,
    runner: str | None = None,
) -> dict[str, Any]:
    """Generate the MCP configuration dictionary for Claude Code.

    Args:
        use_uvx: Whether to invoke recallx via uvx.
        use_pipx: Whether to invoke recallx via pipx.
        runner: Explicit runner string ('uvx', 'pipx', or 'direct').

    Returns:
        JSON-serializable dictionary matching Claude Code MCP settings format:
        {"mcpServers": {"recallx": {"command": ..., "args": [...]}}}
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
    """Return markdown setup instructions for integrating RecallX with Claude Code.

    Returns:
        Step-by-step setup and verification instructions.
    """
    return """# RecallX Integration with Claude Code

To give Claude Code persistent memory across sessions, register the RecallX MCP server.

## Option 1: Claude CLI (Recommended)
Run the following command in your terminal:
```bash
claude mcp add recallx recallx mcp serve
```

Or if running RecallX via `uvx`:
```bash
claude mcp add recallx uvx recallx mcp serve
```

## Option 2: Manual Settings Configuration
Add the configuration block below to your Claude Code configuration file:
- User level: `~/.claude.json`
- Project level: `.claude/config.json`

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

## Verification
1. Start a new Claude Code session: `claude`
2. Run `/mcp` inside the Claude Code prompt to verify `recallx` is connected.
3. Test memory recall: ask Claude "What memories do you have for this project?".
"""
