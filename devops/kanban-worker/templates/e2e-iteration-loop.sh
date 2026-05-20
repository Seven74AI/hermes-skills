#!/usr/bin/env bash
# ============================================================================
# TEMPLATE: Self-contained iteration loop for kanban workers
# ============================================================================
# Use this when a kanban worker repeatedly burns iteration budget running
# tests/benchmarks inline. Put ALL the work in this script, call it ONCE
# in background mode with notify_on_complete=true.
#
# Copy to: <project>/scripts/<task-name>-loop.sh
# Worker calls: terminal("./scripts/<task-name>-loop.sh", background=true,
#                         timeout=7200, notify_on_complete=true, workdir="<project>")
# ============================================================================
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/path/to/project}"
LOG_FILE="$PROJECT_DIR/loop-$(date +%Y%m%d-%H%M%S).log"

cd "$PROJECT_DIR"
echo "=== Loop started: $(date) ===" | tee "$LOG_FILE"

# --- Phase 1: Baseline ---
echo "[1/3] Running baseline..." | tee -a "$LOG_FILE"
# ./scripts/benchmark.sh --runs 3 2>&1 | tee -a "$LOG_FILE"
echo "  Baseline: <result>" | tee -a "$LOG_FILE"

# --- Phase 2: Apply changes ---
echo "[2/3] Applying changes..." | tee -a "$LOG_FILE"
# sed -i 's/OLD/NEW/g' target-file
# find . -name "*.ext" -exec sed -i 's/OLD/NEW/g' {} \;
echo "  Changes applied" | tee -a "$LOG_FILE"

# --- Phase 3: Verify ---
echo "[3/3] Running verification..." | tee -a "$LOG_FILE"
# ./scripts/benchmark.sh --runs 3 2>&1 | tee -a "$LOG_FILE"
echo "  Optimized: <result>" | tee -a "$LOG_FILE"

# --- Report ---
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "RESULTS: <summary>" | tee -a "$LOG_FILE"
echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Completed: $(date)" | tee -a "$LOG_FILE"
