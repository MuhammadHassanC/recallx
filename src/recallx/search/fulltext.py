"""Full-text search engine utilizing SQLite FTS5 for RecallX memories."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import text

from recallx.utils.logging import get_logger

if TYPE_CHECKING:
    from recallx.storage.database import DatabaseManager

logger = get_logger("search.fulltext")


class FullTextSearch:
    """Full-text search provider using SQLite FTS5 virtual table indexing."""

    def __init__(self, db: DatabaseManager | Any) -> None:
        """Initialize FullTextSearch with the database manager.

        Args:
            db: DatabaseManager instance or compatible SQLite connection manager.
        """
        self.db = db

    def _escape_fts_query(self, query: str) -> str:
        """Escape special characters in a raw search query for FTS5.

        Strips non-printable characters and doubles internal quotes so they
        do not break FTS5 token grammar.

        Args:
            query: Raw user query string.

        Returns:
            Sanitized query string safe for FTS5 syntax formatting.
        """
        if not query:
            return ""
        # Remove non-printable characters
        cleaned = "".join(char for char in query if char.isprintable())
        # Escape double quotes by doubling them
        return cleaned.replace('"', '""')

    def _build_fts_query(self, query: str) -> str:
        """Convert a natural language search query into valid FTS5 syntax.

        Extracts alphanumeric keywords, escapes quotes, and formats them into
        prefix-matched tokens joined by boolean AND.

        Args:
            query: Natural language query string.

        Returns:
            FTS5-compatible MATCH expression string.
        """
        if not query or not query.strip():
            return ""

        # Extract tokens: alphanumeric sequences, hyphens, and underscores
        tokens = re.findall(r"[a-zA-Z0-9_\-]+", query)
        if not tokens:
            return ""

        terms = [f'"{self._escape_fts_query(token)}"*' for token in tokens]
        return " AND ".join(terms)

    def _execute_sql(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a parameterized query across various database manager interfaces.

        Supports SQLAlchemy Engine, Session, raw SQLite connection, or duck-typed managers.

        Args:
            sql: SQL statement string.
            params: Dictionary of bind parameters.

        Returns:
            List of row dictionaries.
        """
        # SQLAlchemy DatabaseManager with engine
        if hasattr(self.db, "engine"):
            with self.db.engine.connect() as conn:
                cursor_res = conn.execute(text(sql), params)
                return [dict(row) for row in cursor_res.mappings()]

        # Direct SQLAlchemy Connection or Session
        if hasattr(self.db, "connect"):
            with self.db.connect() as conn:
                cursor_res = conn.execute(text(sql), params)
                return [dict(row) for row in cursor_res.mappings()]

        # Raw sqlite3.Connection
        if isinstance(self.db, sqlite3.Connection):
            old_factory = self.db.row_factory
            try:
                self.db.row_factory = sqlite3.Row
                cursor = self.db.cursor()
                # Convert named :param to ? or execute with dict
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
            finally:
                self.db.row_factory = old_factory

        # Generic object with execute method
        if hasattr(self.db, "execute"):
            cursor = self.db.execute(sql, params)
            if hasattr(cursor, "mappings"):
                return [dict(row) for row in cursor.mappings()]
            if hasattr(cursor, "fetchall"):
                rows = cursor.fetchall()
                if rows and hasattr(rows[0], "keys"):
                    return [dict(row) for row in rows]
                return [dict(row) for row in rows]

        raise TypeError(f"Unsupported database manager type: {type(self.db).__name__}")

    def _format_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw database row into standard memory dictionary format.

        Args:
            row: Raw database result mapping.

        Returns:
            Normalized dictionary containing memory attributes and fts rank.
        """
        item = dict(row)

        # Parse JSON tags
        raw_tags = item.get("tags")
        if isinstance(raw_tags, str):
            try:
                item["tags"] = json.loads(raw_tags)
            except Exception:
                item["tags"] = [raw_tags] if raw_tags else []
        elif raw_tags is None:
            item["tags"] = []

        # Parse metadata_json
        meta = item.get("metadata_json") or item.get("metadata")
        if isinstance(meta, str):
            try:
                item["metadata"] = json.loads(meta)
                item["metadata_json"] = item["metadata"]
            except Exception:
                item["metadata"] = {}
                item["metadata_json"] = {}
        elif isinstance(meta, dict):
            item["metadata"] = meta
            item["metadata_json"] = meta
        else:
            item["metadata"] = {}
            item["metadata_json"] = {}

        # Ensure rank is float
        if "rank" in item and item["rank"] is not None:
            try:
                item["rank"] = float(item["rank"])
            except (ValueError, TypeError):
                item["rank"] = 0.0

        return item

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search memories using SQLite FTS5 full-text indexing.

        Matches natural query keywords against content, tags, memory_type, and project_id.
        Sorts results primarily by FTS rank (BM25 relevance score), with secondary ordering
        by importance score.

        Args:
            query: Natural language or keyword query string.
            project_id: Optional project identifier filter.
            memory_type: Optional memory type filter ('project', 'decision', etc.).
            limit: Maximum number of search results to return (default 20).

        Returns:
            List of matching memory records as dictionaries, including the 'rank' score.
        """
        if not query or not query.strip():
            return []

        fts_match = self._build_fts_query(query)
        if not fts_match:
            return []

        # Construct primary joined query
        clauses = [
            "memory_fts MATCH :match_query",
            "m.is_archived = 0",
        ]
        params: dict[str, Any] = {
            "match_query": fts_match,
            "limit": max(1, limit),
        }

        if project_id is not None:
            clauses.append("m.project_id = :project_id")
            params["project_id"] = str(project_id)

        if memory_type is not None:
            clauses.append("m.memory_type = :memory_type")
            params["memory_type"] = str(memory_type)

        where_sql = " AND ".join(clauses)

        primary_sql = f"""
            SELECT
                m.id,
                m.memory_type,
                m.content,
                m.project_id,
                m.tags,
                m.source,
                m.importance,
                m.confidence,
                m.is_pinned,
                m.is_archived,
                m.content_hash,
                m.metadata_json,
                m.expires_at,
                m.created_at,
                m.updated_at,
                m.accessed_at,
                fts.rank AS rank
            FROM memory_fts fts
            JOIN memories m ON fts.id = m.id
            WHERE {where_sql}
            ORDER BY fts.rank ASC, m.importance DESC
            LIMIT :limit
        """

        try:
            rows = self._execute_sql(primary_sql, params)
        except Exception as exc:
            logger.warning(
                "Joined FTS search failed (%s); attempting standalone memory_fts query.",
                exc,
            )
            # Standalone fallback query directly against memory_fts
            fallback_clauses = ["memory_fts MATCH :match_query"]
            fallback_params: dict[str, Any] = {
                "match_query": fts_match,
                "limit": max(1, limit),
            }
            if project_id is not None:
                fallback_clauses.append("project_id = :project_id")
                fallback_params["project_id"] = str(project_id)
            if memory_type is not None:
                fallback_clauses.append("memory_type = :memory_type")
                fallback_params["memory_type"] = str(memory_type)

            fallback_sql = f"""
                SELECT
                    id,
                    content,
                    tags,
                    memory_type,
                    project_id,
                    rank
                FROM memory_fts
                WHERE {' AND '.join(fallback_clauses)}
                ORDER BY rank ASC
                LIMIT :limit
            """
            try:
                rows = self._execute_sql(fallback_sql, fallback_params)
            except Exception as fallback_exc:
                logger.error("FTS search execution failed: %s", fallback_exc)
                return []

        # If zero results and multiple tokens, attempt an OR fallback query
        tokens = re.findall(r"[a-zA-Z0-9_\-]+", query)
        if not rows and len(tokens) > 1:
            or_match = " OR ".join(f'"{self._escape_fts_query(t)}"*' for t in tokens)
            params["match_query"] = or_match
            try:
                rows = self._execute_sql(primary_sql, params)
            except Exception:
                pass

        return [self._format_row(row) for row in rows]
