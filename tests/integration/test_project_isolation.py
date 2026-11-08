"""Integration tests verifying strict project workspace memory isolation."""
from __future__ import annotations

from recallx.core.memory import MemoryEngine


def test_memories_isolated_by_project(engine: MemoryEngine) -> None:
    """Ensure memories recorded in project A never leak into project B listing."""
    engine.remember(content="Alpha secret architecture spec", project_id="proj-alpha")
    engine.remember(content="Beta secret architecture spec", project_id="proj-beta")

    alpha_mems = engine.list_memories(project_id="proj-alpha")
    beta_mems = engine.list_memories(project_id="proj-beta")

    assert len(alpha_mems) == 1
    assert alpha_mems[0]["content"] == "Alpha secret architecture spec"

    assert len(beta_mems) == 1
    assert beta_mems[0]["content"] == "Beta secret architecture spec"


def test_search_only_returns_own_project(engine: MemoryEngine) -> None:
    """Ensure search queries scoped to a project never return results from other projects."""
    engine.remember(content="Common token auth secret across services", project_id="proj-alpha")
    engine.remember(content="Common token auth secret across services", project_id="proj-beta")

    alpha_results = engine.recall(query="token auth secret", project_id="proj-alpha")
    assert all(r["project_id"] == "proj-alpha" for r in alpha_results)

    beta_results = engine.recall(query="token auth secret", project_id="proj-beta")
    assert all(r["project_id"] == "proj-beta" for r in beta_results)


def test_project_context_only_own_memories(engine: MemoryEngine) -> None:
    """Ensure get_project_context contains strictly memories from the specified project."""
    engine.remember(content="Alpha Decision: use FastAPI", project_id="proj-alpha", memory_type="decision")
    engine.remember(content="Beta Decision: use Django", project_id="proj-beta", memory_type="decision")

    context_alpha = engine.get_project_context("proj-alpha")
    assert context_alpha["project_id"] == "proj-alpha"
    assert context_alpha["total_memories"] == 1

    decisions = context_alpha["memories_by_type"].get("decision", [])
    assert len(decisions) == 1
    assert decisions[0]["content"] == "Alpha Decision: use FastAPI"


def test_stats_per_project(engine: MemoryEngine) -> None:
    """Ensure statistics accurately reflect partition counts per project."""
    engine.remember(content="Alpha 1", project_id="proj-alpha", memory_type="decision")
    engine.remember(content="Alpha 2", project_id="proj-alpha", memory_type="preference")
    engine.remember(content="Beta 1", project_id="proj-beta", memory_type="decision")

    stats_alpha = engine.get_stats("proj-alpha")
    assert stats_alpha["total"] == 2
    assert stats_alpha["counts_by_type"].get("decision") == 1
    assert stats_alpha["counts_by_type"].get("preference") == 1

    stats_beta = engine.get_stats("proj-beta")
    assert stats_beta["total"] == 1
    assert stats_beta["counts_by_type"].get("decision") == 1
    assert stats_beta["counts_by_type"].get("preference", 0) == 0
