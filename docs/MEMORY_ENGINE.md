# Memory Engine Internals

The RecallX Memory Engine (`recallx.engine`) is responsible for memory lifecycle management, input validation, automated rule-based extraction, duplicate detection, multi-signal relevance scoring, and consolidation.

---

## Memory Data Model

Every memory item stored in RecallX adheres to a strict schema represented in Python via Pydantic models and persisted in SQLite:

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique primary key identifier prefixed with `mem_` (e.g., `mem_01hq...`). |
| `project_id` | `str` | Scoped project identifier (alphanumeric, hyphens, underscores; max 128 chars). |
| `content` | `str` | Sanitized, redacted memory body text (max 50,000 characters). |
| `memory_type` | `str` | One of `project`, `decision`, `bug_solution`, `preference`, `session`. |
| `tags` | `list[str]` | Normalized, lowercase tags (max 20 tags, max 50 chars each). |
| `importance` | `float` | Importance weight between `0.0` (trivial) and `1.0` (critical architecture). Default `0.5`. |
| `content_hash` | `str` | SHA-256 hex digest of the normalized content used for fast duplicate checks. |
| `created_at` | `datetime` | UTC timestamp of initial persistence. |
| `updated_at` | `datetime` | UTC timestamp of most recent edit. |
| `access_count` | `int` | Monotonically increasing counter incremented upon retrieval. |
| `last_accessed_at`| `datetime` | UTC timestamp of latest retrieval. |

---

## Memory Types

RecallX categorizes memories into five functional archetypes:

1. **`project`**: Core architecture, repository structure, runtime environments, and stack components.
   - *Example*: "Monorepo configured with Turborepo: backend is FastAPI in Python, frontend is Next.js 14 App Router."
2. **`decision`**: Technical and design decisions accompanied by their explicit rationale.
   - *Example*: "Chose SQLite with WAL mode over PostgreSQL for the local desktop client to remove Docker runtime prerequisites."
3. **`bug_solution`**: Non-trivial errors, bug symptoms, root cause diagnoses, and their verified solutions.
   - *Example*: "Playwright test runner timeout caused by zombie Chrome processes; solved by setting process reaper in conftest.py."
4. **`preference`**: Developer conventions, preferred patterns, formatting rules, and tool preferences.
   - *Example*: "Always prefer absolute imports over relative imports across all python packages."
5. **`session`**: Structured session summaries recording completed work and pending items for subsequent sessions.
   - *Example*: "Completed JWT auth middleware; pending: token refresh rotation and rate limiting."

---

## Rule-Based Memory Extraction

RecallX can automatically detect and extract durable memories from developer conversations or session notes using deterministic heuristic patterns:

```
┌─────────────────────────────────────────────────────────────┐
│                      Raw Conversation Text                  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Regex & Heuristic Classifiers
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   [Decision Patterns]   [Bug Fix Patterns]  [Preference Rules]
   "chose X over Y"      "error fixed by"    "prefer / never use"
   "decided to use"      "root cause was"    "always import with"
          │                    │                    │
          └────────────────────┼────────────────────┘
                               ▼
                   Structured Memory Records
```

- **Decision Heuristics**: Matches phrases such as `decided to use`, `chose X over Y because`, `selected X instead of Y`, `architecture decision:`.
- **Bug Solution Heuristics**: Matches phrases like `fixed by`, `root cause was`, `resolved the error by`, `bugfix:`.
- **Preference Heuristics**: Matches phrases like `always use`, `never use`, `convention is to`, `prefer X for`.
- **Architecture Heuristics**: Matches patterns like `stack consists of`, `project structured as`, `using framework`.

---

## Retrieval and Multi-Signal Relevance Ranking

RecallX combines lexical full-text search with importance weighting and temporal decay to return the most relevant, actionable memories.

### 1. Lexical BM25 Scoring (SQLite FTS5)

Candidate memories are matched against an SQLite FTS5 index using the BM25 probabilistic relevance formula:

$$\text{BM25}(D, Q) = \sum_{i=1}^{N} \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

- Default parameters: $k_1 = 1.2$, $b = 0.75$.
- Exact token matches across `content` and `tags` yield high base scores.

### 2. Recency Time-Decay

Older memories naturally decrease in relevance unless they are frequently accessed or marked with high importance. RecallX applies an exponential time decay:

$$\text{Decay}(t) = \exp\left(-\lambda \cdot \Delta t_{\text{days}}\right)$$

Where:
- $\Delta t_{\text{days}}$ is the elapsed time in days since `last_accessed_at` (or `updated_at`).
- $\lambda = \frac{\ln(2)}{T_{\text{half}}}$ represents the decay constant.
- Default half-life $T_{\text{half}} = 30\text{ days}$.

### 3. Importance Weighting

Memories tagged with high importance receive a proportional boost:

$$\text{Weight}_{\text{imp}} = 1.0 + \alpha \cdot \text{importance}$$

Where:
- $\text{importance} \in [0.0, 1.0]$.
- Default scaling factor $\alpha = 0.5$.

### 4. Optional Dense Vector Semantic Similarity

When `recallx[semantic]` is installed, query embeddings and memory text embeddings are compared via Cosine Similarity:

$$\text{Sim}_{\text{cosine}}(u, v) = \frac{u \cdot v}{\|u\|_2 \|v\|_2}$$

### 5. Composite Ranking (Hybrid Fusion)

When both lexical FTS5 and semantic vector embeddings are active, scores are fused using Reciprocal Rank Fusion (RRF):

$$\text{RRF Score}(d) = \frac{w_{\text{lex}}}{60 + \text{rank}_{\text{lex}}(d)} + \frac{w_{\text{sem}}}{60 + \text{rank}_{\text{sem}}(d)}$$

The fused score is subsequently multiplied by the time-decay and importance factors:

$$\text{Final Score}(d) = \text{Score}_{\text{base}}(d) \times \text{Decay}(t) \times \text{Weight}_{\text{imp}}$$

Results falling below `relevance_threshold` (default `0.3`) are filtered out.

---

## Duplicate Detection and Consolidation

To prevent memory bloat over extended coding periods, RecallX features an automated consolidation engine:

1. **Exact Deduplication**:
   - Compares the `content_hash` (SHA-256) of new content against existing memories within the same project. Exact matches are skipped or their `access_count` is incremented.

2. **Fuzzy Similarity Detection**:
   - Evaluates token n-gram Jaccard similarity and normalized Levenshtein edit distance between memories within the same `project_id` and `memory_type`.
   - Pairs exhibiting similarity $> 0.85$ are flagged as consolidation candidates.

3. **Consolidation Actions**:
   - `recallx consolidate --dry-run`: Reports duplicate clusters and candidate obsolete memories.
   - `recallx consolidate`: Merges newer details into older anchor memories, aggregates tags, and deletes redundant items.
