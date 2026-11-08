---
name: recallx-remember
description: Identify and save durable, reusable information to RecallX persistent memory
---

# RecallX Remember Skill

## When to Trigger
- After making a significant technical decision
- After solving a non-trivial bug
- When a user states a coding preference or convention
- After establishing project architecture or patterns
- When completing a session with unfinished work

## When NOT to Trigger
- For temporary or one-off information
- For sensitive secrets, API keys, or credentials
- For routine code that's self-documenting
- For information already stored in project docs
- When uncertain about the information's accuracy

## How to Use
Call the RecallX MCP tool `remember` with:
- **content**: Clear, concise description of what to remember
- **project_id**: Current project identifier
- **memory_type**: One of: project, decision, bug_solution, preference, session
- **tags**: Relevant tags for categorization
- **importance**: 0.0-1.0 (0.8+ for architecture decisions, 0.5 for general info)

## Guidelines
- Be specific and concise — write memories that will be useful months later
- Include the "why" behind decisions, not just the "what"
- For bug solutions, include the error message and root cause
- Never store raw credentials, tokens, or secrets
- Prefer structured content over raw conversation dumps
- One concept per memory — don't bundle unrelated information

## Example
```
remember(
  content="Using PostgreSQL with SQLAlchemy ORM for the API. Chose PostgreSQL over SQLite for concurrent write support needed by the webhook processor.",
  project_id="my-api",
  memory_type="decision",
  tags=["database", "architecture"],
  importance=0.8
)
```

## Prerequisites
The RecallX MCP server must be configured in your agent's MCP settings. This skill alone does not provide database access.
