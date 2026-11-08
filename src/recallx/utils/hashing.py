"""Content hashing and identifier generation utilities for RecallX."""

from __future__ import annotations

import hashlib
import uuid


def normalize_content(text: str) -> str:
    """Normalize text content for deterministic comparison and hashing.

    Trims leading/trailing whitespace, converts all characters to lowercase,
    and collapses any consecutive whitespace characters (including newlines
    and tabs) into a single space.

    Args:
        text: Input string to normalize.

    Returns:
        Normalized string.
    """
    if not text:
        return ""
    return " ".join(text.strip().lower().split())


def content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hex digest of normalized content.

    Args:
        text: Content to hash.

    Returns:
        64-character lowercase SHA-256 hexadecimal string.
    """
    normalized = normalize_content(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def short_id(length: int = 12) -> str:
    """Generate a short unique identifier based on UUID4.

    Args:
        length: Desired character length (1 to 32, default 12).

    Returns:
        Hexadecimal unique identifier string.
    """
    clamped_len = max(1, min(length, 32))
    return uuid.uuid4().hex[:clamped_len]
