#!/bin/bash
# Sync all productivity skills to all worker profiles that have a skills/productivity/ directory.
# Run after editing any SKILL.md, reference, template, or script.
# Workers crash-loop with "Unknown skill(s)" when a ticket references a skill via --skill that hasn't been synced.

set -euo pipefail

SKILLS_DIR="/root/.hermes/skills/productivity"
PROFILES_DIR="/root/.hermes/profiles"

echo "=== Syncing productivity skills to all profiles ==="

for profile_dir in "$PROFILES_DIR"/*/; do
    profile=$(basename "$profile_dir")
    dest="$profile_dir/skills/productivity"
    if [ -d "$dest" ]; then
        for skill_dir in "$SKILLS_DIR"/*/; do
            skill_name=$(basename "$skill_dir")
            rsync -a --delete "$skill_dir" "$dest/$skill_name/" 2>/dev/null && echo "  $skill_name -> $profile: OK" || echo "  $skill_name -> $profile: FAIL"
        done
    fi
done

echo "=== Done ==="
