# RecallX Agent Skills

Agent Skills provide structured guidelines that instruct AI coding assistants (such as Claude Code, Cursor, Gemini CLI, Antigravity, and OpenCode) on **when**, **why**, and **how** to interact with RecallX persistent memory during coding sessions.

---

## Overview

While the Model Context Protocol (MCP) server gives the agent the mechanical ability to call tools like `remember` and `recall`, Agent Skills give the agent the judgment and operating principles needed to make effective memory decisions:

- Preventing clutter and low-value memories.
- Formulating specific, high-yield retrieval queries.
- Structuring session start context restoration and session end summaries.
- Safeguarding credentials by rejecting unredacted secrets.

RecallX includes three core skills bundled in `src/recallx/skills/`:

1. **`recallx-remember`**: Guidelines for identifying and saving durable knowledge.
2. **`recallx-recall`**: Guidelines for retrieving context before initiating changes.
3. **`recallx-project-context`**: Guidelines for managing end-to-end project context and session handoffs.

---

## Skill Specifications

### 1. `recallx-remember`

**Purpose**: Identifies durable, reusable engineering facts and saves them to RecallX.

#### When to Trigger:
- After finalizing a significant architectural or technical decision.
- After diagnosing and solving a non-trivial bug (recording error symptom, root cause, and fix).
- When the developer expresses a coding style preference, linter rule, or repository convention.
- When creating structural patterns that subsequent sessions should follow.
- At the end of a session when outstanding work items remain.

#### When NOT to Trigger:
- For transient, temporary, or single-use variables and commands.
- For passwords, API keys, private tokens, or connection strings with secrets.
- For routine, self-documenting boilerplate code.
- When the fact is already prominently documented in `README.md` or repository docs.
- When the validity of the technical decision is unverified or speculative.

#### Invocation Example:
```python
remember(
    content="Using PostgreSQL with SQLAlchemy for the API backend. Chose PostgreSQL over SQLite for concurrent writes in the webhook processor.",
    project_id="my-api",
    memory_type="decision",
    tags=["database", "architecture"],
    importance=0.8
)
```

---

### 2. `recallx-recall`

**Purpose**: Retrieves relevant architectural rationale, previous solutions, and preferences before writing code.

#### When to Trigger:
- At the beginning of a fresh conversation or coding session.
- Before committing to significant architectural designs or schema changes.
- When encountering an obscure build failure or runtime bug that might have occurred previously.
- When unsure of conventions (e.g., camelCase vs snake_case, test runners, import patterns).
- Before refactoring or expanding an unfamiliar subsystem.

#### When NOT to Trigger:
- For standard language semantics or well-known public library syntax.
- When the exact context was already provided in the current user prompt.
- For real-time ephemeral information (e.g., inspecting live process PID).

#### Invocation Example:
```python
recall(
    query="database migration and rollback strategy",
    project_id="my-api",
    memory_type="decision",
    limit=5
)
```

---

### 3. `recallx-project-context`

**Purpose**: Maintains a high-level architectural view of the project and documents session progress.

#### Standard Session Lifecycle:

1. **Session Start**:
   The agent queries project context and relevant prior memories:
   ```python
   # Load high-level project conventions and stack
   get_project_context(project_id="my-api")

   # Retrieve specific task context
   recall(query="payment webhook implementation", project_id="my-api")
   ```

2. **Mid-Session Work**:
   When solving difficult bugs or establishing new patterns:
   ```python
   remember(
       content="Stripe test webhooks require header 'Stripe-Signature' validation using raw request body bytes, not parsed JSON.",
       project_id="my-api",
       memory_type="bug_solution",
       tags=["stripe", "webhooks"],
       importance=0.7
   )
   ```

3. **Session End**:
   The agent records a structured session summary to facilitate resumption:
   ```python
   save_session_summary(
       project_id="my-api",
       summary="Implemented Stripe webhook signature verification and idempotency layer.",
       pending_tasks=["Add exponential backoff retry worker", "Write integration tests"],
   )
   ```

---

## Installing Skills in Your Agent

### Antigravity / Gemini CLI
Copy the skill directories into your Antigravity skills repository:

```bash
# Example on Windows:
Copy-Item -Recurse "src/recallx/skills/*" "$HOME/.gemini/config/skills/"

# Example on Linux / macOS:
cp -r src/recallx/skills/* ~/.gemini/config/skills/
```

### Claude Code
Claude Code discovers instructions from `.claude/rules/` or project context files (`CLAUDE.md`). You can include the skill guidelines directly in your project root `CLAUDE.md`:

```markdown
# RecallX Guidelines
- Use the `recall` tool at the beginning of each session to check existing conventions.
- When solving bugs or choosing architectures, call `remember` with clear rationale and tags.
- At the end of major sessions, call `save_session_summary` with completed and pending tasks.
```

### Cursor IDE
Add the skill guidelines into `.cursorrules` or `.cursor/rules/recallx.mdc`:

```markdown
---
description: RecallX Persistent Memory Operating Guidelines
globs: *
---
Before starting complex tasks, call `recall` to inspect prior architecture decisions.
When finishing bugs or making architectural decisions, call `remember` with project_id and tags.
```

---

## Best Practices for Authoring Memories

1. **Capture the "Why", Not Just the "What"**:
   - *Poor*: "We use Redis."
   - *Good*: "Using Redis for session state and rate limiting because multiple worker containers require a shared store."
2. **Keep Memories Focused and Atomic**:
   - Store one concept per memory rather than bundling five unrelated decisions into one record.
3. **Adopt Consistent Tagging**:
   - Use lowercase, hyphen-separated tags (e.g., `auth`, `db-migration`, `frontend`, `docker`).
4. **Use Accurate Importance Ratings**:
   - `0.9 - 1.0`: Core architecture, language choices, immutable database constraints.
   - `0.6 - 0.8`: Reusable patterns, tricky bug resolutions, major subsystem designs.
   - `0.3 - 0.5`: Stylistic conventions, minor preferences.
