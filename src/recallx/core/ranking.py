"""Relevance ranking engine for RecallX memories."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone

    UTC = timezone.utc  # type: ignore[attr-defined]


class RelevanceRanker:
    """Computes multi-signal composite relevance scores for memory items."""

    # Default signal weights summing to 1.0
    WEIGHT_TEXT: float = 0.40
    WEIGHT_IMPORTANCE: float = 0.25
    WEIGHT_RECENCY: float = 0.15
    WEIGHT_ACCESS: float = 0.10
    WEIGHT_TYPE: float = 0.10

    # Half-life for recency decay in days (~30 days)
    RECENCY_HALF_LIFE_DAYS: float = 30.0

    def __init__(
        self,
        weight_text: float = WEIGHT_TEXT,
        weight_importance: float = WEIGHT_IMPORTANCE,
        weight_recency: float = WEIGHT_RECENCY,
        weight_access: float = WEIGHT_ACCESS,
        weight_type: float = WEIGHT_TYPE,
        recency_half_life_days: float = RECENCY_HALF_LIFE_DAYS,
    ) -> None:
        """Initialize the RelevanceRanker with custom or default signal weights.

        Args:
            weight_text: Weight for text relevance / term overlap (default 0.40).
            weight_importance: Weight for memory importance attribute (default 0.25).
            weight_recency: Weight for age decay (default 0.15).
            weight_access: Weight for access recency/frequency (default 0.10).
            weight_type: Weight for query-to-memory-type relevance (default 0.10).
            recency_half_life_days: Half-life period for exponential recency decay.
        """
        total = weight_text + weight_importance + weight_recency + weight_access + weight_type
        if total <= 0:
            total = 1.0
        self.w_text = weight_text / total
        self.w_importance = weight_importance / total
        self.w_recency = weight_recency / total
        self.w_access = weight_access / total
        self.w_type = weight_type / total
        self.half_life_days = max(1.0, recency_half_life_days)

    def rank(self, memories: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """Compute composite relevance scores and return memories sorted descending.

        Args:
            memories: List of memory dictionaries.
            query: The search query string.

        Returns:
            New list of memory dictionaries with an added 'relevance' key, sorted descending.
        """
        if not memories:
            return []

        ranked_items: list[dict[str, Any]] = []
        for mem in memories:
            item = dict(mem)
            content = str(item.get("content", ""))
            importance = float(item.get("importance", 0.5))
            created_at = item.get("created_at")
            accessed_at = item.get("accessed_at")
            memory_type = str(item.get("memory_type", "project"))

            s_text = self._text_relevance(content, query)
            s_importance = max(0.0, min(1.0, importance))
            s_recency = self._recency_score(created_at, accessed_at)
            s_access = self._access_score(created_at, accessed_at)
            s_type = self._type_boost(memory_type, query)

            composite = (
                self.w_text * s_text
                + self.w_importance * s_importance
                + self.w_recency * s_recency
                + self.w_access * s_access
                + self.w_type * s_type
            )

            # Pinned memories receive a slight elevation boost (up to 0.1) without exceeding 1.0
            if item.get("is_pinned"):
                composite = min(1.0, composite + 0.10)

            score = round(max(0.0, min(1.0, composite)), 4)
            item["relevance"] = score
            ranked_items.append(item)

        # Sort descending by relevance, with tie-breaking on importance and recency
        ranked_items.sort(
            key=lambda x: (
                x.get("relevance", 0.0),
                x.get("is_pinned", False),
                x.get("importance", 0.0),
                x.get("created_at") or "",
            ),
            reverse=True,
        )
        return ranked_items

    def _text_relevance(self, content: str, query: str) -> float:
        """Compute term overlap and phrase matching ratio between query and content.

        Args:
            content: Memory text body.
            query: User search query.

        Returns:
            Normalized float between 0.0 and 1.0.
        """
        if not query or not query.strip():
            return 0.5  # Neutral relevance when query is empty

        if not content or not content.strip():
            return 0.0

        q_lower = query.lower().strip()
        c_lower = content.lower().strip()

        # Exact substring match provides high base text relevance
        if q_lower in c_lower:
            return 1.0

        q_tokens = [tok for tok in re.findall(r"\w+", q_lower) if tok]
        if not q_tokens:
            return 0.0

        c_tokens = set(re.findall(r"\w+", c_lower))
        if not c_tokens:
            return 0.0

        matches = sum(1 for tok in q_tokens if tok in c_tokens)
        overlap_ratio = matches / len(q_tokens)

        # Partial token matching (prefix match)
        prefix_matches = sum(
            1 for tok in q_tokens if any(c_tok.startswith(tok) or tok.startswith(c_tok) for c_tok in c_tokens)
        )
        prefix_ratio = prefix_matches / len(q_tokens)

        score = 0.7 * overlap_ratio + 0.3 * prefix_ratio
        return min(1.0, max(0.0, score))

    def _recency_score(self, created_at: Any, accessed_at: Any) -> float:
        """Compute exponential decay score based on age.

        Uses half-life formula: N(t) = 0.5 ^ (age / half_life).

        Args:
            created_at: Datetime or ISO timestamp string of creation.
            accessed_at: Datetime or ISO timestamp string of last access.

        Returns:
            Decay multiplier between 0.0 and 1.0.
        """
        dt = self._parse_datetime(created_at)
        if dt is None:
            return 0.5

        now = datetime.now(UTC)
        age_seconds = max(0.0, (now - dt).total_seconds())
        age_days = age_seconds / 86400.0

        decay = math.pow(0.5, age_days / self.half_life_days)
        return max(0.0, min(1.0, decay))

    def _access_score(self, created_at: Any, accessed_at: Any) -> float:
        """Score based on how recently or frequently the memory was accessed.

        Args:
            created_at: Creation timestamp.
            accessed_at: Last access timestamp.

        Returns:
            Float between 0.0 and 1.0.
        """
        dt_access = self._parse_datetime(accessed_at)
        if dt_access is None:
            return 0.2

        now = datetime.now(UTC)
        access_age_days = max(0.0, (now - dt_access).total_seconds()) / 86400.0

        # Freshness of access (decay over 14 days)
        access_recency = math.pow(0.5, access_age_days / 14.0)

        # Bonus if accessed subsequent to creation
        dt_create = self._parse_datetime(created_at)
        if dt_create and dt_access > dt_create:
            access_recency = min(1.0, access_recency + 0.15)

        return max(0.0, min(1.0, access_recency))

    def _type_boost(self, memory_type: str, query: str) -> float:
        """Boost relevance based on query intent matching memory type.

        Args:
            memory_type: Category ('decision', 'bug_solution', 'preference', etc.).
            query: Query string.

        Returns:
            Boost score in range [0.3, 1.0].
        """
        if not query:
            return 0.5

        q = query.lower()

        intent_keywords: dict[str, list[str]] = {
            "decision": ["why", "chose", "choice", "decide", "decision", "architecture", "tradeoff", "versus", "vs", "rationale"],
            "bug_solution": ["bug", "fix", "fixed", "error", "issue", "crash", "exception", "broken", "root cause", "solution", "patch"],
            "preference": ["prefer", "convention", "style", "standard", "rule", "guideline", "always", "never", "format", "pattern"],
            "project": ["stack", "technology", "tech", "repo", "overview", "project", "setup", "database", "orm", "framework", "library"],
            "session": ["session", "todo", "done", "pending", "progress", "summary", "task", "status", "milestone"],
        }

        keywords = intent_keywords.get(memory_type, [])
        matches = sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", q))

        if matches >= 2:
            return 1.0
        if matches == 1:
            return 0.85
        return 0.50

    @staticmethod
    def _parse_datetime(val: Any) -> datetime | None:
        """Helper to parse datetime objects or ISO strings into UTC datetime."""
        if val is None:
            return None
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=UTC)
            return val.astimezone(UTC)
        if isinstance(val, str):
            try:
                cleaned = val.replace("Z", "+00:00")
                dt = datetime.fromisoformat(cleaned)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=UTC)
                return dt.astimezone(UTC)
            except Exception:
                return None
        return None


def rank(
    memories: list[dict[str, Any]],
    query: str,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Rank memories by relevance against a search query using RelevanceRanker.

    Args:
        memories: List of memory dictionaries.
        query: Search query string.
        **kwargs: Optional weights passed to RelevanceRanker.

    Returns:
        Sorted list of memory dictionaries with 'relevance' score.
    """
    return RelevanceRanker(**kwargs).rank(memories, query)

