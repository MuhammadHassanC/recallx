# Security Policy

RecallX is local-first persistent memory software designed for developer workstations and local coding agent workflows. Security and privacy are primary engineering priorities.

---

## Supported Versions

Security updates and patches are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | Yes                |
| < 1.0   | No                 |

Users are encouraged to run the latest patch release of RecallX.

---

## Reporting a Vulnerability

We take security issues seriously. If you discover a vulnerability or potential security risk in RecallX, please follow our coordinated disclosure process:

1. **Do not create a public GitHub issue.**
2. Send an email to the project maintainer:
   - **Contact**: Muhammad Hassan
   - **Email**: `muhammadhassanchanna8@gmail.com`
   - **Subject**: `[SECURITY VULNERABILITY] RecallX - <Brief Description>`
3. Include the following details in your report:
   - Affected version(s) of RecallX
   - Operating system and Python environment
   - Step-by-step reproduction instructions or proof-of-concept script
   - Assessment of impact, severity, and affected components
4. **Response Timeline**:
   - Initial acknowledgement: within 48 hours
   - Triage and impact assessment: within 5 business days
   - Release of fix / advisory: coordinated with reporter

---

## Security Model

RecallX is built with a strictly local-first security architecture:

1. **Zero External Network Calls**
   - RecallX does not phone home, report metrics, or transmit telemetry.
   - Core search and persistence utilize local SQLite databases and native Python components.
   - Optional semantic search runs entirely locally using quantized open embedding models cached on local disk. No third-party API keys are required or sent over network sockets.

2. **Automated Secret Detection and Redaction**
   - Incoming memory content is scanned for high-entropy secrets and credential patterns before storage.
   - Built-in patterns match AWS keys, GitHub Personal Access Tokens, OAuth credentials, Slack tokens, private keys, database connection strings with embedded passwords, and generic API keys.
   - Matching secrets are replaced with `[REDACTED]` tokens or safely sanitized prior to persistence.

3. **Strict Process Isolation via MCP**
   - RecallX operates as an MCP server communicating over standard input and output (`stdio`).
   - It does not expose listening network ports or unauthenticated HTTP/WebSocket interfaces by default.

4. **Input Sanitization and Database Safety**
   - All database interactions use parameterized SQL statements via SQLAlchemy or parameterized SQLite bindings.
   - FTS5 query inputs are sanitized to prevent query injection and malformed MATCH syntax errors.
   - Input strings are normalized to NFC unicode and stripped of illegal ASCII/Unicode control characters and null bytes.

---

## Threat Model and Protection Scope

### What RecallX Protects Against

- **Accidental Credential Leakage in Agent Memory**: Preventing AI agents from persisting sensitive tokens, keys, and passwords into long-term memory logs.
- **Project Context Contamination**: Memory operations are scoped by `project_id`, preventing cross-project memory leakage and prompt contamination across unrelated codebases.
- **Third-Party Data Exfiltration via RecallX**: Eliminating vendor exposure risks by refusing cloud synchronizations and telemetry channels.
- **SQL / Query Injection in Local Store**: Full parameterization of search terms and database queries.

### What RecallX Does NOT Protect Against (Out of Scope)

RecallX operates within the privileges of the local user account running the process. It does not defend against:

1. **Compromised Host Environment**:
   - If the local operating system or user account is compromised by malware, keyloggers, or malicious processes, an attacker can access the SQLite database file directly on disk.
2. **Physical Access to Unencrypted Disks**:
   - RecallX does not provide application-level database encryption at rest. If storage at rest encryption is required, utilize operating system-level encryption (e.g., BitLocker on Windows, LUKS on Linux, FileVault on macOS).
3. **Malicious MCP Clients or Compromised Agents**:
   - RecallX executes commands requested by the connected MCP client. If the calling AI agent is instructed by malicious prompt injection to retrieve or delete memories, RecallX performs the authorized tool call within the user's local store.
4. **Novel or Obfuscated Secret Formats**:
   - Secret redaction relies on deterministic heuristics and regular expressions. Novel proprietary tokens, base64-encoded secrets inside custom envelopes, or split secrets may not match known patterns. Users should maintain hygiene when feeding raw console logs to agents.

---

## Security Best Practices for Users

- Keep the RecallX database directory (`%LOCALAPPDATA%\RecallX` on Windows, `~/.local/share/recallx` on Linux) restricted to your personal user account.
- When configuring agent MCP settings, use absolute paths to your virtual environment's `recallx` executable to avoid PATH interception.
- Regularly review and clean sensitive project memories using `recallx search` and `recallx delete`.
- Use operating system disk encryption on laptops and workstations carrying production code repositories.
