#!/bin/bash
# Sync ALL productivity skills to ALL worker profiles
# Run after any skill file change (references, templates, scripts, SKILL.md)
set -e
SKILLS_SRC="/root/.hermes/skills/productivity"
PROFILES_DIR="/root/.hermes/profiles"

echo "=== Syncing productivity skills to all profiles ==="
for skill_dir in "$SKILLS_SRC"/*/; do
  skill_name=$(basename "$skill_dir")
  # Skip DESCRIPTION.md (not a skill dir)
  [ "$skill_name" = "DESCRIPTION.md" ] && continue
  
  for profile_dir in "$PROFILES_DIR"/*/; do
    profile_name=$(basename "$profile_dir")
    dst="$profile_dir/skills/productivity/$skill_name"
    if [ -d "$dst" ]; then
      rsync -a --delete "$skill_dir/" "$dst/"
      echo "  $skill_name -> $profile_name: OK"
    fi
  done
done
echo "=== Done ==="
