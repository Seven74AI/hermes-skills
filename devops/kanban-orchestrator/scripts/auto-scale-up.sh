#!/bin/bash
# Auto-scale-up: poll all Kanban boards and clone profiles when
# ready tasks pile up for a role. Run via cron every 5 minutes.
#
# Rules:
#   - Clone when ready_tasks > profiles * 2
#   - Cap at 2 profiles per role (OOM constraint)
#   - Never clone base profiles (they have no -N suffix and are templates)
#
# Profile naming convention: <role> or <project>-<role>
# Clones: <role>-<N> or <project>-<role>-<N> where N >= 2

set -euo pipefail

MAX_PROFILES=2  # Hard cap: OOM on memory-constrained hosts
THRESHOLD_MULTIPLIER=2

# Get all tenant names from kanban boards
TENANTS=$(hermes kanban boards list 2>/dev/null | grep -oP '^\s*\S+' | tail -n +2 || true)
if [ -z "$TENANTS" ]; then
  echo "No kanban boards found."
  exit 0
fi

for TENANT in $TENANTS; do
  # Get all unique assignees with ready tasks
  READY_ASSIGNEES=$(hermes kanban list --tenant "$TENANT" 2>/dev/null | grep "ready" | awk '{print $4}' | sort -u || true)
  if [ -z "$READY_ASSIGNEES" ]; then
    continue
  fi

  for ASSIGNEE in $READY_ASSIGNEES; do
    # Extract the role: strip numeric suffix and project prefix
    # "music-coder-3" → "music-coder" (base)
    # "coder-2" → "coder" (base)
    BASE=$(echo "$ASSIGNEE" | sed -E 's/-[0-9]+$//')
    
    # Count ready tasks for this role family (any profile matching base*)
    READY_COUNT=$(hermes kanban list --tenant "$TENANT" 2>/dev/null | grep "ready" | awk '{print $4}' | grep -c "^${BASE}" || echo 0)
    
    # Count existing profiles for this role family
    PROFILE_COUNT=$(hermes profile list 2>/dev/null | grep -oP "^\s*\S+" | grep -c "^${BASE}" || echo 0)
    
    NEEDED=$((PROFILE_COUNT * THRESHOLD_MULTIPLIER))
    
    if [ "$READY_COUNT" -gt "$NEEDED" ] && [ "$PROFILE_COUNT" -lt "$MAX_PROFILES" ]; then
      NEXT=$((PROFILE_COUNT + 1))
      NEW_PROFILE="${BASE}-${NEXT}"
      
      # Only clone if the target doesn't already exist (safety check)
      if ! hermes profile list 2>/dev/null | grep -q "^  ${NEW_PROFILE} "; then
        echo "[${TENANT}] Cloning ${BASE} → ${NEW_PROFILE} (${READY_COUNT} ready, ${PROFILE_COUNT} profiles)"
        hermes profile create "$NEW_PROFILE" --clone-from "$BASE" 2>&1 || echo "  Failed to create ${NEW_PROFILE}"
      fi
    fi
  done
done

echo "Auto-scale-up check complete."
