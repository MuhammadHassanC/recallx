"""Input validation, data sanitization, and secret redaction for RecallX."""

from __future__ import annotations

import re
import unicodedata
from typing import Mapping

# Named regex patterns for identifying leaked credentials and high-risk secrets
DEFAULT_SECRET_DEFINITIONS: dict[str, str] = {
    "AWS Access Key ID": r"\bAKIA[0-9A-Z]{16}\b",
    "AWS Secret Access Key": r"(?i)(?:aws_secret_access_key|aws_secret_key)\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
    "GitHub Token": r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b",
    "GitHub Fine-Grained PAT": r"\bgithub_pat_[A-Za-z0-9_]{82}\b",
    "OpenAI/Anthropic API Key": r"\bsk-(?:live|ant|proj)?[A-Za-z0-9_-]{24,}\b",
    "Stripe Secret Key": r"\b(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,99}\b",
    "Slack Token": r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b",
    "Private Key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
    "JWT Token": r"\beyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*\b",
    "Password in URL": r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:\s/]+:)([^@\s/]+)(@[^:\s/]+)",
    "Generic API Secret Assignment": r"(?i)\b(?:api_key|apikey|secret_key|auth_token|access_token|bearer_token)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{16,})['\"]",
}

# Exported default regex strings for configuration
DEFAULT_SECRET_PATTERNS: list[str] = list(DEFAULT_SECRET_DEFINITIONS.values())

# Constraints
MAX_MEMORY_CONTENT_LENGTH = 50_000
MAX_PROJECT_ID_LENGTH = 128
MAX_TAG_LENGTH = 50
MAX_TAGS_COUNT = 20

_PROJECT_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
_TAG_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_memory_content(content: str) -> str:
    """Validate memory text content.

    Ensures the content is non-empty after trimming and does not exceed
    the maximum allowed length (50,000 characters).

    Args:
        content: Memory body string.

    Returns:
        Cleaned memory content with stripped leading and trailing whitespace.

    Raises:
        ValueError: If content is empty or exceeds 50,000 characters.
    """
    if not isinstance(content, str):
        raise ValueError(f"Memory content must be a string, got {type(content).__name__}.")

    trimmed = content.strip()
    if not trimmed:
        raise ValueError("Memory content cannot be empty.")

    if len(content) > MAX_MEMORY_CONTENT_LENGTH:
        raise ValueError(
            f"Memory content exceeds maximum length of {MAX_MEMORY_CONTENT_LENGTH:,} characters "
            f"(received {len(content):,} characters)."
        )

    return trimmed


def validate_project_id(project_id: str) -> str:
    """Validate project identifier.

    Project IDs must consist strictly of alphanumeric characters, hyphens,
    and underscores, with a maximum length of 128 characters.

    Args:
        project_id: Project identifier string.

    Returns:
        Validated project_id string.

    Raises:
        ValueError: If the identifier is empty, exceeds length, or contains invalid chars.
    """
    if not isinstance(project_id, str):
        raise ValueError(f"Project ID must be a string, got {type(project_id).__name__}.")

    trimmed = project_id.strip()
    if not trimmed:
        raise ValueError("Project ID cannot be empty.")

    if len(trimmed) > MAX_PROJECT_ID_LENGTH:
        raise ValueError(
            f"Project ID exceeds maximum length of {MAX_PROJECT_ID_LENGTH} characters "
            f"(received {len(trimmed)} characters)."
        )

    if not _PROJECT_ID_REGEX.match(trimmed):
        raise ValueError(
            f"Invalid Project ID '{trimmed}'. Only alphanumeric characters, hyphens, "
            "and underscores are permitted."
        )

    return trimmed


def validate_tags(tags: list[str]) -> list[str]:
    """Validate, normalize, and deduplicate tags.

    Tags must be alphanumeric with hyphens/underscores, maximum 50 characters each.
    A maximum of 20 tags per memory item is permitted.

    Args:
        tags: List of tag strings.

    Returns:
        Deduplicated, lowercase list of validated tags preserving insertion order.

    Raises:
        ValueError: If tag count exceeds 20 or any individual tag is invalid.
    """
    if not isinstance(tags, (list, tuple, set)):
        raise ValueError(f"Tags must be a sequence of strings, got {type(tags).__name__}.")

    if len(tags) > MAX_TAGS_COUNT:
        raise ValueError(
            f"Cannot assign more than {MAX_TAGS_COUNT} tags (received {len(tags)} tags)."
        )

    seen: set[str] = set()
    validated: list[str] = []

    for idx, raw_tag in enumerate(tags):
        if not isinstance(raw_tag, str):
            raise ValueError(f"Tag at index {idx} must be a string, got {type(raw_tag).__name__}.")

        normalized = raw_tag.strip().lower()
        if not normalized:
            raise ValueError(f"Tag at index {idx} cannot be empty.")

        if len(normalized) > MAX_TAG_LENGTH:
            raise ValueError(
                f"Tag '{normalized}' exceeds maximum length of {MAX_TAG_LENGTH} characters."
            )

        if not _TAG_REGEX.match(normalized):
            raise ValueError(
                f"Tag '{normalized}' contains invalid characters. Only alphanumeric, hyphens, "
                "and underscores are allowed."
            )

        if normalized not in seen:
            seen.add(normalized)
            validated.append(normalized)

    return validated


def sanitize_for_storage(text: str) -> str:
    """Sanitize text for safe database and filesystem storage.

    Strips null bytes, removes non-printable control characters (while preserving
    standard whitespace like newlines, tabs, and carriage returns), and normalizes
    unicode characters into NFC standard form.

    Args:
        text: Raw input text.

    Returns:
        Sanitized safe text string.
    """
    if not text:
        return ""

    # Remove null bytes immediately
    cleaned = text.replace("\x00", "")

    # Normalize unicode to standard NFC composition
    normalized = unicodedata.normalize("NFC", cleaned)

    # Filter out disruptive control characters while retaining valid formatting
    allowed_control = {"\n", "\r", "\t"}
    filtered_chars = [
        char
        for char in normalized
        if char in allowed_control or not unicodedata.category(char).startswith("C")
    ]

    return "".join(filtered_chars)


def detect_secrets(text: str, patterns: list[str] | None = None) -> list[str]:
    """Detect security credentials, access keys, or sensitive patterns in text.

    Args:
        text: Input string to inspect.
        patterns: Optional list of custom regex pattern strings. If omitted,
            the built-in DEFAULT_SECRET_DEFINITIONS are evaluated.

    Returns:
        List of identified secret types or pattern descriptions (without leaking secret values).
    """
    if not text:
        return []

    detected: list[str] = []

    if patterns is not None:
        # Use provided pattern strings
        for pattern_str in patterns:
            try:
                regex = re.compile(pattern_str)
                if regex.search(text):
                    detected.append(f"Secret pattern: {pattern_str}")
            except re.error:
                continue
    else:
        # Use default named dictionary
        for secret_name, pattern_str in DEFAULT_SECRET_DEFINITIONS.items():
            regex = re.compile(pattern_str)
            if regex.search(text):
                detected.append(secret_name)

    return detected


def redact_secrets(
    text: str,
    patterns: list[str] | None = None,
    replacement: str = "[REDACTED]",
) -> str:
    """Redact identified secrets and credentials from text.

    Replaces high-entropy credentials, private keys, and passwords with a safe placeholder.

    Args:
        text: Original text potentially containing credentials.
        patterns: Optional list of regex patterns to redact. Defaults to DEFAULT_SECRET_DEFINITIONS.
        replacement: Placeholder text (default '[REDACTED]').

    Returns:
        Sanitized text with credentials redacted.
    """
    if not text:
        return ""

    redacted = text

    if patterns is not None:
        for pattern_str in patterns:
            try:
                regex = re.compile(pattern_str)
                redacted = regex.sub(replacement, redacted)
            except re.error:
                continue
        return redacted

    # Execute tailored redaction with contextual capture group awareness
    for secret_name, pattern_str in DEFAULT_SECRET_DEFINITIONS.items():
        regex = re.compile(pattern_str)

        if secret_name == "Password in URL":
            # URL password group 2 is the password: group1 + replacement + group3
            redacted = regex.sub(rf"\g<1>{replacement}\g<3>", redacted)
        elif secret_name in ("AWS Secret Access Key", "Generic API Secret Assignment"):
            # Redact only the quoted/assigned value if capture group exists
            def _replace_assignment(m: re.Match[str]) -> str:
                full = m.group(0)
                val = m.group(1)
                return full.replace(val, replacement)

            redacted = regex.sub(_replace_assignment, redacted)
        else:
            redacted = regex.sub(replacement, redacted)

    return redacted
