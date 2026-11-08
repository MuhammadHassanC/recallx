# Security and Privacy Architecture

RecallX is designed from the ground up with a local-first, zero-trust mindset for developer workstations. AI coding agents frequently inspect raw logs, stack traces, and configurations that may contain sensitive credentials; RecallX ensures this data is protected before it is ever stored to disk.

---

## Core Security Principles

1. **Local-First and Offline-First**:
   - All memory persistence, indexing, and retrieval executes on the local host machine.
   - Zero telemetry, zero analytics, zero external network requests.
   - Works fully in air-gapped and disconnected environments.

2. **Automated Credential Redaction**:
   - Every memory payload submitted via MCP or CLI is automatically scanned for high-entropy secrets and credential patterns prior to database insertion.
   - Detected secrets are replaced with `[REDACTED]` placeholders.

3. **Project Isolation**:
   - Memories are strictly partitioned by `project_id`.
   - AI agents querying memory for Project A cannot accidentally retrieve or leak architectural context from Project B.

4. **Input Sanitization**:
   - Memory inputs undergo character normalization and sanitization to prevent terminal injection, null byte corruption, or database exploits.

---

## Secret Detection and Redaction Engine

The secret detection engine (`recallx.utils.validation`) executes high-performance regular expression scanning against memory text.

### Default Credential Patterns

| Secret Classification | Pattern Description / Matched Format |
|---|---|
| **AWS Access Key ID** | `\bAKIA[0-9A-Z]{16}\b` |
| **AWS Secret Access Key** | Assignments matching `aws_secret_access_key` or `aws_secret_key` |
| **GitHub Classic Token** | `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` followed by base62 characters |
| **GitHub Fine-Grained PAT** | `github_pat_` followed by 82 base62 characters |
| **OpenAI / Anthropic Keys** | `sk-` / `sk-ant-` / `sk-proj-` followed by high-entropy keys |
| **Stripe Secret / Restricted Key** | `sk_live_`, `sk_test_`, `rk_live_`, `rk_test_` keys |
| **Slack API Token** | `xoxb-`, `xoxa-`, `xoxp-`, `xoxr-`, `xoxs-` tokens |
| **Private Cryptographic Keys** | RSA, EC, OPENSSH, DSA, and PGP private key blocks |
| **JSON Web Tokens (JWT)** | Standard three-part base64url encoded tokens (`eyJ...`) |
| **Database URLs with Passwords** | URI schemes (`postgres://user:password@host`) |
| **Generic API Secret Assignments** | Key-value pairs for `api_key`, `secret_key`, `auth_token`, `bearer_token` |

### Custom Secret Patterns

Users can register custom proprietary token formats by specifying regular expressions in `config.toml` or via the `RECALLX_SECRET_PATTERNS` environment variable:

```toml
# In config.toml
secret_patterns = [
    "corp_token_[a-f0-9]{32}",
    "internal_oauth_key_[A-Za-z0-9_]{40}"
]
```

---

## Input Sanitization and Normalization

Before storage, raw text is sanitized using `sanitize_for_storage()`:

1. **Null Byte Stripping**:
   - Null bytes (`\x00`) are removed to prevent C-string termination attacks or database engine discrepancies.

2. **Unicode NFC Normalization**:
   - All text is converted to Unicode Standard Normalization Form C (NFC). This prevents homoglyph confusion and duplicate visual representations.

3. **Control Character Filtering**:
   - ASCII and Unicode control characters (category `C*`) are removed, while safe whitespace (newlines `\n`, carriage returns `\r`, and tabs `\t`) is preserved.

4. **Constraint Enforcement**:
   - Maximum content length: 50,000 characters.
   - Maximum project ID length: 128 characters (strict `^[a-zA-Z0-9_\-]+$` regex).
   - Maximum tag count: 20 tags per memory.
   - Maximum tag length: 50 characters (strict `^[a-zA-Z0-9_\-]+$` regex).

---

## Threat Model and Security Boundaries

### Protected Against
- **Agent Memory Leakage**: Prevents AI agents from saving credentials into persistent memory.
- **Cross-Project Contamination**: Enforces project boundaries so queries in one repository do not leak facts into another.
- **Data Exfiltration by Memory Layer**: Guarantees no outbound network connections.
- **FTS5 / SQL Injection**: All queries use parameterized queries and sanitized search terms.

### Not Protected Against (Out of Scope)
- **Local Host Compromise**: If an attacker has user-level shell access or malware on the developer machine, they can read the SQLite file directly from the filesystem.
- **Disk Theft without OS Encryption**: RecallX stores data in SQLite files on local disk without proprietary at-rest encryption. Users should enable OS-level disk encryption (BitLocker, FileVault, LUKS).
- **Adversarial Obfuscation**: Base64-encoded, ciphered, or split credentials may not trigger heuristic regex matchers.

---

## Defense-in-Depth Recommendations

1. **Restrict Storage Permissions**:
   Ensure only your user account has read/write permissions to the RecallX data folder (`chmod 700 ~/.local/share/recallx` on Linux/macOS).
2. **Enable Disk Encryption**:
   Ensure whole-disk encryption is active on all developer laptops.
3. **Audit Memories Periodically**:
   Run `recallx search "key"` or `recallx search "token"` periodically to ensure no project credentials slipped through regex detection.
