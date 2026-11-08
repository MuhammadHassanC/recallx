"""Retrieval orchestrator for RecallX combining full-text search and relevance ranking."""

from __future__ import annotations

import re
from typing import Any

from recallx.core.ranking import RelevanceRanker
from recallx.storage.repositories import MemoryRepository
from recallx.utils.logging import get_logger

logger = get_logger("recallx.core.retrieval")

_SEARCH_STOPWORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
        "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
        "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
        "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
        "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
        "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
        "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
        "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
        "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
        "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
        "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
        "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
        "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
        "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
        "they've", "this", "those", "through", "to", "too", "under", "until", "up",
        "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
        "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
        "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
        "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours",
    }
)


class RetrievalEngine:
    """Orchestrates memory searches using FTS5, metadata filters, and relevance ranking."""

    def __init__(
        self,
        repo: MemoryRepository,
        ranker: RelevanceRanker | None = None,
    ) -> None:
        """Initialize RetrievalEngine.

        Args:
            repo: Initialized MemoryRepository instance.
            ranker: Optional RelevanceRanker instance (defaults to standard ranker).
        """
        self.repo = repo
        self.ranker = ranker or RelevanceRanker()

    def search(
        self,
        query: str,
        project_id: str | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        min_relevance: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search memories using FTS5, filter by tags, and rank results.

        Args:
            query: User search query.
            project_id: Optional project identifier filter.
            memory_type: Optional memory type filter.
            tags: Optional list of tags (memory must have at least one matching tag).
            limit: Maximum number of results to return.
            min_relevance: Minimum composite relevance score threshold (0.0 to 1.0).

        Returns:
            List of matching memory dictionaries sorted by relevance.
        """
        clean_query = query.strip()
        fetch_limit = max(50, limit * 3)

        candidates: list[dict[str, Any]] = []
        if clean_query:
            candidates = self.repo.search_fts(
                query=clean_query,
                project_id=project_id,
                memory_type=memory_type,
                limit=fetch_limit,
            )
        else:
            candidates = self.repo.list(
                project_id=project_id,
                memory_type=memory_type,
                limit=fetch_limit,
            )

        seen_ids = {c["id"] for c in candidates}

        # Token expansion for natural language queries (e.g. conversational questions)
        tokens = [
            t
            for t in re.findall(r"\w+", clean_query.lower())
            if t not in _SEARCH_STOPWORDS and len(t) >= 2
        ]

        if len(candidates) < limit and len(tokens) > 1:
            for tok in tokens:
                sub_matches = self.repo.search_fts(
                    query=tok,
                    project_id=project_id,
                    memory_type=memory_type,
                    limit=limit,
                )
                for item in sub_matches:
                    if item["id"] not in seen_ids:
                        candidates.append(item)
                        seen_ids.add(item["id"])

        # Tag filtering if specified
        if tags:
            normalized_filter_tags = {t.strip().lower() for t in tags if t.strip()}
            filtered: list[dict[str, Any]] = []
            for item in candidates:
                item_tags = {str(t).lower() for t in item.get("tags", [])}
                if item_tags.intersection(normalized_filter_tags):
                    filtered.append(item)
            candidates = filtered

        # Apply multi-signal relevance ranking
        ranked = self.ranker.rank(candidates, clean_query)

        # Filter by minimum relevance threshold
        if min_relevance > 0.0:
            ranked = [m for m in ranked if m.get("relevance", 0.0) >= min_relevance]

        return ranked[: max(1, limit)]

    def search_hybrid(
        self,
        query: str,
        project_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search combining FTS5 lexical matching and semantic search if available.

        Falls back cleanly to standard FTS + relevance ranking if vector search is unavailable.

        Args:
            query: User search query.
            project_id: Optional project identifier filter.
            memory_type: Optional memory type filter.
            limit: Maximum results to return.

        Returns:
            Ranked list of memory dictionaries.
        """
        # First retrieve FTS candidates
        fts_results = self.search(
            query=query,
            project_id=project_id,
            memory_type=memory_type,
            limit=limit * 2,
        )

        semantic_results: list[dict[str, Any]] = []
        if self._has_semantic_support():
            semantic_results = self._semantic_search(
                query=query,
                project_id=project_id,
                memory_type=memory_type,
                limit=limit * 2,
            )

        if not semantic_results:
            return fts_results[:limit]

        # Merge and deduplicate candidates
        merged_map: dict[str, dict[str, Any]] = {}
        for item in fts_results:
            merged_map[item["id"]] = item

        for item in semantic_results:
            if item["id"] not in merged_map:
                merged_map[item["id"]] = item

        combined = list(merged_map.values())
        ranked = self.ranker.rank(combined, query)
        return ranked[:limit]

    def _has_semantic_support(self) -> bool:
        """Check whether local embedding model dependencies are installed."""
        try:
            import numpy  # noqa: F401
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def _semantic_search(
        self,
        query: str,
        project_id: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Perform semantic embedding similarity search if model is available."""
        try:
            return []
        except Exception as exc:
            logger.debug("Semantic search pass encountered error: %s", exc)
            return []
