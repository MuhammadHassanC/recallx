"""Security integration tests verifying secret redaction, SQL injection prevention, and isolation."""
from __future__ import annotations

import pytest

from recallx.core.memory import MemoryEngine


def test_secret_redaction_on_remember(engine: MemoryEngine) -> None:
    """Ensure sensitive credentials and tokens are redacted prior to storage."""
    raw_content = (
        "Connecting to AWS S3 bucket with AKIAIOSFODNN7EXAMPLE. "
        "Also set api_key = 'sk-live-1234567890abcdef12345678'."
    )
    saved = engine.remember(content=raw_content, project_id="sec-proj")

    assert "AKIAIOSFODNN7EXAMPLE" not in saved["content"]
    assert "sk-live-1234567890abcdef12345678" not in saved["content"]
    assert "[REDACTED]" in saved["content"]

    # Verify retrieval from database also contains redacted version
    retrieved = engine.get(saved["id"])
    assert retrieved is not None
    assert "AKIAIOSFODNN7EXAMPLE" not in retrieved["content"]


def test_sql_injection_in_search(engine: MemoryEngine) -> None:
    """Ensure SQL injection payloads in search queries do not alter query logic or crash."""
    engine.remember(content="Legitimate engineering architecture note", project_id="sec-proj")

    injection_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE memories; --",
        "\" OR 1=1 --",
        "' UNION SELECT * FROM memories --",
        "') OR ('1'='1",
    ]

    for payload in injection_payloads:
        results = engine.recall(query=payload, project_id="sec-proj")
        assert isinstance(results, list)
        # Injection must not expose other records arbitrarily
        assert len(results) <= 1


def test_sql_injection_in_project_id(engine: MemoryEngine) -> None:
    """Ensure SQL injection attempts in project identifiers are rejected during validation."""
    malicious_ids = [
        "proj'; DROP TABLE memories; --",
        "alpha' OR '1'='1",
        "proj\" UNION SELECT 1--",
    ]
    for pid in malicious_ids:
        with pytest.raises(ValueError):
            engine.remember(content="Safe content body", project_id=pid)


def test_path_traversal_in_project_id(engine: MemoryEngine) -> None:
    """Ensure directory traversal attempts in project IDs are rejected."""
    traversal_ids = [
        "../../etc/passwd",
        "../..\\Windows\\System32",
        "projects/../../secret",
        "..",
        "./subfolder",
    ]
    for pid in traversal_ids:
        with pytest.raises(ValueError):
            engine.remember(content="Valid content string", project_id=pid)


def test_null_bytes_sanitized(engine: MemoryEngine) -> None:
    """Ensure embedded null bytes and harmful control characters are stripped."""
    content_with_nulls = "Payload\x00with\x00null\x00bytes\x08and\x07bell"
    saved = engine.remember(content=content_with_nulls, project_id="sec-proj")

    assert "\x00" not in saved["content"]
    assert "\x08" not in saved["content"]
    assert "\x07" not in saved["content"]
    assert "Payloadwithnullbytesandbell" == saved["content"]


def test_very_large_content_rejected(engine: MemoryEngine) -> None:
    """Ensure oversized memory bodies (>50KB) are rejected."""
    huge_text = "A" * 60_000
    with pytest.raises(ValueError, match="exceeds maximum length"):
        engine.remember(content=huge_text, project_id="sec-proj")


def test_cross_project_retrieval_blocked(engine: MemoryEngine) -> None:
    """Ensure queries in project A never return sensitive records from project B."""
    engine.remember(
        content="Confidential proprietary payment processing algorithm v2",
        project_id="client-alpha",
    )

    results_in_beta = engine.recall(
        query="proprietary payment processing algorithm",
        project_id="client-beta",
    )
    assert len(results_in_beta) == 0
