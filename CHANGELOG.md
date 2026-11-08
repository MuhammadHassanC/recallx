# Changelog

All notable changes to RecallX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-11-08

### Added
- Core memory engine with CRUD operations (create, read, update, delete).
- SQLite storage with FTS5 full-text search and BM25 relevance scoring.
- Model Context Protocol (MCP) server supporting stdio transport for universal agent integration.
- Command-line interface (`recallx`) powered by Typer and Rich formatting for all operations.
- Project-aware memory isolation preventing cross-project context pollution.
- Multi-signal relevance ranking incorporating keyword matching, importance weighting, and time decay.
- Rule-based memory extraction identifying architectural patterns, bug solutions, decisions, and preferences.
- Duplicate detection and memory consolidation with similarity metrics.
- High-entropy secret detection and automatic redaction before persistence.
- Complete data portability: JSON import, export, and transactional database backups.
- Agent integration configurations and quick-start guides for Claude Code, Cursor, Gemini CLI / Antigravity, Codex, and OpenCode.
- Agent skills specification and prompts (`recallx-remember`, `recallx-recall`, `recallx-project-context`).
- Optional local semantic search using Hugging Face sentence-transformers embeddings without cloud APIs.
- Comprehensive test suite covering units, integration, storage, CLI commands, and MCP tools.
