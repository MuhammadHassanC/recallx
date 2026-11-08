## Description

Briefly describe the intent and impact of this pull request. Explain what bug was fixed or what feature was added.

Related Issue: Closes #(issue)

---

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Performance optimization / Refactoring
- [ ] Documentation update
- [ ] Test suite enhancement

---

## Key Changes and Design Decisions

- Bullet list of changes made
- Note any specific architectural decisions or tradeoffs

---

## Verification and Testing

Describe the tests executed to verify your changes:

- [ ] Added or updated unit/integration tests in `tests/`
- [ ] Verified tests pass locally: `pytest`
- [ ] Verified lint and formatting: `ruff check .` and `ruff format --check .`
- [ ] Verified static types: `mypy src`
- [ ] Tested manually via CLI or MCP client

---

## Checklist

- [ ] My code adheres to the project's PEP 8 coding standards and type annotations.
- [ ] I have commented my code, particularly in complex or algorithmic areas.
- [ ] I have made corresponding changes to the documentation (if applicable).
- [ ] My changes introduce no new external cloud dependencies or telemetry calls.
- [ ] Secrets and credentials are not logged or stored without redaction.
- [ ] All new and existing tests pass.
