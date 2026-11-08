# Configuration Reference

RecallX supports layered configuration. Settings can be specified in a user configuration file (`config.toml`), overridden by environment variables prefixed with `RECALLX_`, or supplied via CLI flags.

---

## Configuration File Locations

Upon running `recallx init`, RecallX writes a default configuration file to the platform standard configuration directory:

| Operating System | Default Configuration File Path |
|---|---|
| **Windows** | `%APPDATA%\RecallX\config.toml` |
| **Linux / POSIX** | `~/.config/recallx/config.toml` (or `$XDG_CONFIG_HOME/recallx/config.toml`) |
| **macOS** | `~/Library/Application Support/RecallX/config.toml` |

---

## Example `config.toml`

```toml
# RecallX Configuration

# Storage and Database Settings
# data_dir = "/custom/path/to/data"
database_name = "recallx.db"
# default_project = "my-active-project"

# Retrieval & Search Settings
max_search_results = 20
relevance_threshold = 0.3
enable_semantic_search = false
embedding_model = "all-MiniLM-L6-v2"
embedding_dimensions = 384

# Logging and Output
log_level = "WARNING"
json_output = false
quiet = false

# Custom Secret Redaction Patterns (Regular Expressions)
# Uncomment to augment built-in secret patterns
# secret_patterns = [
#     "my_company_pat_[A-Za-z0-9]{32}",
#     "internal_token_[0-9a-f]{40}"
# ]
```

---

## Configuration Keys Reference

The following table documents every available configuration option:

| Option | Type | Default | Description |
|---|---|---|---|
| `data_dir` | string / path | `null` | Custom path override for the data directory containing the SQLite database and backups. If not set, the platform default is used. |
| `database_name` | string | `"recallx.db"` | Filename of the SQLite database located within `data_dir`. |
| `default_project` | string | `null` | Default project identifier assumed when `--project` / `-p` is omitted in CLI commands. |
| `max_search_results`| integer | `20` | Maximum number of results returned by search queries (range: 1 to 1000). |
| `relevance_threshold`| float | `0.3` | Minimum relevance score (0.0 to 1.0) required for a memory to appear in retrieval results. |
| `enable_semantic_search` | boolean | `false` | Enable vector embedding search. Requires installing `recallx[semantic]`. |
| `embedding_model` | string | `"all-MiniLM-L6-v2"` | Hugging Face local sentence-transformer model name used for vector embeddings. |
| `embedding_dimensions` | integer | `384` | Embedding dimensionality corresponding to `embedding_model`. |
| `secret_patterns` | list of strings | *(built-in defaults)* | List of regular expression patterns scanned to detect and redact credentials. |
| `log_level` | string | `"WARNING"` | Logging verbosity: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, or `"CRITICAL"`. |
| `json_output` | boolean | `false` | Force all CLI output to print as structured JSON instead of formatted tables. |
| `quiet` | boolean | `false` | Suppress non-error informational messages and progress feedback. |

---

## Environment Variables

Every setting can be overridden at runtime using environment variables prefixed with `RECALLX_`. Environment variables take precedence over settings defined in `config.toml`.

| Environment Variable | Equivalent Config Key | Example |
|---|---|---|
| `RECALLX_DATA_DIR` | `data_dir` | `/var/lib/recallx` |
| `RECALLX_DATABASE_NAME` | `database_name` | `shared.db` |
| `RECALLX_DEFAULT_PROJECT` | `default_project` | `backend-api` |
| `RECALLX_MAX_SEARCH_RESULTS` | `max_search_results` | `50` |
| `RECALLX_RELEVANCE_THRESHOLD` | `relevance_threshold` | `0.4` |
| `RECALLX_ENABLE_SEMANTIC_SEARCH` | `enable_semantic_search` | `true` |
| `RECALLX_EMBEDDING_MODEL` | `embedding_model` | `all-MiniLM-L6-v2` |
| `RECALLX_EMBEDDING_DIMENSIONS` | `embedding_dimensions` | `384` |
| `RECALLX_LOG_LEVEL` | `log_level` | `DEBUG` |
| `RECALLX_JSON_OUTPUT` | `json_output` | `true` |
| `RECALLX_QUIET` | `quiet` | `true` |

### Setting Environment Variables in Windows PowerShell
```powershell
$env:RECALLX_LOG_LEVEL = "DEBUG"
$env:RECALLX_ENABLE_SEMANTIC_SEARCH = "true"
recallx status
```

### Setting Environment Variables in Linux / macOS
```bash
export RECALLX_LOG_LEVEL="DEBUG"
export RECALLX_DEFAULT_PROJECT="my-api"
recallx status
```

---

## Configuration Precedence

When resolving settings, RecallX applies values in the following order (highest precedence first):

1. **Explicit CLI Flags** (e.g., `--project`, `--limit`, `--json`)
2. **Environment Variables** (e.g., `RECALLX_DEFAULT_PROJECT`)
3. **User Configuration File** (`config.toml`)
4. **Internal Application Defaults**
