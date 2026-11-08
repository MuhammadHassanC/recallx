"""Deduplication and similarity detection engine for RecallX memories."""

from __future__ import annotations

import difflib
import re
from typing import Any

from recallx.storage.repositories import MemoryRepository
from recallx.utils.hashing import content_hash, normalize_content
from recallx.utils.logging import get_logger

logger = get_logger("recallx.core.deduplication")


class DeduplicationEngine:
    """Detects exact and near duplicates across project memories and handles merging."""

    def __init__(self, repo: MemoryRepository) -> None:
        """Initialize DeduplicationEngine.

        Args:
            repo: Initialized MemoryRepository instance.
        """
        self.repo = repo

    def is_duplicate(self, content: str, project_id: str) -> dict[str, Any] | None:
        """Check whether identical normalized content already exists for a project.

        Args:
            content: Candidate memory content string.
            project_id: Project identifier.

        Returns:
            Existing memory dict if exact duplicate hash found, None otherwise.
        """
        if not content or not content.strip():
            return None

        c_hash = content_hash(content)
        return self.repo.find_by_hash(content_hash=c_hash, project_id=project_id)

    def find_similar(
        self,
        content: str,
        project_id: str,
        threshold: float = 0.8,
    ) -> list[dict[str, Any]]:
        """Find memories in the project with textual similarity above the threshold.

        Uses FTS5 to find candidate matches followed by SequenceMatcher ratio calculation.

        Args:
            content: Target content to compare against.
            project_id: Project workspace identifier.
            threshold: Minimum similarity ratio between 0.0 and 1.0 (default 0.8).

        Returns:
            List of matching memory dictionaries with 'similarity' key, ordered descending.
        """
        norm_target = normalize_content(content)
        if not norm_target:
            return []

        # Extract tokens for candidate FTS retrieval
        tokens = [t for t in re.findall(r"\w+", norm_target) if len(t) >= 3]
        query_str = " ".join(tokens[:10]) if tokens else norm_target[:100]

        candidates: list[dict[str, Any]] = []
        if query_str.strip():
            candidates = self.repo.search_fts(
                query=query_str,
                project_id=project_id,
                limit=50,
            )

        # Fallback to listing project memories if FTS candidates were empty
        if not candidates:
            candidates = self.repo.list(
                project_id=project_id,
                limit=100,
            )

        matches: list[dict[str, Any]] = []
        matcher = difflib.SequenceMatcher(None, norm_target, "")

        for cand in candidates:
            cand_norm = normalize_content(str(cand.get("content", "")))
            if not cand_norm:
                continue

            # Fast check: identical
            if cand_norm == norm_target:
                item = dict(cand)
                item["similarity"] = 1.0
                matches.append(item)
                continue

            matcher.set_seq2(cand_norm)
            ratio = matcher.ratio()

            if ratio >= threshold:
                item = dict(cand)
                item["similarity"] = round(ratio, 4)
                matches.append(item)

        matches.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
        return matches

    def merge_duplicates(self, memory_ids: list[str], keep_id: str) -> dict[str, Any]:
        """Merge multiple duplicate memories into a single target memory.

        Consolidates tags, takes highest importance & confidence, keeps earliest created_at,
        merges metadata dictionaries, and removes obsolete duplicate entries.

        Args:
            memory_ids: List of memory IDs to merge.
            keep_id: Target memory ID to preserve and update.

        Returns:
            Updated memory dictionary for keep_id.

        Raises:
            ValueError: If keep_id does not exist or memory_ids is empty.
        """
        all_ids = list(dict.fromkeys([keep_id] + memory_ids))
        target_mem = self.repo.get(keep_id)
        if not target_mem:
            raise ValueError(f"Target memory with ID '{keep_id}' not found.")

        memories: list[dict[str, Any]] = []
        for mid in all_ids:
            m = self.repo.get(mid)
            if m:
                memories.append(m)

        if not memories:
            return target_mem

        # Merge tags preserving order
        merged_tags: list[str] = []
        seen_tags: set[str] = set()
        for m in memories:
            for tag in m.get("tags", []):
                cleaned = str(tag).strip().lower()
                if cleaned and cleaned not in seen_tags:
                    seen_tags.add(cleaned)
                    merged_tags.append(cleaned)

        # Determine highest importance and confidence
        highest_importance = max(float(m.get("importance", 0.5)) for m in memories)
        highest_confidence = max(float(m.get("confidence", 0.7)) for m in memories)
        is_pinned = any(bool(m.get("is_pinned", False)) for m in memories)

        # Determine earliest created_at
        created_dates = [m.get("created_at") for m in memories if m.get("created_at")]
        earliest_created = min(created_dates) if created_dates else target_mem.get("created_at")

        # Merge metadata
        merged_meta: dict[str, Any] = {}
        for m in memories:
            merged_meta.update(m.get("metadata", {}) or {})
        merged_meta["merged_from"] = [m["id"] for m in memories if m["id"] != keep_id]

        updates: dict[str, Any] = {
            "tags": merged_tags,
            "importance": highest_importance,
            "confidence": highest_confidence,
            "is_pinned": is_pinned,
            "metadata": merged_meta,
        }

        # Update target memory
        updated = self.repo.update(keep_id, updates)
        if not updated:
            raise ValueError(f"Failed to update target memory '{keep_id}'.")

        # Delete superseded memories
        for m in memories:
            if m["id"] != keep_id:
                self.repo.delete(m["id"])
                logger.info("Deleted duplicate memory %s merged into %s", m["id"], keep_id)

        return updated
