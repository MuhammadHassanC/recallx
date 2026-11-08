"""Unit tests for input validation, secret detection, and sanitization."""
from __future__ import annotations

import pytest

from recallx.utils.validation import (
    MAX_MEMORY_CONTENT_LENGTH,
    detect_secrets,
    redact_secrets,
    sanitize_for_storage,
    validate_memory_content,
    validate_project_id,
    validate_tags,
)


def test_validate_memory_content_valid() -> None:
    """Ensure valid content is stripped and returned properly."""
    content = "  This is a valid memory entry for RecallX.  \n"
    result = validate_memory_content(content)
    assert result == "This is a valid memory entry for RecallX."


def test_validate_memory_content_empty_raises() -> None:
    """Ensure empty or whitespace-only content raises ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_memory_content("")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_memory_content("    \t\n   ")


def test_validate_memory_content_too_long_raises() -> None:
    """Ensure content exceeding MAX_MEMORY_CONTENT_LENGTH raises ValueError."""
    oversized = "x" * (MAX_MEMORY_CONTENT_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_memory_content(oversized)


def test_validate_project_id_valid() -> None:
    """Ensure valid project identifiers pass validation."""
    valid_ids = [
        "recallx",
        "recallx-core",
        "project_123",
        "My-Project_v2",
    ]
    for pid in valid_ids:
        assert validate_project_id(pid) == pid


def test_validate_project_id_invalid_chars_raises() -> None:
    """Ensure project identifiers with invalid characters or traversal raise ValueError."""
    invalid_ids = [
        "../path-traversal",
        "project/sub",
        "project@id",
        "hello world",
        "proj!ect",
        "",
        "   ",
    ]
    for pid in invalid_ids:
        with pytest.raises(ValueError):
            validate_project_id(pid)


def test_validate_tags_valid() -> None:
    """Ensure valid tags are lowercased and deduplicated in order."""
    tags = ["Database", "SQL", "database", "orm_v2", "FAST-API"]
    validated = validate_tags(tags)
    assert validated == ["database", "sql", "orm_v2", "fast-api"]


def test_validate_tags_too_many_raises() -> None:
    """Ensure supplying more than the allowed maximum number of tags raises ValueError."""
    excessive_tags = [f"tag_{i}" for i in range(25)]
    with pytest.raises(ValueError, match="Cannot assign more than"):
        validate_tags(excessive_tags)


def test_detect_secrets_finds_aws_key() -> None:
    """Ensure AWS Access Key IDs are detected."""
    text = "Deploying with key AKIAIOSFODNN7EXAMPLE to S3 bucket."
    detected = detect_secrets(text)
    assert any("AWS Access Key" in item for item in detected)


def test_detect_secrets_finds_github_token() -> None:
    """Ensure GitHub personal access tokens are detected."""
    token = "ghp_" + "a" * 36
    text = f"Using token {token} for git clone."
    detected = detect_secrets(text)
    assert any("GitHub Token" in item for item in detected)


def test_detect_secrets_finds_generic_api_key() -> None:
    """Ensure generic API key assignments are detected."""
    text = 'api_key = "abcdef1234567890abcdef1234567890"'
    detected = detect_secrets(text)
    assert any("Generic API Secret" in item for item in detected)


def test_detect_secrets_no_false_positive_on_normal_text() -> None:
    """Ensure everyday technical writing does not trigger false positives."""
    safe_text = (
        "PostgreSQL 15 supports declarative partitioning and improved memory management. "
        "The authentication route uses standard PBKDF2 with 100000 iterations."
    )
    detected = detect_secrets(safe_text)
    assert len(detected) == 0


def test_redact_secrets_replaces_keys() -> None:
    """Ensure secret values are replaced with [REDACTED]."""
    text = "Secret is AKIAIOSFODNN7EXAMPLE and api_key = 'abcdef12345678901234567890'."
    redacted = redact_secrets(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "abcdef12345678901234567890" not in redacted
    assert "[REDACTED]" in redacted


def test_sanitize_for_storage_strips_null_bytes() -> None:
    """Ensure null bytes and corrupting control characters are stripped."""
    dirty_text = "Clean\x00Text\x00With\x08Bad\x00Chars\nPreserve newline\tPreserve tab"
    sanitized = sanitize_for_storage(dirty_text)
    assert "\x00" not in sanitized
    assert "\x08" not in sanitized
    assert "CleanTextWithBadChars\nPreserve newline\tPreserve tab" == sanitized
