#!/bin/bash
# push-digest.sh — commit a digest JSON file to the twitter-digest repo
# Usage: push-digest.sh <json_file> <digest_type> <date>
#   json_file: path to the digest JSON (e.g. /tmp/2026-05-18-dev-ai.json)
#   digest_type: "dev-ai" or "crypto"  
#   date: YYYY-MM-DD

set -e
JSON_FILE="$1"
TYPE="$2"
DATE="$3"
REPO_DIR="/tmp/twitter-digest-data"
INDEX="$REPO_DIR/data/index.json"

# Source env for GITHUB_TOKEN
source ~/.hermes/.env 2>/dev/null || true

# Clone if not exists
if [ ! -d "$REPO_DIR/.git" ]; then
  rm -rf "$REPO_DIR"
  git clone "https://${GITHUB_TOKEN}@github.com/Seven74AI/twitter-digest.git" "$REPO_DIR" 2>/dev/null
fi

cd "$REPO_DIR"
git pull origin master 2>/dev/null || true

# Copy JSON
FILENAME="${DATE}-${TYPE}.json"
cp "$JSON_FILE" "data/$FILENAME"

# Update index.json
python3 -c "
import json
files = sorted(set(json.load(open('$INDEX')) + ['$FILENAME']), reverse=True)
json.dump(files, open('$INDEX','w'), indent=2)
"

# Commit and push
git add "data/$FILENAME" data/index.json
git commit -m "digest: $TYPE $DATE" 2>/dev/null || true
git push origin master 2>/dev/null || true

rm -f "$JSON_FILE"
echo "Pushed: $FILENAME"
