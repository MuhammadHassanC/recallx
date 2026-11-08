"""Vector index and semantic similarity search using SQLite BLOB storage."""

from __future__ import annotations

import math
import sqlite3
import struct
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from recallx.search.embeddings import EmbeddingProvider
from recallx.utils.logging import get_logger

if TYPE_CHECKING:
    from recallx.storage.database import DatabaseManager

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

logger = get_logger("search.vector")


def _vector_to_blob(vec: list[float]) -> bytes:
    """Pack a list of float numbers into a 32-bit little-endian binary BLOB.

    Args:
        vec: List of float values.

    Returns:
        Packed bytes representation.
    """
    if _HAS_NUMPY:
        return np.array(vec, dtype=np.float32).tobytes()
    return struct.pack(f"<{len(vec)}f", *vec)


def _blob_to_vector(blob: bytes) -> list[float]:
    """Unpack a 32-bit little-endian binary BLOB into a list of floats.

    Args:
        blob: Packed bytes.

    Returns:
        List of float numbers.
    """
    if _HAS_NUMPY:
        return np.frombuffer(blob, dtype=np.float32).tolist()  # type: ignore[no-any-return]
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def _cosine_similarity_py(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors using pure Python.

    Args:
        v1: First float vector.
        v2: Second float vector.

    Returns:
        Cosine similarity score between -1.0 and 1.0 (or 0.0 if either has zero norm).
    """
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


class VectorIndex:
    """Manages dense vector storage and cosine similarity retrieval in SQLite.

    Stores embeddings as raw 32-bit binary float BLOBs in the dedicated
    'memory_vectors' table. Performs similarity search using NumPy vectorization
    when available, with pure Python fallback.
    """

    def __init__(self, db: DatabaseManager | Any, provider: EmbeddingProvider) -> None:
        """Initialize VectorIndex with database and embedding provider.

        Args:
            db: DatabaseManager or SQLite connection.
            provider: Active EmbeddingProvider instance.
        """
        self.db = db
        self.provider = provider
        self._ensure_table()

    def _execute(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a SQL statement with parameters across database interfaces."""
        bind_params = params or {}

        if hasattr(self.db, "engine"):
            with self.db.engine.begin() as conn:
                return conn.execute(text(sql), bind_params)

        if hasattr(self.db, "connect"):
            with self.db.connect() as conn:
                return conn.execute(text(sql), bind_params)

        if isinstance(self.db, sqlite3.Connection):
            cursor = self.db.cursor()
            cursor.execute(sql, bind_params)
            self.db.commit()
            return cursor

        if hasattr(self.db, "execute"):
            return self.db.execute(sql, bind_params)

        raise TypeError(f"Unsupported database manager type: {type(self.db).__name__}")

    def _fetchall(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows for a parameterized query."""
        bind_params = params or {}

        if hasattr(self.db, "engine"):
            with self.db.engine.connect() as conn:
                res = conn.execute(text(sql), bind_params)
                return [dict(row) for row in res.mappings()]

        if hasattr(self.db, "connect"):
            with self.db.connect() as conn:
                res = conn.execute(text(sql), bind_params)
                return [dict(row) for row in res.mappings()]

        if isinstance(self.db, sqlite3.Connection):
            old_factory = self.db.row_factory
            try:
                self.db.row_factory = sqlite3.Row
                cursor = self.db.cursor()
                cursor.execute(sql, bind_params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                self.db.row_factory = old_factory

        if hasattr(self.db, "execute"):
            cursor = self.db.execute(sql, bind_params)
            if hasattr(cursor, "mappings"):
                return [dict(row) for row in cursor.mappings()]
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows and hasattr(rows[0], "keys") else rows

        raise TypeError(f"Unsupported database manager type: {type(self.db).__name__}")

    def _ensure_table(self) -> None:
        """Ensure the memory_vectors table exists."""
        create_sql = """
            CREATE TABLE IF NOT EXISTS memory_vectors (
                memory_id TEXT PRIMARY KEY,
                embedding BLOB NOT NULL
            )
        """
        try:
            self._execute(create_sql)
            logger.debug("Table memory_vectors verified.")
        except Exception as exc:
            logger.error("Failed to initialize memory_vectors table: %s", exc)
            raise

    def index_memory(self, memory_id: str, content: str) -> None:
        """Generate and store embedding for a memory record.

        Args:
            memory_id: Target memory identifier.
            content: Textual content to embed.
        """
        if not content or not content.strip():
            logger.debug("Skipping empty content embedding for memory %s", memory_id)
            return

        try:
            vec = self.provider.embed(content)
            blob = _vector_to_blob(vec)
            upsert_sql = """
                INSERT INTO memory_vectors (memory_id, embedding)
                VALUES (:memory_id, :embedding)
                ON CONFLICT(memory_id) DO UPDATE SET embedding = excluded.embedding
            """
            self._execute(upsert_sql, {"memory_id": str(memory_id), "embedding": blob})
            logger.debug("Indexed vector for memory %s", memory_id)
        except Exception as exc:
            logger.error("Failed to index vector for memory %s: %s", memory_id, exc)
            raise

    def search(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        """Perform semantic cosine similarity search against indexed memory vectors.

        Args:
            query: Query string to embed and match.
            limit: Maximum number of closest matches to return (default 20).

        Returns:
            List of (memory_id, similarity) tuples sorted descending by similarity.
        """
        if not query or not query.strip():
            return []

        rows = self._fetchall("SELECT memory_id, embedding FROM memory_vectors")
        if not rows:
            return []

        query_vec = self.provider.embed(query)

        # Accelerated calculation using NumPy if available
        if _HAS_NUMPY:
            mem_ids = [str(row["memory_id"]) for row in rows]
            blobs = [bytes(row["embedding"]) for row in rows]
            dim = self.provider.dimensions

            # Reconstruct 2D matrix (N, D)
            matrix = np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(blobs), dim)
            q_arr = np.array(query_vec, dtype=np.float32)

            q_norm = np.linalg.norm(q_arr)
            if q_norm == 0:
                return []

            dots = np.dot(matrix, q_arr)
            matrix_norms = np.linalg.norm(matrix, axis=1)
            denominator = matrix_norms * q_norm

            # Avoid division by zero
            with np.errstate(divide="ignore", invalid="ignore"):
                sims = np.where(denominator > 0, dots / denominator, 0.0)

            top_k = min(max(1, limit), len(mem_ids))
            top_indices = np.argsort(sims)[::-1][:top_k]

            return [(mem_ids[idx], float(sims[idx])) for idx in top_indices]

        # Pure Python fallback
        scores: list[tuple[str, float]] = []
        for row in rows:
            mem_id = str(row["memory_id"])
            vec = _blob_to_vector(bytes(row["embedding"]))
            similarity = _cosine_similarity_py(query_vec, vec)
            scores.append((mem_id, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[: max(1, limit)]

    def rebuild(self) -> int:
        """Rebuild the entire vector index from active memories in the database.

        Deletes existing vector rows, reads all non-archived memories from the
        'memories' table, computes batch embeddings, and populates the index.

        Returns:
            Number of memories indexed into the vector store.
        """
        logger.info("Starting complete vector index rebuild...")
        self._ensure_table()
        self._execute("DELETE FROM memory_vectors")

        try:
            mem_rows = self._fetchall(
                "SELECT id, content FROM memories WHERE is_archived = 0 ORDER BY created_at ASC"
            )
        except Exception as exc:
            logger.warning("Could not read memories table for vector rebuild: %s", exc)
            return 0

        if not mem_rows:
            logger.info("No active memories found to index.")
            return 0

        valid_records = [(str(r["id"]), str(r["content"])) for r in mem_rows if str(r["content"]).strip()]
        if not valid_records:
            return 0

        ids, contents = zip(*valid_records)
        logger.info("Computing batch embeddings for %d memories...", len(contents))

        vectors = self.provider.embed_batch(list(contents))

        insert_sql = """
            INSERT INTO memory_vectors (memory_id, embedding)
            VALUES (:memory_id, :embedding)
        """
        for mem_id, vec in zip(ids, vectors):
            blob = _vector_to_blob(vec)
            self._execute(insert_sql, {"memory_id": mem_id, "embedding": blob})

        logger.info("Successfully rebuilt vector index with %d memories.", len(vectors))
        return len(vectors)
