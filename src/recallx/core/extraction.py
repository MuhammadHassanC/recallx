"""Deterministic rule-based memory extraction from text and conversations."""

from __future__ import annotations

import re
from typing import Any

from recallx.utils.logging import get_logger

logger = get_logger("recallx.core.extraction")


class MemoryExtractor:
    """Extracts structured memories from unstructured text using deterministic regex rules."""

    # Pre-compiled patterns for decisions
    _DECISION_PATTERNS = [
        re.compile(
            r"(?i)(?:we\s+)?decided\s+to\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)chose\s+([^.\n]+?\s+over\s+[^.\n]+)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)using\s+([^.\n]+?\s+because\s+[^.\n]+)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:decision|architecture|rationale)\s*[:\-]\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:we\s+)?opted\s+to\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:architectural|design)\s+choice\s*[:\-]?\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
    ]

    # Pre-compiled patterns for bugs and solutions
    _BUG_PATTERNS = [
        re.compile(
            r"(?i)(?:fixed|resolved)\s+(?:the\s+)?(?:bug|issue|error|crash)\s*(?:where|in|with)?\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:root\s+cause|the\s+issue\s+was)\s*[:\-]?\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:bug|error|issue)\s*[:\-]\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:fix|solution|resolution)\s*[:\-]\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:solved\s+by|fixed\s+by)\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
    ]

    # Pre-compiled patterns for preferences and standards
    _PREFERENCE_PATTERNS = [
        re.compile(
            r"(?i)(?:always\s+use|prefer\s+to\s+use|prefer)\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:never\s+use|avoid\s+using|do\s+not\s+use)\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:convention|standard|guideline|rule|code\s+style)\s*[:\-]\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:our\s+standard\s+is|team\s+preference\s+is)\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
    ]

    # Pre-compiled patterns for project architecture and tech stack
    _PROJECT_PATTERNS = [
        re.compile(
            r"(?i)(?:tech\s+stack|stack|built\s+with|uses\s+framework)\s*[:\-]\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)uses\s+([^.\n]+?\s+for\s+[^.\n]+)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)(?:backend|frontend|api|database|db)\s+(?:is|uses)\s+([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
        re.compile(
            r"(?i)project\s+(?:structure|overview|setup)\s*[:\-]\s*([^.\n]+(?:\.[^.\n]+)*)",
            re.MULTILINE,
        ),
    ]

    def extract(self, text: str, project_id: str, source: str = "extraction") -> list[dict[str, Any]]:
        """Parse text for extractable memories across all categories.

        Args:
            text: Input document or dialogue text.
            project_id: Project identifier to assign.
            source: Extraction source label (defaults to 'extraction').

        Returns:
            List of memory payload dictionaries ready for ingestion by remember().
        """
        if not text or not text.strip():
            return []

        extracted_items: list[dict[str, Any]] = []
        extracted_items.extend(self._extract_decisions(text))
        extracted_items.extend(self._extract_bugs(text))
        extracted_items.extend(self._extract_preferences(text))
        extracted_items.extend(self._extract_project_info(text))

        # Deduplicate results by normalized content
        seen_contents: set[str] = set()
        ready_memories: list[dict[str, Any]] = []

        for item in extracted_items:
            raw_content = str(item["content"]).strip()
            norm = " ".join(raw_content.lower().split())
            if len(norm) < 15 or norm in seen_contents:
                continue
            seen_contents.add(norm)

            m_type = item["memory_type"]
            method = item.get("extraction_method", "pattern")

            ready_memories.append(
                {
                    "content": raw_content,
                    "project_id": project_id,
                    "memory_type": m_type,
                    "tags": item.get("tags", []),
                    "source": source,
                    "importance": self._assign_importance(m_type, raw_content),
                    "confidence": self._assign_confidence(method),
                    "metadata": {
                        "extracted_via": method,
                        "raw_tags": item.get("tags", []),
                    },
                }
            )

        return ready_memories

    def _extract_decisions(self, text: str) -> list[dict[str, Any]]:
        """Extract architectural and engineering decisions."""
        memories: list[dict[str, Any]] = []
        lines_and_blocks = self._split_units(text)

        for unit in lines_and_blocks:
            for pattern in self._DECISION_PATTERNS:
                m = pattern.search(unit)
                if m:
                    extracted_text = self._clean_matched_unit(unit, m.group(0))
                    tags = self._infer_tags(extracted_text, extra=["decision", "architecture"])
                    method = "explicit" if any(k in unit.lower() for k in ["decision:", "architecture:"]) else "pattern"
                    memories.append(
                        {
                            "content": extracted_text,
                            "memory_type": "decision",
                            "tags": tags,
                            "extraction_method": method,
                        }
                    )
                    break

        return memories

    def _extract_bugs(self, text: str) -> list[dict[str, Any]]:
        """Extract resolved bugs, errors, and workarounds."""
        memories: list[dict[str, Any]] = []
        lines_and_blocks = self._split_units(text)

        for unit in lines_and_blocks:
            for pattern in self._BUG_PATTERNS:
                m = pattern.search(unit)
                if m:
                    extracted_text = self._clean_matched_unit(unit, m.group(0))
                    tags = self._infer_tags(extracted_text, extra=["bug", "fix"])
                    method = "explicit" if any(k in unit.lower() for k in ["solution:", "root cause:"]) else "pattern"
                    memories.append(
                        {
                            "content": extracted_text,
                            "memory_type": "bug_solution",
                            "tags": tags,
                            "extraction_method": method,
                        }
                    )
                    break

        return memories

    def _extract_preferences(self, text: str) -> list[dict[str, Any]]:
        """Extract coding preferences, project conventions, and team guidelines."""
        memories: list[dict[str, Any]] = []
        lines_and_blocks = self._split_units(text)

        for unit in lines_and_blocks:
            for pattern in self._PREFERENCE_PATTERNS:
                m = pattern.search(unit)
                if m:
                    extracted_text = self._clean_matched_unit(unit, m.group(0))
                    tags = self._infer_tags(extracted_text, extra=["preference", "convention"])
                    method = "explicit" if any(k in unit.lower() for k in ["convention:", "standard:"]) else "pattern"
                    memories.append(
                        {
                            "content": extracted_text,
                            "memory_type": "preference",
                            "tags": tags,
                            "extraction_method": method,
                        }
                    )
                    break

        return memories

    def _extract_project_info(self, text: str) -> list[dict[str, Any]]:
        """Extract project tech stack and infrastructure details."""
        memories: list[dict[str, Any]] = []
        lines_and_blocks = self._split_units(text)

        for unit in lines_and_blocks:
            for pattern in self._PROJECT_PATTERNS:
                m = pattern.search(unit)
                if m:
                    extracted_text = self._clean_matched_unit(unit, m.group(0))
                    tags = self._infer_tags(extracted_text, extra=["project", "stack"])
                    method = "explicit" if any(k in unit.lower() for k in ["stack:", "architecture:"]) else "pattern"
                    memories.append(
                        {
                            "content": extracted_text,
                            "memory_type": "project",
                            "tags": tags,
                            "extraction_method": method,
                        }
                    )
                    break

        return memories

    def _assign_importance(self, memory_type: str, content: str) -> float:
        """Heuristic scoring of memory importance."""
        base_map: dict[str, float] = {
            "decision": 0.80,
            "bug_solution": 0.70,
            "preference": 0.65,
            "project": 0.75,
            "session": 0.50,
        }
        score = base_map.get(memory_type, 0.50)
        c_lower = content.lower()

        # Elevate critical and security-relevant items
        if any(w in c_lower for w in ["security", "critical", "auth", "credential", "database migration"]):
            score += 0.15
        elif any(w in c_lower for w in ["always", "never", "production", "breaking change"]):
            score += 0.10

        return round(max(0.1, min(1.0, score)), 2)

    def _assign_confidence(self, extraction_method: str) -> float:
        """Assign confidence rating based on specificity of extraction."""
        if extraction_method == "explicit":
            return 0.90
        if extraction_method == "pattern":
            return 0.80
        return 0.70

    def _split_units(self, text: str) -> list[str]:
        """Split text into sentence and bullet-level units for extraction."""
        units: list[str] = []
        for line in text.splitlines():
            cleaned = line.strip()
            # Clean markdown bullets and numbers
            cleaned = re.sub(r"^[*\-+]\s+", "", cleaned)
            cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
            cleaned = re.sub(r"^#+\s+", "", cleaned)
            if not cleaned:
                continue

            # Split sentences within line
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            for s in sentences:
                s_strip = s.strip()
                if len(s_strip) >= 15:
                    units.append(s_strip)

        return units

    def _clean_matched_unit(self, unit: str, match_str: str) -> str:
        """Format the matched unit cleanly."""
        # Use full unit if it provides complete sentence context
        if len(unit) <= 250:
            return unit
        return match_str.strip()

    def _infer_tags(self, text: str, extra: list[str] | None = None) -> list[str]:
        """Infer thematic tags from content."""
        tags: list[str] = list(extra or [])
        t_lower = text.lower()

        keywords = [
            "python", "typescript", "javascript", "react", "vue", "fastapi", "django",
            "flask", "sqlite", "postgres", "redis", "docker", "auth", "jwt", "api",
            "cors", "rest", "graphql", "orm", "sqlalchemy", "pydantic", "git", "ci",
        ]

        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", t_lower):
                tags.append(kw)

        # Deduplicate
        return list(dict.fromkeys(tags))[:10]
