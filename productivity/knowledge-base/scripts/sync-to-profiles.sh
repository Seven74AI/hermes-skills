#!/bin/bash
# Sync knowledge-base skills to all worker profiles
# Run after any skill file change (references, templates, scripts, SKILL.md)
set -e
SRC="/root/.hermes/skills/productivity/knowledge-base"
for p in researcher researcher-videos; do
  DST="/root/.hermes/profiles/$p/skills/productivity/knowledge-base"
  if [ -d "$DST" ]; then
    rsync -a --delete "$SRC/" "$DST/"
    echo "$p: OK"
  fi
done
# Also sync to any other profiles that have the skill
for p in /root/.hermes/profiles/*/; do
  name=$(basename "$p")
  DST="$p/skills/productivity/knowledge-base"
  if [ -d "$DST" ] && [ "$name" != "researcher" ] && [ "$name" != "researcher-videos" ]; then
    rsync -a --delete "$SRC/" "$DST/"
    echo "$name: OK"
  fi
done
