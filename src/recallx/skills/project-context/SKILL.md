---
name: recallx-project-context
description: Maintain and retrieve project architecture and development context
---

# RecallX Project Context Skill

## When to Trigger
- At the very start of working on a project
- When a new collaborator joins a project
- Before major refactoring or architecture changes
- When switching between projects

## When NOT to Trigger
- Mid-task when context is already loaded
- For quick, isolated bug fixes with full context

## How to Use
1. **Retrieve context**: Call `get_project_context` with the project_id
2. **Save context**: Call `remember` with memory_type="project" for architectural info
3. **Session summary**: Call `save_session_summary` at session end

## Maintaining Good Context
- Keep project memories concise and current
- Update outdated architectural decisions rather than creating new ones
- Use `consolidate_memories` periodically to merge related memories
- Pin the most important project memories (architecture, stack, conventions)

## Example Session Start
```
# 1. Get project context
get_project_context(project_id="my-api")

# 2. Search for relevant memories about today's task
recall(query="payment processing implementation", project_id="my-api")
```

## Example Session End
```
save_session_summary(
  project_id="my-api",
  summary="Implemented Stripe webhook handler with idempotency",
  tasks_completed=["webhook endpoint", "signature verification", "idempotency check"],
  tasks_pending=["retry logic", "dead letter queue"],
  issues=["Stripe test mode webhooks have 5s delay"]
)
```

## Prerequisites
The RecallX MCP server must be configured in your agent's MCP settings.
