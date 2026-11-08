# Frequently Asked Questions (FAQ)

### General

#### What is RecallX?
RecallX is a local-first persistent memory infrastructure for AI coding agents. It provides a structured, searchable storage layer accessed via the Model Context Protocol (MCP) or command-line interface (CLI), allowing AI agents to retain architectural decisions, bug solutions, project context, and user preferences across multiple sessions.

#### Does RecallX send any data to the cloud or third-party APIs?
**No.** RecallX has zero cloud dependencies, zero telemetry, and zero tracking code. All memories, indexes, and configuration files remain strictly on your local computer.

#### Does RecallX work completely offline?
**Yes.** RecallX runs 100% offline. SQLite FTS5 full-text search operates locally with zero network calls. Even if you enable the optional semantic search feature (`recallx[semantic]`), the embedding models run locally on your CPU/GPU after their initial one-time download.

---

### Storage and Portability

#### Where are my memories stored?
By default, memories are stored in an SQLite database (`recallx.db`) in your platform's standard local data directory:
- **Windows**: `%LOCALAPPDATA%\RecallX\recallx.db`
- **Linux**: `~/.local/share/recallx/recallx.db` (or `$XDG_DATA_HOME/recallx/recallx.db`)
- **macOS**: `~/Library/Application Support/RecallX/recallx.db`

You can override this directory by setting `RECALLX_DATA_DIR` or editing `config.toml`.

#### How do I backup my memories?
Create a transactional backup of your active database at any time using:
```bash
recallx backup
```
RecallX creates a timestamped copy in your backups directory. You can also export your memories to clean JSON:
```bash
recallx export -o my_memories.json
```

#### How do I restore or migrate memories to a new machine?
To restore from a JSON export:
```bash
recallx import my_memories.json
```
Alternatively, simply copy the `recallx.db` file directly to the data directory on your new computer.

---

### Performance and Scale

#### How many memories can RecallX handle?
RecallX is optimized for up to **100,000 memories** per developer workstation. SQLite with Write-Ahead Logging (WAL) and FTS5 indexes executes search queries in sub-millisecond to low millisecond times even across tens of thousands of records.

#### What happens if my terminal or IDE crashes during a session?
RecallX uses SQLite ACID transactions with Write-Ahead Logging (WAL). If your agent process or IDE crashes unexpectedly, the database recovers automatically without data corruption. Any committed memory remains safe.

---

### Multi-Project Workflows

#### Can I use RecallX across multiple projects without context contamination?
**Yes.** All memories are tagged with a `project_id`. When an agent works on Project A, it queries memories scoped to `project_id="Project A"`. Memories from Project B will not contaminate the context window unless explicitly queried without a project filter.

#### How do I set a default project?
You can set a default project in `config.toml`:
```toml
default_project = "my-api"
```
Or set the environment variable:
```bash
export RECALLX_DEFAULT_PROJECT="my-api"
```

---

### Privacy and Security

#### How does RecallX handle secrets and credentials?
RecallX automatically scans all incoming memory text against regular expression patterns for known API keys, private tokens, passwords in URLs, and private cryptographic keys. Any identified credential is automatically replaced with `[REDACTED]` prior to saving.

#### Can other users on my computer access my memories?
RecallX creates its database files with user-level permissions. If your operating system user account is secured and you use standard disk encryption (such as BitLocker or FileVault), other accounts cannot read your memories.

---

### MCP and Agents

#### Which AI coding agents work with RecallX?
Any coding agent or client supporting the **Model Context Protocol (MCP)** over `stdio`. This includes:
- Claude Code
- Cursor IDE
- Gemini CLI / Antigravity
- Codex
- OpenCode
- Custom MCP client implementations

#### How do I check if the MCP server is working?
Run `recallx mcp serve` directly from your command line. If the server starts and waits quietly on `stdin`, it is functioning properly. You can also run `recallx status` to verify database health and memory count.
