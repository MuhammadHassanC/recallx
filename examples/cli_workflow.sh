#!/usr/bin/env bash
# Example: End-to-end RecallX CLI Workflow (Bash)
# Demonstrates initializing, recording architectural decisions, searching with BM25,
# managing project context, exporting, and backups.

set -euo pipefail

echo "=== RecallX End-to-End CLI Workflow ==="

# 1. Initialize RecallX
echo -e "\n1. Initializing storage and database..."
recallx init

# 2. Check runtime status
echo -e "\n2. Checking RecallX status..."
recallx status

# 3. Create a project workspace namespace
echo -e "\n3. Registering project namespace 'fintech-core'..."
recallx project init fintech-core --name "FinTech Core Ledger" --description "High-precision double-entry bookkeeping ledger"

# 4. Save memories across categories
echo -e "\n4. Recording memories across categories..."

# Architectural Decision
recallx remember "Using Decimal(128) arithmetic with fixed-point scale of 4 for all currency balances to prevent IEEE 754 float rounding inaccuracies." -p fintech-core -t decision --tags ledger,currency,math -i 0.95

# Bug Solution
recallx remember "Deadlock during concurrent account rebalancing resolved by strictly sorting account IDs in ascending order before acquiring row-level SELECT FOR UPDATE locks." -p fintech-core -t bug_solution --tags deadlock,postgres,concurrency -i 0.9

# Developer Preference
recallx remember "All ledger database migrations must be backwards-compatible (expand-and-contract pattern). Never rename or drop columns in a single deploy wave." -p fintech-core -t preference --tags migrations,deployment -i 0.8

# 5. Search memories
echo -e "\n5. Searching for 'deadlock concurrency'..."
recallx search "deadlock concurrency" -p fintech-core

# 6. Retrieve structured project context
echo -e "\n6. Compiling structured project context..."
recallx project context fintech-core

# 7. List registered projects
echo -e "\n7. Listing project namespaces..."
recallx project list

# 8. Export project memories to JSON
echo -e "\n8. Exporting memories to backup JSON..."
recallx export -p fintech-core -o fintech_backup.json
echo "Export completed to fintech_backup.json"

# 9. Clean up temporary backup file
rm -f fintech_backup.json

echo -e "\n[✓] Workflow demonstration completed successfully!"

