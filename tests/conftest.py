"""Shared test fixtures for RecallX."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from recallx.storage.database import DatabaseManager
from recallx.storage.repositories import MemoryRepository, ProjectRepository
from recallx.core.memory import MemoryEngine


@pytest.fixture
def tmp_path_factory_unique(tmp_path: Path) -> Path:
    """Provide a unique temporary directory for each test."""
    return tmp_path


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test_recallx.db"


@pytest.fixture
def db(db_path: Path):
    """Provide an initialized DatabaseManager."""
    database = DatabaseManager(db_path)
    database.initialize()
    yield database
    database.close()


@pytest.fixture
def memory_repo(db: DatabaseManager) -> MemoryRepository:
    """Provide a MemoryRepository."""
    return MemoryRepository(db)


@pytest.fixture
def project_repo(db: DatabaseManager) -> ProjectRepository:
    """Provide a ProjectRepository."""
    return ProjectRepository(db)


@pytest.fixture
def engine(db: DatabaseManager) -> MemoryEngine:
    """Provide a MemoryEngine."""
    return MemoryEngine(db)


@pytest.fixture
def sample_memory() -> dict:
    """Provide sample memory data."""
    return {
        "content": (
            "Using PostgreSQL with SQLAlchemy ORM for the API backend. Chose PostgreSQL over SQLite "
            "for concurrent write support needed by the webhook processor."
        ),
        "project_id": "test-project",
        "memory_type": "decision",
        "tags": ["database", "architecture"],
        "importance": 0.8,
        "source": "test",
    }


@pytest.fixture
def sample_memories() -> list[dict]:
    """Provide multiple sample memories."""
    return [
        {
            "content": "Project uses React 18 with TypeScript and Vite for the frontend",
            "project_id": "test-project",
            "memory_type": "project",
            "tags": ["frontend", "stack"],
            "importance": 0.7,
        },
        {
            "content": (
                "JWT authentication with refresh tokens. Access tokens expire in 15 minutes, "
                "refresh tokens in 7 days."
            ),
            "project_id": "test-project",
            "memory_type": "decision",
            "tags": ["auth", "security"],
            "importance": 0.9,
        },
        {
            "content": (
                "Fixed CORS error by adding credentials: 'include' to fetch requests and configuring "
                "allowed origins on the backend."
            ),
            "project_id": "test-project",
            "memory_type": "bug_solution",
            "tags": ["cors", "fetch", "bug"],
            "importance": 0.6,
        },
        {
            "content": (
                "Always use absolute imports in Python. Use ruff for linting. Prefer dataclasses over "
                "plain dicts."
            ),
            "project_id": "test-project",
            "memory_type": "preference",
            "tags": ["style", "python"],
            "importance": 0.5,
        },
        {
            "content": (
                "Completed authentication flow implementation. Pending: rate limiting, audit logging."
            ),
            "project_id": "test-project",
            "memory_type": "session",
            "tags": ["auth", "progress"],
            "importance": 0.4,
        },
    ]
