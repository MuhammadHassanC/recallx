"""Memory consolidation engine for RecallX."""

from __future__ import annotations

import difflib
from collections import defaultdict
from datetime import datetime
from typing import Any

from recallx.storage.repositories import MemoryCreate, MemoryRepository
from recallx.utils.hashing import normalize_content
from recallx.utils.logging import get_logger

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone

    UTC = timezone.utc  # type: ignore[attr-defined]

logger = get_logger("recallx.core.consolidation")


class ConsolidationEngine:
    """Discovers clusters of related memories and consolidates them into unified summaries."""

    def __init__(self, repo: MemoryRepository) -> None:
        """Initialize ConsolidationEngine.

        Args:
            repo: Initialized MemoryRepository instance.
        """
        self.repo = repo

    def find_consolidation_candidates(
        self,
        project_id: str,
        similarity_threshold: float = 0.50,
    ) -> list[list[dict[str, Any]]]:
        """Group memories within a project by type and cluster closely related memories.

        Args:
            project_id: Project identifier to search.
            similarity_threshold: Minimum textual / tag overlap ratio for clustering.

        Returns:
            List of memory groups (each group containing 2 or more related memory dicts).
        """
        memories = self.repo.list(project_id=project_id, limit=200, is_archived=False)
        if len(memories) < 2:
            return []

        # Partition by memory type
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for mem in memories:
            m_type = str(mem.get("memory_type", "project"))
            by_type[m_type].append(mem)

        candidate_groups: list[list[dict[str, Any]]] = []

        for _, group in by_type.items():
            if len(group) < 2:
                continue

            # Build adjacency graph of related memories
            n = len(group)
            adj: dict[int, set[int]] = defaultdict(set)

            for i in range(n):
                c1 = normalize_content(str(group[i].get("content", "")))
                tags1 = {str(t).lower() for t in group[i].get("tags", [])}

                for j in range(i + 1, n):
                    c2 = normalize_content(str(group[j].get("content", "")))
                    tags2 = {str(t).lower() for t in group[j].get("tags", [])}

                    # Shared tag overlap
                    shared_tags = tags1.intersection(tags2)
                    tag_sim = len(shared_tags) / max(1, len(tags1.union(tags2))) if (tags1 or tags2) else 0.0

                    # Sequence text similarity
                    text_sim = difflib.SequenceMatcher(None, c1[:300], c2[:300]).ratio() if (c1 and c2) else 0.0

                    composite_sim = 0.6 * text_sim + 0.4 * tag_sim

                    if composite_sim >= similarity_threshold or (tag_sim >= 0.5 and len(shared_tags) >= 2):
                        adj[i].add(j)
                        adj[j].add(i)

            # Discover connected components
            visited: set[int] = set()
            for i in range(n):
                if i not in visited and adj[i]:
                    cluster_indices: set[int] = set()
                    queue = [i]
                    visited.add(i)

                    while queue:
                        curr = queue.pop(0)
                        cluster_indices.add(curr)
                        for neighbor in adj[curr]:
                            if neighbor not in visited:
                                visited.add(neighbor)
                                queue.append(neighbor)

                    if len(cluster_indices) >= 2:
                        cluster = [group[idx] for idx in sorted(cluster_indices)]
                        candidate_groups.append(cluster)

        return candidate_groups

    def consolidate(
        self,
        memory_ids: list[str],
        new_content: str,
        project_id: str,
        tags: list[str] | None = None,
        memory_type: str | None = None,
        importance: float | None = None,
    ) -> dict[str, Any]:
        """Consolidate multiple existing memories into a single concise memory.

        The original memories are archived (preserving history without loss),
        and the new consolidated memory is created with full provenance metadata.

        Args:
            memory_ids: List of unique memory identifiers to consolidate.
            new_content: Synthesized textual content for the new memory.
            project_id: Project identifier.
            tags: Optional tags override. If None, unions all tags from inputs.
            memory_type: Optional category override. If None, uses majority type.
            importance: Optional importance override. If None, uses highest importance.

        Returns:
            Dictionary of the newly created consolidated memory.

        Raises:
            ValueError: If memory_ids is empty or new_content is blank.
        """
        if not memory_ids:
            raise ValueError("memory_ids cannot be empty for consolidation.")
        if not new_content or not new_content.strip():
            raise ValueError("new_content cannot be empty.")

        source_memories: list[dict[str, Any]] = []
        for mid in memory_ids:
            mem = self.repo.get(mid)
            if mem:
                source_memories.append(mem)

        if not source_memories:
            raise ValueError("None of the specified memory_ids were found in storage.")

        # Determine tags
        if tags is not None:
            resolved_tags = list(tags)
        else:
            merged_tags: list[str] = []
            seen_tags: set[str] = set()
            for mem in source_memories:
                for t in mem.get("tags", []):
                    ct = str(t).strip().lower()
                    if ct and ct not in seen_tags:
                        seen_tags.add(ct)
                        merged_tags.append(ct)
            resolved_tags = merged_tags

        # Determine memory_type
        if memory_type:
            resolved_type = memory_type
        else:
            type_counts: dict[str, int] = defaultdict(int)
            for mem in source_memories:
                type_counts[str(mem.get("memory_type", "project"))] += 1
            resolved_type = max(type_counts.items(), key=lambda x: x[1])[0]

        # Determine importance & confidence
        resolved_importance = (
            float(importance)
            if importance is not None
            else max(float(m.get("importance", 0.5)) for m in source_memories)
        )
        resolved_confidence = max(float(m.get("confidence", 0.7)) for m in source_memories)

        # Build provenance metadata
        now_iso = datetime.now(UTC).isoformat()
        metadata: dict[str, Any] = {
            "consolidated_from": [m["id"] for m in source_memories],
            "consolidated_at": now_iso,
            "source_count": len(source_memories),
        }

        # Create new consolidated record
        create_payload = MemoryCreate(
            content=new_content.strip(),
            project_id=project_id,
            memory_type=resolved_type,
            tags=resolved_tags,
            importance=resolved_importance,
            confidence=resolved_confidence,
            source="consolidation",
            metadata=metadata,
        )
        new_memory = self.repo.create(create_payload)

        # Archive original memories (soft delete to keep audit history)
        for mem in source_memories:
            self.repo.update(mem["id"], {"is_archived": True})
            logger.info("Archived memory %s as part of consolidation into %s", mem["id"], new_memory["id"])

        return new_memory
