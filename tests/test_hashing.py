"""Tests for content hashing and ID utilities."""

from __future__ import annotations

import hashlib

from recallx.utils.hashing import content_hash, normalize_content, short_id


def test_normalize_content_empty() -> None:
    assert normalize_content("") == ""
    assert normalize_content("   ") == ""


def test_normalize_content_whitespace_and_casing() -> None:
    raw = "   HeLLo   \n\t  WorLD   \r\n test   "
    expected = "hello world test"
    assert normalize_content(raw) == expected


def test_content_hash_deterministic() -> None:
    text1 = "Persistent Memory for Agents"
    text2 = "  persistent   memory   for  agents  \n"
    hash1 = content_hash(text1)
    hash2 = content_hash(text2)

    assert hash1 == hash2
    assert len(hash1) == 64
    assert hash1 == hashlib.sha256(b"persistent memory for agents").hexdigest()


def test_short_id() -> None:
    id1 = short_id()
    id2 = short_id()

    assert len(id1) == 12
    assert len(id2) == 12
    assert id1 != id2

    custom_len = short_id(length=8)
    assert len(custom_len) == 8

    # Clamping boundaries
    assert len(short_id(length=0)) == 1
    assert len(short_id(length=50)) == 32
