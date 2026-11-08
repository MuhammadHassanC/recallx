# Example: End-to-end RecallX CLI Workflow (PowerShell)
# Demonstrates initializing, recording architectural decisions, searching with BM25,
# managing project context, exporting, and backups.

$ErrorActionPreference = "Stop"

Write-Host "=== RecallX End-to-End CLI Workflow ===" -ForegroundColor Cyan

# 1. Initialize RecallX
Write-Host "`n1. Initializing storage and database..." -ForegroundColor Yellow
python -m recallx.cli.app init

# 2. Check runtime status
Write-Host "`n2. Checking RecallX status..." -ForegroundColor Yellow
python -m recallx.cli.app status

# 3. Create a project workspace namespace
Write-Host "`n3. Registering project namespace 'fintech-core'..." -ForegroundColor Yellow
python -m recallx.cli.app project init fintech-core --name "FinTech Core Ledger" --description "High-precision double-entry bookkeeping ledger"

# 4. Save memories across categories
Write-Host "`n4. Recording memories across categories..." -ForegroundColor Yellow

# Architectural Decision
python -m recallx.cli.app remember "Using Decimal(128) arithmetic with fixed-point scale of 4 for all currency balances to prevent IEEE 754 float rounding inaccuracies." -p fintech-core -t decision --tags ledger,currency,math -i 0.95

# Bug Solution
python -m recallx.cli.app remember "Deadlock during concurrent account rebalancing resolved by strictly sorting account IDs in ascending order before acquiring row-level SELECT FOR UPDATE locks." -p fintech-core -t bug_solution --tags deadlock,postgres,concurrency -i 0.9

# Developer Preference
python -m recallx.cli.app remember "All ledger database migrations must be backwards-compatible (expand-and-contract pattern). Never rename or drop columns in a single deploy wave." -p fintech-core -t preference --tags migrations,deployment -i 0.8

# 5. Search memories
Write-Host "`n5. Searching for 'deadlock concurrency'..." -ForegroundColor Yellow
python -m recallx.cli.app search "deadlock concurrency" -p fintech-core

# 6. Retrieve structured project context
Write-Host "`n6. Compiling structured project context..." -ForegroundColor Yellow
python -m recallx.cli.app project context fintech-core

# 7. List registered projects
Write-Host "`n7. Listing project namespaces..." -ForegroundColor Yellow
python -m recallx.cli.app project list

# 8. Export project memories to JSON
Write-Host "`n8. Exporting memories to backup JSON..." -ForegroundColor Yellow
python -m recallx.cli.app export -p fintech-core -o fintech_backup.json
Write-Host "Export completed to fintech_backup.json" -ForegroundColor Green

# 9. Clean up temporary backup file
if (Test-Path fintech_backup.json) {
    Remove-Item fintech_backup.json -Force
}

Write-Host "`n[✓] Workflow demonstration completed successfully!" -ForegroundColor Green
