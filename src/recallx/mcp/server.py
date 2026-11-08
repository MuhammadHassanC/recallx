"""RecallX MCP Server - Memory infrastructure for AI coding agents."""
from __future__ import annotations

import sys
from typing import Any
from mcp.server.fastmcp import FastMCP

# Ensure backward/forward compatibility if description is supplied to FastMCP
_orig_fastmcp_init = FastMCP.__init__


def _patched_fastmcp_init(self: Any, *args: Any, **kwargs: Any) -> None:
    if "description" in kwargs:
        kwargs.setdefault("instructions", kwargs.pop("description"))
    _orig_fastmcp_init(self, *args, **kwargs)


FastMCP.__init__ = _patched_fastmcp_init  # type: ignore[method-assign]

# Create the MCP server
mcp = FastMCP(
    "RecallX",
    description="Universal local-first persistent memory for AI coding agents. "
    "Remember project context, technical decisions, debugging solutions, "
    "and developer preferences across sessions.",
)

# Import and register all tools from tools module
from recallx.mcp import tools  # noqa: F401, E402

# Import and register all resources from resources module
from recallx.mcp import resources  # noqa: F401, E402

# Import and register all prompts from prompts module
from recallx.mcp import prompts  # noqa: F401, E402


def main() -> None:
    """Run the RecallX MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
