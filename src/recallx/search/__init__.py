"""Search and retrieval algorithms for RecallX."""

from __future__ import annotations

from recallx.search.embeddings import (
    EmbeddingProvider,
    LocalEmbeddingProvider,
    get_embedding_provider,
)
from recallx.search.fulltext import FullTextSearch
from recallx.search.hybrid import HybridSearch
from recallx.search.vector import VectorIndex

__all__ = [
    "EmbeddingProvider",
    "FullTextSearch",
    "HybridSearch",
    "LocalEmbeddingProvider",
    "VectorIndex",
    "get_embedding_provider",
]
