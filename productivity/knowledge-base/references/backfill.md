# Backfill Procedure

Retroactively archive raw sources for notes created before MinIO archiving was mandatory.

## Phase 0 — Identify gaps

```python
import os, re

for root, dirs, files in os.walk('Knowledge base/'):
    for f in files:
        if not f.endswith('.md'):
            continue
        with open(os.path.join(root, f)) as fh:
            content = fh.read()
        
        has_url = bool(re.search(r'^source_url:', content, re.MULTILINE))
        has_minio = bool(re.search(r'^minio:', content, re.MULTILINE))
        has_sourcefiles = bool(re.search(r'^source_files:', content, re.MULTILINE))
        
        if has_url and not has_minio and not has_sourcefile:
            # TRUE gap — needs backfill
            pass
        elif has_sourcefile and not has_minio:
            # Already archived — just standardize to source_files:
            pass
```

## Phase 1 — Categorize by content type

| URL pattern | Content type | Archive to | Method |
|---|---|---|---|
| `instagram.com/reel/` | Video | `knowledge-base/reels/` | yt-dlp + cookies |
| `instagram.com/p/` | Image/carousel | `knowledge-base/articles/` | cookies + OCR |
| `threads.com` / `threads.net` | Text ± video | `knowledge-base/threads/` | Firecrawl JS |
| `substack.com` | Text | `knowledge-base/articles/` | Firecrawl |
| `youtube.com` / `youtu.be` | Video | `knowledge-base/videos/` | yt-dlp |
| Books (old `source_file:`/`minio:`) | Already archived | — | Standardize to `source_files:` |
| Other web | Text | `knowledge-base/articles/` | Firecrawl |

## Phase 2 — Process by type

### Books (easiest — content already on MinIO)

These notes have old `source_file:` or `minio:` fields with MinIO URLs. Content is already uploaded. Just standardize the field:

```python
# Replace source_file: or minio: with source_files:
old = 'minio: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/foo.epub'
new = 'minio: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/books/foo.epub'
```

Atomic git commit per note.

### Text (Substack, web)

```bash
URL="<source_url>"
SLUG="<note-slug>"

# Firecrawl extraction
curl -s --max-time 60 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$URL\",\"formats\":[\"markdown\"],\"waitFor\":3000}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['markdown'])" \
  > "/tmp/${SLUG}_raw.md"

# Validate (>500 chars, not 404)
CHARS=$(wc -c < "/tmp/${SLUG}_raw.md")
if [ "$CHARS" -lt 500 ]; then
    echo "SKIP: content too short or 404"
    exit 0
fi

# Upload and add minio: field
mc cp "/tmp/${SLUG}_raw.md" "minio/knowledge-base/articles/${SLUG}.md"
# Patch note frontmatter to add minio: field
```

### Instagram Reels

Requires valid cookies (`sessionid`). Download video via yt-dlp, upload to `knowledge-base/reels/`. No diarization/transcription for backfill unless transcript already exists in vault.

### Instagram Posts

Requires valid cookies. Download image(s), OCR, upload images + OCR text to `knowledge-base/articles/`.

## Phase 3 — Atomic commits

One git commit per note:
```bash
cd "$OBSIDIAN_VAULT_PATH"
git add "Knowledge base/${SLUG}.md"
git commit -m "backfill: minio archive for ${SLUG}"
git push
```

## Phase 4 — Idempotency

- Dead URLs (404, domain expired) → skip, log to `skipped_backfill.txt`
- Already archived (minio: present) → skip
- Firecrawl down → skip, retry next run
- Cookie failures (Instagram/Threads) → skip, log to `skipped_<platform>.txt`
