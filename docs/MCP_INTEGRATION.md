# Model Context Protocol (MCP) Integration

The **Model Context Protocol (MCP)** is an open standard enabling AI coding assistants to securely interact with local developer tools, databases, and context servers. RecallX exposes a full-featured MCP server that runs locally over standard input/output (`stdio`), allowing agents to persist and query structured memory on demand.

---

## Protocol Overview

RecallX implements the MCP protocol via standard input and output streams (`stdio`) using JSON-RPC 2.0 messages:

- **No open network ports**: Operates strictly within local subprocess pipes spawned by the agent.
- **Zero third-party telemetry**: Queries and tool parameters never leave your local machine.
- **Bi-directional safety**: Secrets and sensitive credentials within memory payloads are automatically scanned and redacted before storage.

---

## Agent Configuration Guides

### 1. Claude Code

Claude Code supports MCP servers registered in your user or project MCP configuration.

#### Automated Configuration via Claude CLI:
```bash
claude mcp add recallx recallx mcp serve
```

#### Manual Configuration:
Add the following to your Claude Code configuration file:
- On Linux / macOS: `~/.claude/mcp.json` or `~/.config/claude/mcp.json`
- On Windows: `%APPDATA%\Claude\mcp.json`

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

If you installed RecallX inside an isolated virtual environment, supply the full path to the executable:
```json
{
  "mcpServers": {
    "recallx": {
      "command": "/home/user/.venv/bin/recallx",
      "args": ["mcp", "serve"]
    }
  }
}
```

---

### 2. Cursor IDE

Cursor supports MCP servers configured at the workspace level (`.cursor/mcp.json`) or globally via IDE settings.

Create or update `.cursor/mcp.json` in your workspace root:

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

If RecallX was installed via `uvx` or `pipx`:
```json
{
  "mcpServers": {
    "recallx": {
      "command": "pipx",
      "args": ["run", "recallx", "mcp", "serve"]
    }
  }
}
```

After modifying `.cursor/mcp.json`, restart Cursor or reload the MCP server list under Cursor Settings > Features > MCP.

---

### 3. Gemini CLI / Antigravity

For Gemini CLI and Antigravity environments, register RecallX in `.gemini/settings.json` (or `%USERPROFILE%\.gemini\settings.json`):

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

---

### 4. Codex and OpenCode

For OpenCode or generic MCP clients that read JSON configuration:

```json
{
  "mcpServers": {
    "recallx": {
      "command": "recallx",
      "args": ["mcp", "serve"],
      "env": {
        "RECALLX_LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

---

## CLI Integration Helper

RecallX provides an interactive integration command that outputs ready-to-use configuration blocks and instructions:

```bash
# Print instructions for all supported agents
recallx integrate

# Print instructions for a specific agent
recallx integrate claude-code
recallx integrate cursor
recallx integrate gemini-cli
```

---

## Available MCP Tools Reference

When connected, RecallX registers the following 10 MCP tools:

### 1. `remember`
Save durable information to persistent memory.
- **Parameters**:
  - `content` *(string, required)*: Clear, concise description of the memory.
  - `project_id` *(string, required)*: Identifier for the current project codebase.
  - `memory_type` *(string, optional, default: `"project"`)*: One of `project`, `decision`, `bug_solution`, `preference`, `session`.
  - `tags` *(array of strings, optional)*: Categorization tags (e.g., `["auth", "jwt"]`).
  - `importance` *(number, optional, default: `0.5`)*: Float between `0.0` and `1.0`.

### 2. `recall`
Search for relevant memories matching a query.
- **Parameters**:
  - `query` *(string, required)*: Search keywords or question.
  - `project_id` *(string, optional)*: Filter memories to a specific project.
  - `memory_type` *(string, optional)*: Filter memories by type.
  - `tags` *(array of strings, optional)*: Filter memories by tag match.
  - `limit` *(integer, optional, default: `10`)*: Maximum number of results.

### 3. `get_memory`
Retrieve a single memory record by its unique identifier.
- **Parameters**:
  - `memory_id` *(string, required)*: The unique memory ID (e.g., `mem_01hq...`).

### 4. `update_memory`
Update an existing memory's content, tags, or importance.
- **Parameters**:
  - `memory_id` *(string, required)*: Memory ID to modify.
  - `content` *(string, optional)*: Updated text body.
  - `tags` *(array of strings, optional)*: Updated tags list.
  - `importance` *(number, optional)*: Updated importance score (`0.0` to `1.0`).

### 5. `forget`
Delete a specific memory by ID.
- **Parameters**:
  - `memory_id` *(string, required)*: ID of the memory to remove.

### 6. `list_memories`
List memories with pagination and attribute filtering.
- **Parameters**:
  - `project_id` *(string, optional)*: Scoped project identifier.
  - `memory_type` *(string, optional)*: Filter by memory type.
  - `limit` *(integer, optional, default: `20`)*: Number of items.
  - `offset` *(integer, optional, default: `0`)*: Offset index.

### 7. `get_project_context`
Get an aggregated, compact context block summarizing key architecture, decisions, and preferences for a project.
- **Parameters**:
  - `project_id` *(string, required)*: Project to summarize.
  - `max_tokens` *(integer, optional, default: `1500`)*: Token budget constraint for the context snippet.

### 8. `save_session_summary`
Persist a summary of work completed, decisions reached, and pending tasks at the conclusion of a session.
- **Parameters**:
  - `project_id` *(string, required)*: Project identifier.
  - `summary` *(string, required)*: Summary of accomplishments and current state.
  - `pending_tasks` *(array of strings, optional)*: Work items remaining for future sessions.

### 9. `consolidate_memories`
Identify and merge overlapping or obsolete memories for a project.
- **Parameters**:
  - `project_id` *(string, required)*: Target project identifier.
  - `dry_run` *(boolean, optional, default: `true`)*: If true, reports potential merges without modifying data.

### 10. `get_memory_stats`
Retrieve database and operational statistics.
- **Parameters**:
  - `project_id` *(string, optional)*: Optional project filter.

---

## Verifying and Debugging MCP

To test the MCP server directly from your terminal, execute:

```bash
recallx mcp serve
```

The process will start and wait for JSON-RPC messages on `stdin`. You can send an initialization request:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0.0"}}}
```

RecallX will reply with its server capabilities and tool inventory. Press `Ctrl+C` to terminate the test session.
