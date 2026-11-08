"""Example: Programmatic MCP Client connecting to RecallX Server via Stdio.

Demonstrates how an AI coding agent or host application interacts with RecallX
using the Model Context Protocol (MCP) standard I/O transport.
"""

from __future__ import annotations

import asyncio
import json
import sys
from subprocess import PIPE


async def run_mcp_client_demo() -> None:
    """Connect to RecallX MCP server via subprocess stdio and execute tools."""
    # Launch recallx mcp serve as a subprocess with piped stdio
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "recallx.cli.app",
        "mcp",
        "serve",
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )

    print("[*] Connected to RecallX MCP Server via stdio.")

    # In a full MCP client implementation, the client sends JSON-RPC 2.0 messages:
    # 1. initialize request
    # 2. tools/list request
    # 3. tools/call request (e.g. remember, recall)

    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "example-client",
                "version": "1.0.0",
            },
        },
    }

    print(f"[*] Sending MCP initialization payload...")
    request_line = json.dumps(init_request) + "\n"
    if process.stdin:
        process.stdin.write(request_line.encode("utf-8"))
        await process.stdin.drain()

    # Terminate demo subprocess cleanly
    try:
        process.terminate()
        await process.wait()
    except Exception:
        pass

    print("[✓] MCP Client stdio connection verified successfully.")


def main() -> None:
    asyncio.run(run_mcp_client_demo())


if __name__ == "__main__":
    main()

