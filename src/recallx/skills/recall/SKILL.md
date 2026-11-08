---
name: recallx-recall
description: Retrieve relevant previous context from RecallX before starting work
---

# RecallX Recall Skill

## When to Trigger
- At the start of a new coding session
- Before making architectural decisions
- When encountering a bug that might have been solved before
- When unsure about project conventions or preferences
- Before implementing a feature in an unfamiliar part of the codebase

## When NOT to Trigger
- For trivial, well-known information
- When context is already provided in the conversation
- For real-time information (current errors, live logs)

## How to Use
Call the RecallX MCP tool `recall` with:
- **query**: Natural language description of what you need
- **project_id**: Current project identifier (if known)
- **memory_type**: Optional filter (project, decision, bug_solution, preference, session)
- **limit**: Number of results (default 10)

For comprehensive project context, use `get_project_context` instead.

## Guidelines
- Search before assuming you don't have context
- Use specific queries — "authentication architecture" not "auth"
- If results aren't relevant, try different search terms
- Don't treat recalled memories as absolute truth — they're contextual hints
- Check memory timestamps for relevance
- An empty result is honest — don't invent context

## Example
```
recall(
  query="database migration strategy",
  project_id="my-api",
  memory_type="decision",
  limit=5
)
```

## Prerequisites
The RecallX MCP server must be configured in your agent's MCP settings.
