# MinIO Integrity Checks

Verify that files referenced in notes actually exist in MinIO. Broken references
happen when workers upload wrong formats (`.srt` instead of `.json`) or skip uploads.

## Check a single note

```bash
# Extract minio:// references from frontmatter, verify each
grep -oP 'minio://\S+' "Knowledge base/<slug>.md" | while read ref; do
  path=$(echo "$ref" | sed 's|minio://|minio/|')
  if mc ls "$path" >/dev/null 2>&1; then
    echo "OK: $ref"
  else
    echo "MISSING: $ref"
  fi
done
```

## Batch-check recent notes

```bash
cd "$OBSIDIAN_VAULT_PATH"
# Notes from last 24h
git log --oneline --since="24 hours ago" -- "Knowledge base/" |
  while read hash msg; do
    git diff-tree --no-commit-id --name-only -r "$hash" -- "Knowledge base/"
  done | sort -u | while read note; do
    echo "=== $note ==="
    grep -oP '(source_file|transcript_file):\s*minio://\S+' "$note" |
      while read line; do
        path=$(echo "$line" | sed 's|.*minio://|minio/|')
        mc ls "$path" >/dev/null 2>&1 && echo "  OK: $path" || echo "  MISSING: $path"
      done
  done
```

## Check transcript format

Old transcripts may be `.srt` instead of `.json`. Detect format mismatches:

```bash
# If note references .json but MinIO has .srt instead
slug="<slug>"
if mc ls "minio/knowledge-base/transcripts/$slug.json" 2>&1 | grep -q "does not exist"; then
  if mc ls "minio/knowledge-base/videos/$slug.srt" >/dev/null 2>&1; then
    echo "FORMAT MISMATCH: note refs .json, MinIO has .srt"
  fi
fi
```

## Check diarization

Verify transcripts have speaker labels (not just `?`):

```bash
mc cat "minio/knowledge-base/transcripts/<slug>.json" |
  python3 -c "
import json, sys
d = json.load(sys.stdin)
speakers = set(s.get('speaker', '?') for s in d.get('segments', []))
if speakers == {'?'}:
    print('NOT DIARIZED')
else:
    print(f'{len(speakers)} speakers: {speakers}')
"
```

## Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `.json` referenced but `.srt` exists | Old worker used SRT format | Re-upload as JSON or create note with SRT reference |
| `.json` missing entirely | Upload step skipped | Re-run upload from local temp files |
| `.mp4` missing | Video was downloaded to /tmp and cleaned up before upload | Re-download from source URL |
| All speakers = `?` | Diarization was skipped (old "single-speaker" exception) | Re-run with mandatory diarization pipeline |
