"""Tests for validation, sanitization, and secret detection."""

from __future__ import annotations

import pytest

from recallx.utils.validation import (
    detect_secrets,
    redact_secrets,
    sanitize_for_storage,
    validate_memory_content,
    validate_project_id,
    validate_tags,
)


def test_validate_memory_content_success() -> None:
    text = "   This is important context.   "
    validated = validate_memory_content(text)
    assert validated == "This is important context."


def test_validate_memory_content_empty() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_memory_content("   \n\t  ")


def test_validate_memory_content_too_long() -> None:
    too_long = "a" * 50_001
    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_memory_content(too_long)


def test_validate_project_id_success() -> None:
    assert validate_project_id("my-project_123") == "my-project_123"
    assert validate_project_id("  recallx-core  ") == "recallx-core"


def test_validate_project_id_invalid_chars() -> None:
    with pytest.raises(ValueError, match="Only alphanumeric"):
        validate_project_id("project/with/slashes")

    with pytest.raises(ValueError, match="Only alphanumeric"):
        validate_project_id("project with spaces")


def test_validate_project_id_length() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_project_id("   ")

    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_project_id("a" * 129)


def test_validate_tags_success() -> None:
    raw = ["PYTHON", "ai-agent", "Persistent_Storage", "python"]
    # Duplicates removed, lowercased, preserved order
    validated = validate_tags(raw)
    assert validated == ["python", "ai-agent", "persistent_storage"]


def test_validate_tags_constraints() -> None:
    with pytest.raises(ValueError, match="Cannot assign more than 20 tags"):
        validate_tags([f"tag-{i}" for i in range(21)])

    with pytest.raises(ValueError, match="exceeds maximum length"):
        validate_tags(["a" * 51])

    with pytest.raises(ValueError, match="contains invalid characters"):
        validate_tags(["invalid tag with space!"])


def test_sanitize_for_storage() -> None:
    text = "Hello\x00 World!\x07\x08 Good\nmorning\t\r."
    sanitized = sanitize_for_storage(text)
    assert "\x00" not in sanitized
    assert "\x07" not in sanitized
    assert "\x08" not in sanitized
    assert "Hello World! Good\nmorning\t\r." == sanitized


def test_detect_secrets() -> None:
    aws_text = "Deploy using AKIAIOSFODNN7EXAMPLE credentials"
    detected = detect_secrets(aws_text)
    assert "AWS Access Key ID" in detected

    gh_text = "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
    detected = detect_secrets(gh_text)
    assert "GitHub Token" in detected

    url_text = "postgres://admin:superSecretP@ssword@localhost:5432/mydb"
    detected = detect_secrets(url_text)
    assert "Password in URL" in detected

    clean_text = "This is a normal note about algorithms."
    assert detect_secrets(clean_text) == []


def test_redact_secrets() -> None:
    aws_text = "Key: AKIAIOSFODNN7EXAMPLE for user."
    redacted = redact_secrets(aws_text)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED]" in redacted

    url_text = "postgres://admin:superSecret@localhost:5432/db"
    redacted = redact_secrets(url_text)
    assert "superSecret" not in redacted
    assert "postgres://admin:[REDACTED]@localhost:5432/db" == redacted
