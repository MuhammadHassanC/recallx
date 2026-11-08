"""Unit tests for content normalization, hashing, and ID generation."""
from __future__ import annotations

from recallx.utils.hashing import content_hash, normalize_content, short_id


def test_normalize_content_strips_whitespace() -> None:
    """Ensure leading and trailing whitespace is stripped."""
    text = "   hello world   \n\t"
    assert normalize_content(text) == "hello world"


def test_normalize_content_lowercases() -> None:
    """Ensure characters are converted to lowercase."""
    text = "PostgreSQL With SQLAlchemy ORM"
    assert normalize_content(text) == "postgresql with sqlalchemy orm"


def test_normalize_content_collapses_spaces() -> None:
    """Ensure multiple spaces, tabs, and newlines are collapsed into single spaces."""
    text = "PostgreSQL   \n\n\t  with   SQLAlchemy\t\tORM"
    assert normalize_content(text) == "postgresql with sqlalchemy orm"


def test_content_hash_deterministic() -> None:
    """Ensure identical calls produce the identical hash digest."""
    text = "Memory content for caching"
    hash1 = content_hash(text)
    hash2 = content_hash(text)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_content_hash_different_for_different_content() -> None:
    """Ensure differing texts produce different hashes."""
    hash1 = content_hash("System architecture using microservices")
    hash2 = content_hash("System architecture using monolith")
    assert hash1 != hash2


def test_content_hash_same_for_normalized_equivalent() -> None:
    """Ensure texts that normalize to the same string produce the exact same hash."""
    t1 = "  Using Redis For Caching  \n"
    t2 = "using   redis   for   caching"
    assert content_hash(t1) == content_hash(t2)


def test_short_id_length() -> None:
    """Ensure short_id returns strings of the requested length."""
    assert len(short_id(8)) == 8
    assert len(short_id(12)) == 12
    assert len(short_id(16)) == 16
    assert len(short_id(32)) == 32


def test_short_id_unique() -> None:
    """Ensure generated short IDs are unique."""
    ids = {short_id(12) for _ in range(1000)}
    assert len(ids) == 1000
