#!/usr/bin/env bash
# Chrysalis multi-agent test and analysis pipeline.
# Spawns test-runner and simulation-agent in parallel, then runs
# fact-checker → analysis-agent → fix-agent sequentially per CLAUDE.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
mkdir -p reports

echo "=== Chrysalis pipeline starting ==="
echo "Project root: $PROJECT_ROOT"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo ""

claude --agents "run the full Chrysalis test and analysis pipeline per CLAUDE.md"
