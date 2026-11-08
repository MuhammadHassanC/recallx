"""Embedding provider interface and local model implementations for RecallX."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from recallx.utils.logging import get_logger

logger = get_logger("search.embeddings")


class EmbeddingProvider(ABC):
    """Abstract interface defining required contract for vector embedding providers."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return dimensionality of the embedding vectors produced by this provider."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier or path."""
        ...

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate a single vector embedding for the input text.

        Args:
            text: Input string to embed.

        Returns:
            List of float values representing the embedding vector.
        """
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a sequence of texts.

        Args:
            texts: List of strings to embed.

        Returns:
            List of embedding vectors, one for each input text.
        """
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embedding generator powered by sentence-transformers.

    Loads the underlying neural model lazily upon first inference request
    to minimize startup latency and memory overhead.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        dimensions: int = 384,
    ) -> None:
        """Initialize the local embedding provider.

        Args:
            model_name: Hugging Face model identifier (default 'all-MiniLM-L6-v2').
            dimensions: Vector embedding dimensionality (default 384).
        """
        self._model_name = model_name
        self._dimensions = dimensions
        self._model: Any = None

    @property
    def model_name(self) -> str:
        """Return the Hugging Face model identifier."""
        return self._model_name

    @property
    def dimensions(self) -> int:
        """Return vector dimension count."""
        return self._dimensions

    def _get_model(self) -> Any:
        """Lazily load the SentenceTransformer instance.

        Returns:
            Active SentenceTransformer model instance.

        Raises:
            ImportError: If sentence-transformers is not installed.
        """
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as exc:
            msg = (
                "Local semantic embeddings require the 'sentence-transformers' package.\n"
                "To enable semantic vector search, install RecallX with the semantic extra:\n"
                "    pip install recallx[semantic]\n"
                "or install directly:\n"
                "    pip install sentence-transformers"
            )
            logger.error(msg)
            raise ImportError(msg) from exc

        logger.info("Loading local embedding model '%s'...", self._model_name)
        model = SentenceTransformer(self._model_name)
        try:
            detected_dim = model.get_sentence_embedding_dimension()
            if detected_dim is not None:
                self._dimensions = int(detected_dim)
        except Exception as exc:
            logger.debug("Could not automatically inspect model dimension: %s", exc)

        self._model = model
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate vector embedding for a single text string.

        Args:
            text: Input string to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        if not text or not text.strip():
            return [0.0] * self._dimensions

        model = self._get_model()
        vector = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        return [float(x) for x in vector]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for multiple text strings.

        Args:
            texts: List of strings to embed.

        Returns:
            List of float vectors corresponding to input strings.
        """
        if not texts:
            return []

        model = self._get_model()
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [[float(x) for x in vec] for vec in vectors]


def get_embedding_provider(config: Any = None) -> EmbeddingProvider | None:
    """Factory function resolving the configured embedding provider.

    Inspects the configuration to determine whether semantic vector search
    is enabled. Returns a LocalEmbeddingProvider instance when enabled,
    or None when disabled.

    Args:
        config: Optional RecallXConfig instance or dictionary. If omitted,
            loads the global active configuration.

    Returns:
        Configured EmbeddingProvider instance, or None if disabled.
    """
    if config is None:
        try:
            from recallx.config import get_config

            config = get_config()
        except Exception as exc:
            logger.debug("Unable to load global config: %s", exc)
            return None

    # Handle both Pydantic model and dict
    if isinstance(config, dict):
        enabled = bool(config.get("enable_semantic_search", False))
        model_name = str(config.get("embedding_model", "all-MiniLM-L6-v2"))
        dims = int(config.get("embedding_dimensions", 384))
    else:
        enabled = bool(getattr(config, "enable_semantic_search", False))
        model_name = str(getattr(config, "embedding_model", "all-MiniLM-L6-v2"))
        dims = int(getattr(config, "embedding_dimensions", 384))

    if not enabled:
        logger.debug("Semantic vector search is disabled in configuration.")
        return None

    return LocalEmbeddingProvider(model_name=model_name, dimensions=dims)
