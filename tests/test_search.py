"""Unit and integration tests for RecallX search infrastructure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import pytest
from sqlalchemy import text

from recallx.search.embeddings import (
    EmbeddingProvider,
    LocalEmbeddingProvider,
    get_embedding_provider,
)
from recallx.search.fulltext import FullTextSearch
from recallx.search.hybrid import HybridSearch
from recallx.search.vector import VectorIndex, _cosine_similarity_py, _vector_to_blob, _blob_to_vector
from recallx.storage.database import DatabaseManager


class DummyEmbeddingProvider(EmbeddingProvider):
    """Deterministic dummy embedding provider for fast unit tests."""

    def __init__(self, dimensions: int = 4) -> None:
        self._dimensions = dimensions
        self._model_name = "test-dummy-model"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, text: str) -> list[float]:
        # Generate predictable deterministic vector based on text contents
        normalized = text.lower()
        if "database" in normalized or "sql" in normalized:
            return [1.0, 0.0, 0.0, 0.0]
        elif "auth" in normalized or "jwt" in normalized:
            return [0.0, 1.0, 0.0, 0.0]
        elif "frontend" in normalized or "react" in normalized:
            return [0.0, 0.0, 1.0, 0.0]
        return [0.5, 0.5, 0.5, 0.5]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


@pytest.fixture
def test_db() -> DatabaseManager:
    """Fixture providing an initialized in-memory database."""
    manager = DatabaseManager(":memory:")
    manager.initialize()
    return manager


def _seed_memory(
    db: DatabaseManager,
    mem_id: str,
    content: str,
    project_id: str = "project-alpha",
    memory_type: str = "decision",
    tags: list[str] | None = None,
    importance: float = 0.8,
) -> None:
    """Helper to insert memory into both memories and memory_fts tables."""
    tags_list = tags or ["architecture", "core"]
    tags_json = json.dumps(tags_list)

    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO memories (
                    id, memory_type, content, project_id, tags, source,
                    importance, confidence, is_pinned, is_archived,
                    content_hash, metadata_json, created_at, updated_at, accessed_at
                ) VALUES (
                    :id, :memory_type, :content, :project_id, :tags, 'cli',
                    :importance, 0.9, 0, 0, 'dummyhash', '{}',
                    datetime('now'), datetime('now'), datetime('now')
                )
                """
            ),
            {
                "id": mem_id,
                "memory_type": memory_type,
                "content": content,
                "project_id": project_id,
                "tags": tags_json,
                "importance": importance,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO memory_fts (id, content, tags, memory_type, project_id)
                VALUES (:id, :content, :tags, :memory_type, :project_id)
                """
            ),
            {
                "id": mem_id,
                "content": content,
                "tags": tags_json,
                "memory_type": memory_type,
                "project_id": project_id,
            },
        )


def test_fts_query_escaping(test_db: DatabaseManager) -> None:
    """Test escaping of special characters for FTS5."""
    fts = FullTextSearch(test_db)

    assert fts._escape_fts_query("") == ""
    assert fts._escape_fts_query('hello "world"') == 'hello ""world""'
    assert fts._escape_fts_query('test "special" characters') == 'test ""special"" characters'


def test_fts_build_query(test_db: DatabaseManager) -> None:
    """Test conversion of natural language query to FTS5 syntax."""
    fts = FullTextSearch(test_db)

    assert fts._build_fts_query("") == ""
    assert fts._build_fts_query("   ") == ""

    built = fts._build_fts_query("database migration")
    assert '"database"*' in built
    assert '"migration"*' in built
    assert " AND " in built

    # Special punctuation query
    special_built = fts._build_fts_query("error: code 500 (timeout)")
    assert '"error"*' in special_built
    assert '"500"*' in special_built


def test_fulltext_search_execution(test_db: DatabaseManager) -> None:
    """Test full-text search matching and filtering."""
    fts = FullTextSearch(test_db)

    _seed_memory(
        test_db,
        mem_id="mem-1",
        content="Using PostgreSQL database for transactional storage",
        project_id="backend-api",
        memory_type="decision",
        tags=["database", "sql"],
    )
    _seed_memory(
        test_db,
        mem_id="mem-2",
        content="JWT authentication tokens expire in 15 minutes",
        project_id="backend-api",
        memory_type="decision",
        tags=["auth", "security"],
    )
    _seed_memory(
        test_db,
        mem_id="mem-3",
        content="SQLite database used for local development",
        project_id="mobile-client",
        memory_type="project",
        tags=["database", "mobile"],
    )

    # Search for database in backend-api
    results = fts.search("database", project_id="backend-api")
    assert len(results) == 1
    assert results[0]["id"] == "mem-1"
    assert "rank" in results[0]
    assert isinstance(results[0]["rank"], float)

    # Search across all projects
    all_db_results = fts.search("database")
    assert len(all_db_results) == 2
    ids = {r["id"] for r in all_db_results}
    assert ids == {"mem-1", "mem-3"}

    # Search with memory_type filter
    type_filtered = fts.search("database", memory_type="project")
    assert len(type_filtered) == 1
    assert type_filtered[0]["id"] == "mem-3"

    # Search with no matches
    empty_results = fts.search("quantum teleportation")
    assert empty_results == []


def test_embedding_provider_factory() -> None:
    """Test embedding provider factory function with configs."""
    # When semantic search is disabled
    config_disabled = {"enable_semantic_search": False}
    provider = get_embedding_provider(config_disabled)
    assert provider is None

    # When semantic search is enabled
    config_enabled = {
        "enable_semantic_search": True,
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_dimensions": 384,
    }
    active_provider = get_embedding_provider(config_enabled)
    assert active_provider is not None
    assert isinstance(active_provider, LocalEmbeddingProvider)
    assert active_provider.model_name == "all-MiniLM-L6-v2"
    assert active_provider.dimensions == 384


def test_local_embedding_provider_lazy_load() -> None:
    """Test LocalEmbeddingProvider properties before model instantiation."""
    provider = LocalEmbeddingProvider("all-MiniLM-L6-v2", dimensions=384)
    assert provider.model_name == "all-MiniLM-L6-v2"
    assert provider.dimensions == 384
    # Ensure model is not loaded yet
    assert provider._model is None


def test_vector_conversions() -> None:
    """Test float vector to blob serialization and cosine similarity."""
    vec = [0.1, 0.5, 0.9, -0.4]
    blob = _vector_to_blob(vec)
    assert isinstance(blob, bytes)

    restored = _blob_to_vector(blob)
    assert len(restored) == 4
    for orig, res in zip(vec, restored):
        assert abs(orig - res) < 1e-5

    # Cosine similarity
    sim_self = _cosine_similarity_py(vec, vec)
    assert abs(sim_self - 1.0) < 1e-5

    orthogonal = [0.0, 1.0]
    orthogonal2 = [1.0, 0.0]
    assert abs(_cosine_similarity_py(orthogonal, orthogonal2)) < 1e-5


def test_vector_index_search_and_rebuild(test_db: DatabaseManager) -> None:
    """Test VectorIndex indexing, searching, and rebuilding."""
    provider = DummyEmbeddingProvider(dimensions=4)
    vector_idx = VectorIndex(test_db, provider)

    # Seed memories in table
    _seed_memory(test_db, "mem-db", "PostgreSQL database configuration")
    _seed_memory(test_db, "mem-auth", "JWT auth tokens and refresh flows")

    # Index memories
    vector_idx.index_memory("mem-db", "PostgreSQL database configuration")
    vector_idx.index_memory("mem-auth", "JWT auth tokens and refresh flows")

    # Search for database
    results = vector_idx.search("database query", limit=5)
    assert len(results) >= 1
    top_id, similarity = results[0]
    assert top_id == "mem-db"
    assert similarity > 0.8

    # Search for auth
    auth_results = vector_idx.search("jwt auth verification", limit=5)
    assert len(auth_results) >= 1
    assert auth_results[0][0] == "mem-auth"

    # Rebuild index
    count = vector_idx.rebuild()
    assert count == 2


def test_hybrid_search_rrf_and_execution(test_db: DatabaseManager) -> None:
    """Test HybridSearch reciprocal rank fusion merging."""
    fts = FullTextSearch(test_db)
    provider = DummyEmbeddingProvider(dimensions=4)
    vector_idx = VectorIndex(test_db, provider)

    # Seed memories
    _seed_memory(test_db, "mem-1", "Database replication setup with PostgreSQL")
    _seed_memory(test_db, "mem-2", "JWT auth middleware security")

    vector_idx.rebuild()

    hybrid = HybridSearch(fts, vector_idx)

    # 1. Test RRF function directly
    mock_fts = [{"id": "mem-1", "content": "A", "importance": 0.5}]
    mock_vec = [("mem-2", 0.95), ("mem-1", 0.85)]
    merged = hybrid._reciprocal_rank_fusion(mock_fts, mock_vec, k=60)

    assert len(merged) == 2
    # mem-1 appeared in both FTS (rank 1) and Vector (rank 2)
    # mem-1 score = 1/(60+1) + 1/(60+2)
    # mem-2 score = 1/(60+1)
    # mem-1 should be rank 1
    assert merged[0]["id"] == "mem-1"
    assert merged[0]["search_method"] == "hybrid"
    assert "rrf_score" in merged[0]

    # 2. Test search end-to-end
    results = hybrid.search("database replication", limit=10)
    assert len(results) >= 1
    assert results[0]["id"] == "mem-1"

    # 3. Test fallback when vector is None
    fts_only_hybrid = HybridSearch(fts, vector=None)
    fts_only_results = fts_only_hybrid.search("database", limit=5)
    assert len(fts_only_results) >= 1
    assert fts_only_results[0]["id"] == "mem-1"
