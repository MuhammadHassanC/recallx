"""RecallX MCP Prompts - Context capture, retrieval, and session summary templates."""
from __future__ import annotations

from recallx.mcp.server import mcp


@mcp.prompt("remember-context")
def remember_context(project_id: str, topic: str = "") -> str:
    """Prompt template for agents to capture useful context into RecallX persistent memory."""
    topic_str = f" regarding '{topic}'" if topic else ""
    return f"""You are capturing persistent memory for project '{project_id}'{topic_str}.

Analyze the recent conversation, debugging session, or technical decision to identify durable, reusable knowledge:
1. Technical Decisions: What choice was made and why (include trade-offs and rationale).
2. Bug Solutions: The symptom/error message, root cause, and verified solution.
3. Developer Preferences: Project standards, formatting, conventions, and style rules.
4. Core Project Architecture: Tech stack components, repository layout, and integration points.

For each distinct item, call the `remember` tool:
- `content`: Clear, self-contained description.
- `project_id`: '{project_id}'
- `memory_type`: One of 'decision', 'bug_solution', 'preference', 'project'.
- `tags`: Specific descriptive tags (e.g. ['auth', 'jwt', 'security']).
- `importance`: Float between 0.0 (trivial) and 1.0 (critical architecture, use 0.8+).

Do not save transient session chatter, secrets, credentials, or obvious code that is self-documenting.
"""


@mcp.prompt("recall-context")
def recall_context(project_id: str, task: str = "") -> str:
    """Prompt template for retrieving relevant context before starting work on a task."""
    task_str = f" for task: '{task}'" if task else ""
    return f"""Before starting work on project '{project_id}'{task_str}, retrieve existing project memory:

Step 1: Check Project Architecture and Pinned Context
Call `get_project_context(project_id='{project_id}')` to inspect high-level stack components, established conventions, and pinned decisions.

Step 2: Search Task-Specific Memories
If working on a specific feature, component, or bug:
Call `recall(query='{task or "architecture conventions"}', project_id='{project_id}', limit=10)` to find relevant previous decisions, bug fixes, or developer preferences.

Step 3: Review Past Sessions
If resuming previous work, call `list_memories(project_id='{project_id}', memory_type='session', limit=3)` to review recent progress and pending tasks.

Integrate these findings into your implementation plan before modifying any code.
"""


@mcp.prompt("session-summary")
def session_summary(project_id: str) -> str:
    """Prompt template for summarizing a coding session."""
    return f"""You are concluding a coding session on project '{project_id}'.

Persist your session progress to RecallX so future agent sessions can seamlessly resume:

Call the `save_session_summary` tool with:
- `project_id`: '{project_id}'
- `summary`: A concise 2-4 sentence summary of accomplishments and current system state.
- `tasks_completed`: List of finished tasks and implemented features.
- `tasks_pending`: List of remaining work items, next steps, or open questions.
- `issues`: Any unresolved blockers, bugs, or technical debt identified during the session.

If you made any major technical decisions or solved non-trivial bugs during this session, make sure to also record them individually using the `remember` tool before wrapping up.
"""
