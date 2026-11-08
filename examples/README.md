# RecallX Examples

This directory contains executable reference scripts and sample data demonstrating how to use RecallX programmatically, via MCP, and through the command line.

---

## Directory Contents

| File | Description | Language / Format |
|------|-------------|-------------------|
| [`python_sdk_usage.py`](python_sdk_usage.py) | Complete Python script demonstrating direct programmatic usage: initializing the database, creating memories across categories, full-text searching, ranking, and compiling structured project context. | Python 3.10+ |
| [`mcp_client_example.py`](mcp_client_example.py) | Example showing how an external Python client or agent interacts with the RecallX FastMCP server over standard input/output (`stdio`). | Python 3.10+ / Asyncio |
| [`sample_memories.json`](sample_memories.json) | Production-realistic sample memory dataset covering all 5 memory types (`project`, `decision`, `bug_solution`, `preference`, `session`) that can be imported immediately with `recallx import-memories`. | JSON |
| [`cli_workflow.ps1`](cli_workflow.ps1) | PowerShell script executing an end-to-end lifecycle workflow on Windows: initialization, project namespace setup, memory creation, search, context generation, and export. | PowerShell |
| [`cli_workflow.sh`](cli_workflow.sh) | Bash script executing the identical end-to-end lifecycle workflow for Linux and macOS environments. | Bash |

---

## Running the Examples

### 1. Python SDK Usage
```bash
python examples/python_sdk_usage.py
```

### 2. Import Sample Memories
Import the curated dataset into a project namespace:
```bash
recallx import-memories examples/sample_memories.json -p cloud-saas
```
Then inspect the imported context:
```bash
recallx project context cloud-saas
recallx search "rate limiting redis" -p cloud-saas
```

### 3. Run the CLI Lifecycle Workflow
**Windows (PowerShell):**
```powershell
.\examples\cli_workflow.ps1
```

**Linux / macOS (Bash):**
```bash
chmod +x ./examples/cli_workflow.sh
./examples/cli_workflow.sh
```

### 4. Test MCP Server Stdio Connection
```bash
python examples/mcp_client_example.py
```

