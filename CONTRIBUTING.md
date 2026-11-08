# Contributing to RecallX

Thank you for your interest in contributing to RecallX. RecallX is designed as a local-first, privacy-respecting persistent memory infrastructure for AI coding agents. We welcome contributions that maintain our high standards of software quality, safety, and performance.

---

## Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating in our issues, discussions, or pull requests.

---

## Prerequisites

Before setting up your development environment, ensure you have:

- **Python 3.10 or higher** (Python 3.10, 3.11, 3.12, or 3.13)
- **Git** installed and configured
- **Virtual environment tool** (`venv` or `virtualenv`)
- (Optional) **C compiler / build tools** if building optional dependencies from source

---

## Development Setup

1. **Fork and Clone the Repository**

   ```bash
   git clone https://github.com/MuhammadHassanC/RecallX.git
   cd RecallX
   ```

2. **Create and Activate a Virtual Environment**

   On Linux / macOS:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   On Windows (Command Prompt):
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate.bat
   ```

3. **Install Editable Package with Development Dependencies**

   ```bash
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   ```

   To install optional semantic search dependencies for local embeddings:
   ```bash
   pip install -e ".[dev,semantic]"
   ```

4. **Verify Installation**

   ```bash
   recallx --help
   pytest
   ```

---

## Quality Standards and Style Guidelines

RecallX follows strict engineering standards to ensure high reliability in developer environments.

### Code Style and Formatting

- **PEP 8 Compliance**: Follow standard Python conventions.
- **Ruff**: We use `ruff` for linting and code formatting. Maximum line length is set to 100 characters.
- **Type Annotations**: All public and internal functions, classes, and methods must include explicit type hints. `mypy` is run with `--strict` enforcement.
- **Docstrings**: Public APIs must contain Google-style or standard Sphinx docstrings specifying descriptions, arguments, returns, and raised exceptions.
- **Modern Python 3.10+ Features**: Use `from __future__ import annotations`, modern union syntax (`X | Y`), built-in generic collections (`list[str]`, `dict[str, Any]`), and dataclasses or Pydantic models for structured data.
- **Zero Cloud / Telemetry**: Never introduce external telemetry, phone-home mechanisms, or hardcoded external network endpoints.

### Running Quality Checks

Run the following checks locally before opening a pull request:

1. **Linting and Format Checking**:
   ```bash
   ruff check .
   ruff format --check .
   ```

2. **Automatic Code Formatting**:
   ```bash
   ruff format .
   ruff check --fix .
   ```

3. **Type Checking**:
   ```bash
   mypy src
   ```

4. **Running Tests with Coverage**:
   ```bash
   pytest --cov=recallx --cov-report=term-missing
   ```

---

## Submitting Pull Requests

1. **Create a Dedicated Branch**
   Branch from `main` with a clear, descriptive name:
   ```bash
   git checkout -b feat/hybrid-search-refinement
   # or
   git checkout -b fix/secret-redaction-pattern
   ```

2. **Make Focused, Atomic Commits**
   - Keep commits focused on a single logical change.
   - Write informative, imperative commit messages (e.g., `Add FTS5 query token sanitizer`, `Fix SQLite connection lifecycle in MCP server`).

3. **Add Tests**
   - Every bug fix must include a regression test.
   - Every new feature must include comprehensive unit and integration tests.
   - Maintain or improve overall test coverage.

4. **Ensure All Checks Pass Locally**
   Ensure `ruff`, `mypy`, and `pytest` execute with zero failures before opening your pull request.

5. **Open a Pull Request**
   - Provide a clear description of the problem solved, design decisions, and verification steps.
   - Reference any relevant GitHub issues (`Closes #123`).
   - Use our pull request template.

---

## Reporting Issues and Bugs

### Reporting Bugs

Check the issue tracker first to see if the issue has already been reported. If not, open a new issue using our **Bug Report** template. Include:

- Operating system and Python version
- RecallX version (`recallx --version`)
- Clear reproduction steps
- Expected vs actual behavior
- Relevant error tracebacks (scrub any credentials or sensitive paths before posting)

### Proposing Enhancements

Feature requests and architectural proposals should be submitted using our **Feature Request** template. Describe:

- The problem or workflow limitation
- Proposed solution or API design
- Potential alternatives considered
- Impact on local performance, memory usage, and user experience

---

## Security Disclosures

Do not report security vulnerabilities through public GitHub issues. Please review our [Security Policy](SECURITY.md) for our coordinated disclosure process.
