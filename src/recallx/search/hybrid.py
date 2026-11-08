"""Hybrid search combining SQLite FTS5 lexical matching and dense vector retrieval."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Optional

from recallx.search.fulltext import FullTextSearch
from recallx.search.vector import VectorIndex
from recallx.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("search.hybrid")


class HybridSearch:
    """Hybrid search orchestrator using Reciprocal Rank Fusion (RRF).

    Combines BM25 lexical ranking from FullTextSearch with dense semantic
    cosine similarity from VectorIndex. When vector indexing is unavailable,
    gracefully delegates solely to full-text search.
    """

    def __init__(
        self,
        fts: FullTextSearch,
        vector: Optional[VectorIndex] = None,
    ) -> None:
        """Initialize HybridSearch with full-text search and optional vector index.

        Args:
            fts: Configured FullTextSearch instance.
            vector: Optional VectorIndex instance for semantic retrieval.
        """
        self.fts = fts
        self.vector = vector

    def _get_memory_record(self, memory_id: str) -> dict[str, Any] | None:
        """Fetch full memory attributes from the database for a specific ID.

        Args:
            memory_id: Memory identifier.

        Returns:
            Dictionary of memory fields, or None if not found or archived.
        """
        sql = """
            SELECT
                id, memory_type, content, project_id, tags, source,
                importance, confidence, is_pinned, is_archived,
                content_hash, metadata_json, expires_at, created_at,
                updated_at, accessed_at
            FROM memories
            WHERE id = :id AND is_archived = 0
        """
        try:
            rows = self.fts._execute_sql(sql, {"id": str(memory_id)})
            if not rows:
                return None
            return self.fts._format_row(rows[0])
        except Exception as exc:
            logger.debug("Could not fetch memory record for ID %s: %s", memory_id, exc)
            return None

    def _reciprocal_rank_fusion(
        self,
        fts_results: list[dict[str, Any]],
        vector_results: list[tuple[str, float]] | list[dict[str, Any]],
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """Merge lexical and vector result sets using Reciprocal Rank Fusion (RRF).

        Formula:
            RRF_score(d) = sum_{m in models} (1 / (k + rank_m(d)))

        Args:
            fts_results: Ranked list of memory dictionaries from FTS search.
            vector_results: Ranked list of (memory_id, similarity) pairs or memory dicts.
            k: Smoothing constant parameter (default 60).

        Returns:
            Consolidated and deduplicated list of memory dictionaries sorted by RRF score.
        """
        rrf_scores: dict[str, float] = defaultdict(float)
        records: dict[str, dict[str, Any]] = {}
        fts_ranks: dict[str, int] = {}
        vec_ranks: dict[str, int] = {}
        vec_sims: dict[str, float] = {}

        # 1. Accumulate FTS ranks
        for idx, item in enumerate(fts_results):
            mem_id = str(item.get("id"))
            rank = idx + 1
            rrf_scores[mem_id] += 1.0 / (k + rank)
            records[mem_id] = dict(item)
            fts_ranks[mem_id] = rank

        # 2. Accumulate Vector ranks
        for idx, item in enumerate(vector_results):
            if isinstance(item, tuple) or isinstance(item, list):
                mem_id = str(item[0])
                sim = float(item[1]) if len(item) > 1 else 0.0
            elif isinstance(item, dict):
                mem_id = str(item.get("id"))
                sim = float(item.get("similarity", item.get("vector_similarity", 0.0)))
            else:
                continue

            rank = idx + 1
            rrf_scores[mem_id] += 1.0 / (k + rank)
            vec_ranks[mem_id] = rank
            vec_sims[mem_id] = sim

            # If memory was not captured by FTS, populate record
            if mem_id not in records:
                db_record = self._get_memory_record(mem_id)
                if db_record is not None:
                    records[mem_id] = db_record
                elif isinstance(item, dict):
                    records[mem_id] = dict(item)
                else:
                    records[mem_id] = {"id": mem_id, "content": ""}

        # 3. Enrich items with fused score and metadata
        fused_items: list[dict[str, Any]] = []
        for mem_id, score in rrf_scores.items():
            if mem_id not in records:
                continue
            rec = records[mem_id]
            rec["rrf_score"] = score
            rec["fts_rank"] = fts_ranks.get(mem_id)
            rec["vector_rank"] = vec_ranks.get(mem_id)
            rec["vector_similarity"] = vec_sims.get(mem_id)
            rec["search_method"] = (
                "hybrid"
                if (mem_id in fts_ranks and mem_id in vec_ranks)
                else ("fts" if mem_id in fts_ranks else "vector")
            )
            fused_items.append(rec)

        # 4. Sort primarily by rrf_score descending, secondarily by importance
        fused_items.sort(
            key=lambda x: (
                float(x.get("rrf_score", 0.0)),
                float(x.get("importance", 0.0)),
            ),
            reverse=True,
        )

        return fused_items

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Perform hybrid search over persistent memories.

        Executes lexical FTS search and semantic vector search in parallel,
        merging candidates via Reciprocal Rank Fusion. If vector search is not
        available or encounters an error, falls back transparently to FTS.

        Args:
            query: User search query.
            project_id: Optional project filter.
            memory_type: Optional memory type category filter.
            limit: Maximum count of results to return (default 20).

        Returns:
            List of ranked memory dictionaries matching the query.
        """
        if not query or not query.strip():
            return []

        # If vector index is not configured, execute FTS only
        if self.vector is None:
            return self.fts.search(
                query=query,
                project_id=project_id,
                memory_type=memory_type,
                limit=limit,
            )

        candidate_pool_size = max(limit * 2, 20)

        # Execute full-text lexical search
        fts_results = self.fts.search(
            query=query,
            project_id=project_id,
            memory_type=memory_type,
            limit=candidate_pool_size,
        )

        # Execute semantic vector search
        try:
            vector_candidates = self.vector.search(
                query=query,
                limit=candidate_pool_size * 2,
            )
        except Exception as exc:
            logger.warning(
                "Vector search encountered an error (%s); falling back to FTS only.",
                exc,
            )
            return fts_results[:limit]

        # Filter vector candidates to respect project_id and memory_type constraints
        filtered_vector: list[tuple[str, float]] = []
        for mem_id, sim in vector_candidates:
            # If already verified in fts_results, it matches the filter
            if any(f.get("id") == mem_id for f in fts_results):
                filtered_vector.append((mem_id, sim))
                continue

            # Otherwise, check constraints from database record
            rec = self._get_memory_record(mem_id)
            if rec is None:
                continue

            if project_id is not None and rec.get("project_id") != str(project_id):
                continue
            if memory_type is not None and rec.get("memory_type") != str(memory_type):
                continue

            filtered_vector.append((mem_id, sim))

        # Perform Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(
            fts_results=fts_results,
            vector_results=filtered_vector,
            k=60,
        )

        return fused[: max(1, limit)]
