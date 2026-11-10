# RecallX

**Your AI's Memory, Across Every Coding Session.**

Universal local-first persistent memory for AI coding agents. Remember project context, technical decisions, debugging solutions, and developer preferences across sessions.

---

## ⚡ One-Prompt Install (For Any AI Coding Agent)

If you use **Claude Code**, **Cursor**, **Gemini CLI / Antigravity**, **Windsurf**, or **Roo Code**, simply paste this single prompt into your AI coding assistant:

> **"Install RecallX from https://github.com/MuhammadHassanC/recallx and configure my coding assistant."**

### How AI Coding Agents Install RecallX (Automated)

When an AI coding agent is given the repo URL, it executes the automated one-step installer:

```bash
git clone https://github.com/MuhammadHassanC/recallx.git
cd recallx
python install.py
```

Or via pip:

```bash
pip install git+https://github.com/MuhammadHassanC/recallx.git
recallx setup
```

**What the installer does automatically in seconds:**
1. Installs the RecallX engine and dependencies.
2. Initializes the local SQLite persistent database and FTS5 search index (`%LOCALAPPDATA%/RecallX` or `~/.local/share/recallx`).
3. Auto-detects your coding agent (`Claude Code`, `Cursor`, `Gemini CLI / Antigravity`, `Windsurf`, `Cline / Roo Code`) and configures the RecallX MCP server in their settings files (`~/.claude.json`, `.cursor/mcp.json`, `~/.gemini/settings.json`, etc.).
4. Copies the Agent Skills (`recallx-remember`, `recallx-recall`, `recallx-project-context`) into your agent's skills directory.
5. Verifies the connection so your AI agent has persistent memory active immediately.

---

## The Problem

AI coding agents lose context between sessions. Every new conversation starts from scratch. You repeatedly explain your architecture, preferences, decisions, and previous work. Context is lost, productivity suffers.

## The Solution

RecallX provides a persistent, searchable, structured memory layer that any AI coding agent can access through the Model Context Protocol (MCP). Your agent remembers what matters — automatically.

### Key Features

- **Local-first** — All data stays on your machine. No cloud, no telemetry, no external APIs.
- **Agent-independent** — Works with Claude Code, Cursor, Gemini CLI, Codex, OpenCode, and any MCP-compatible agent.
- **Project-aware** — Memories are isolated by project. No cross-contamination.
- **Intelligent retrieval** — Full-text search with relevance ranking. Optional semantic search with local embeddings.
- **Structured memories** — Project context, technical decisions, bug solutions, developer preferences, session summaries.
- **Privacy-first** — Automatic secret detection and redaction. No hidden network requests.
- **CLI + MCP** — Full-featured command line interface and Model Context Protocol server.

---

## Quick Start

### Installation

```bash
pip install recallx
```

Or with pipx for isolated installation:

```bash
pipx install recallx
```

### Initialize

```bash
recallx init
```

### Save a Memory

```bash
recallx remember "Using PostgreSQL with SQLAlchemy for the API backend" -p my-api -t decision --tags database,architecture -i 0.8
```

### Search Memories

```bash
recallx search "database architecture" -p my-api
```

### Check Status

```bash
recallx status
```

---

## MCP Integration

RecallX integrates with AI coding agents through the Model Context Protocol.

### Claude Code

Add to your Claude Code MCP settings:

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

### Cursor

Add to `.cursor/mcp.json`:

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

### Gemini CLI / Antigravity

Add to `.gemini/settings.json`:

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

Run `recallx integrate <agent>` for specific setup instructions.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `recallx init` | Initialize RecallX |
| `recallx setup` | Auto-configure detected AI coding agents and skills |
| `recallx status` | Show status |
| `recallx remember <content>` | Save a memory |
| `recallx search <query>` | Search memories |
| `recallx list` | List memories |
| `recallx show <id>` | Show memory details |
| `recallx update <id>` | Update a memory |
| `recallx delete <id>` | Delete a memory |
| `recallx project init <id>` | Initialize a project |
| `recallx project context <id>` | Show project context |
| `recallx project list` | List projects |
| `recallx export` | Export memories as JSON |
| `recallx import <file>` | Import memories |
| `recallx backup` | Create a backup |
| `recallx mcp serve` | Start MCP server |
| `recallx integrate [agent]` | Setup instructions |

---

## MCP Tools

When connected via MCP, RecallX exposes these tools to your AI agent:

| Tool | Description |
|------|-------------|
| `remember` | Save structured information for later retrieval |
| `recall` | Search for relevant memories |
| `get_memory` | Retrieve a specific memory by ID |
| `update_memory` | Update an existing memory |
| `forget` | Delete a memory |
| `list_memories` | List memories with filtering |
| `get_project_context` | Get compact project context |
| `save_session_summary` | Save a session summary |
| `consolidate_memories` | Find and merge related memories |
| `get_memory_stats` | Memory statistics |

---

## Agent Skills

RecallX includes reusable agent skills for structured memory operations:

- **recallx-remember** — Guidelines for identifying and saving durable information
- **recallx-recall** — Guidelines for retrieving relevant context before starting work
- **recallx-project-context** — Guidelines for maintaining project context

Skills are located in `src/recallx/skills/` and can be copied to your agent's skills directory.

---

## Memory Types

| Type | Description | Example |
|------|-------------|---------|
| `project` | Project architecture, stack, structure | "Using React 18 with TypeScript and Vite" |
| `decision` | Technical decisions with rationale | "Chose PostgreSQL over SQLite for concurrent writes" |
| `bug_solution` | Bugs, root causes, and fixes | "CORS error fixed by adding credentials: include" |
| `preference` | Developer coding preferences | "Always use absolute imports in Python" |
| `session` | Session summaries and status | "Completed auth flow, pending: rate limiting" |

---

## Storage and Privacy

- All data stored locally in SQLite
- Default location:
  - Windows: `%LOCALAPPDATA%\RecallX\`
  - Linux: `~/.local/share/recallx/`
  - macOS: `~/Library/Application Support/RecallX/`
- No telemetry, analytics, or external data transmission
- Automatic detection and redaction of secrets (API keys, tokens, passwords)
- Full export/import for data portability

---

## Optional Semantic Search

For enhanced retrieval, install with semantic search support:

```bash
pip install recallx[semantic]
```

This downloads a local embedding model (~90MB). No external API required. RecallX works perfectly without it — FTS5 full-text search handles most use cases.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  AI Coding Agent                │
│         (Claude, Cursor, Gemini, etc.)          │
└──────────────────────┬──────────────────────────┘
                       │ MCP (stdio)
┌──────────────────────▼──────────────────────────┐
│                  RecallX MCP Server             │
│              Tools · Resources · Prompts        │
├─────────────────────────────────────────────────┤
│                  Memory Engine                  │
│     Extraction · Retrieval · Ranking · Dedup    │
├─────────────────────────────────────────────────┤
│                  Search Layer                   │
│         FTS5 · Embeddings · Hybrid Search       │
├─────────────────────────────────────────────────┤
│                  Storage Layer                  │
│           SQLite · Repositories · Migrations    │
└─────────────────────────────────────────────────┘
```

---

## Limitations

- Semantic search requires additional disk space for the embedding model
- Memory extraction uses rule-based patterns (no LLM-powered extraction in v1)
- MCP servers cannot automatically access agent conversation histories
- Performance depends on database size (optimized for up to ~100K memories)

---

## Roadmap

- [ ] Web-based memory browser (optional)
- [ ] LLM-powered memory extraction
- [ ] Memory graph visualization
- [ ] Team/shared memory (opt-in)
- [ ] Plugin system for custom memory types
- [ ] Automatic session capture hooks

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## Security

See [SECURITY.md](SECURITY.md) for security policies and reporting.

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**RecallX** — Built with engineering discipline, privacy, and reliability as the highest priorities.
