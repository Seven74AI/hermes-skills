#!/usr/bin/env bash
# Sync all dogfood project skills from the main profile to worker profiles.
# Run this after creating a new dogfood skill or after any profile cleanup.
#
# Usage: bash sync-dogfood-skills.sh [--dry-run]

set -euo pipefail

MAIN_SKILLS="/root/.hermes/skills/dogfood"
PROFILES=("coder" "reviewer" "planner" "researcher" "hermes-devops")
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

for ds in "$MAIN_SKILLS"/*/; do
    skill_name=$(basename "$ds")
    for profile in "${PROFILES[@]}"; do
        dst="/root/.hermes/profiles/$profile/skills/dogfood/$skill_name"
        if [[ -d "$dst" ]]; then
            continue  # already present
        fi
        if $DRY_RUN; then
            echo "[DRY-RUN] Would sync: $skill_name → $profile"
        else
            mkdir -p "$(dirname "$dst")"
            cp -r "$ds" "$dst"
            echo "Synced: $skill_name → $profile"
        fi
    done
done

echo "Done."
