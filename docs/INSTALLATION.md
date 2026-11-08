# Installation Guide

RecallX is distributed as a standard Python package. It requires **Python 3.10 or higher** and runs on Windows, Linux, and macOS.

---

## Installation Methods

### Option 1: Standard Installation via pip

Install the latest stable release into your current Python environment:

```bash
pip install recallx
```

### Option 2: Isolated Global CLI Installation via pipx (Recommended for CLI)

If you primarily use RecallX via the command-line interface or wish to isolate its dependencies from other Python projects:

```bash
pipx install recallx
```

To update RecallX later via pipx:
```bash
pipx upgrade recallx
```

### Option 3: Installation with Optional Semantic Search

Standard RecallX uses SQLite FTS5 for fast, lightweight full-text search without heavy dependencies. To enable local dense vector embeddings using `sentence-transformers`:

```bash
pip install "recallx[semantic]"
```

Or via pipx:
```bash
pipx install "recallx[semantic]"
```

*Note: The semantic search extra downloads local PyTorch and Hugging Face sentence transformers dependencies (~90MB model cached upon first use).*

---

## Platform-Specific Instructions

### Windows

#### Prerequisites
- Python 3.10+ installed from [python.org](https://www.python.org/) or Microsoft Store.
- Ensure **"Add Python to PATH"** was checked during Python installation.

#### Installation Steps
Open PowerShell or Windows Terminal:

```powershell
# Verify Python version
python --version

# Install RecallX
pip install recallx

# Initialize storage and default configuration
recallx init

# Verify status
recallx status
```

#### Default Storage Locations on Windows
- **Data & SQLite Database**: `%LOCALAPPDATA%\RecallX\recallx.db`  
  (Typically `C:\Users\<Username>\AppData\Local\RecallX\recallx.db`)
- **Configuration**: `%APPDATA%\RecallX\config.toml`  
  (Typically `C:\Users\<Username>\AppData\Roaming\RecallX\config.toml`)

---

### macOS

#### Prerequisites
- macOS 12 (Monterey) or newer (Apple Silicon M1/M2/M3 or Intel).
- Python 3.10+ installed via Homebrew (`brew install python`) or standard installer.

#### Installation Steps
Open Terminal:

```bash
# Verify Python 3
python3 --version

# Install RecallX
python3 -m pip install --user recallx

# Initialize storage
recallx init

# Verify status
recallx status
```

#### Default Storage Locations on macOS
- **Data & SQLite Database**: `~/Library/Application Support/RecallX/recallx.db`
- **Configuration**: `~/Library/Application Support/RecallX/config.toml`

---

### Linux

#### Prerequisites
- Any modern Linux distribution (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch Linux).
- Python 3.10+ and standard development packages.

#### Installation on Debian / Ubuntu
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# Recommended: use virtual environment or pipx
pip3 install --user recallx

# Initialize RecallX
recallx init

# Verify installation
recallx status
```

#### Default Storage Locations on Linux
RecallX adheres to the **XDG Base Directory Specification**:
- **Data & SQLite Database**: `$XDG_DATA_HOME/recallx/recallx.db` (defaults to `~/.local/share/recallx/recallx.db`)
- **Configuration**: `$XDG_CONFIG_HOME/recallx/config.toml` (defaults to `~/.config/recallx/config.toml`)

---

## Development Installation (From Source)

To build and run RecallX from source code for development:

```bash
# 1. Clone repository
git clone https://github.com/MuhammadHassanC/RecallX.git
cd RecallX

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Linux / macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# 4. Install editable package with dev dependencies
pip install --upgrade pip
pip install -e ".[dev]"

# 5. Run test suite to verify
pytest
```

---

## Verification Steps

Once installed, execute the following commands to confirm your installation:

1. **Verify CLI binary availability**:
   ```bash
   recallx --help
   ```

2. **Initialize storage**:
   ```bash
   recallx init
   ```

3. **Check operational status**:
   ```bash
   recallx status
   ```

4. **Persist a test memory**:
   ```bash
   recallx remember "Test verification memory" -p test-suite -t project --tags verify
   ```

5. **Search test memory**:
   ```bash
   recallx search "verification" -p test-suite
   ```

6. **Clean up test memory**:
   ```bash
   recallx delete <id-from-search-output>
   ```

---

## Troubleshooting

### Command not found: `recallx`
- **Cause**: Python's user script directory is not present in your system `PATH`.
- **Solution**:
  - Windows: Add `%APPDATA%\Python\Python3xx\Scripts` or `%LOCALAPPDATA%\Programs\Python\Python3xx\Scripts` to your system Environment Variables.
  - Linux/macOS: Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc` or `~/.zshrc`.
  - Alternative: Run the module directly via `python -m recallx.cli.app --help`.

### SQLite FTS5 Module Missing
- **Cause**: Rare custom or minimal Python binaries compiled without SQLite FTS5 extension.
- **Solution**: RecallX requires SQLite compiled with FTS5 enabled (standard on official Python releases and Homebrew distributions). Check support with:
  ```bash
  python -c "import sqlite3; con = sqlite3.connect(':memory:'); con.execute('CREATE VIRTUAL TABLE t USING fts5(x);'); print('FTS5 is enabled')"
  ```
  If this errors, reinstall Python from the official python.org distribution or your OS package manager.

### Semantic Search Import Errors
- **Cause**: `recallx[semantic]` was not installed, but `enable_semantic_search = true` is configured in `config.toml`.
- **Solution**: Install the semantic search dependencies:
  ```bash
  pip install "recallx[semantic]"
  ```
