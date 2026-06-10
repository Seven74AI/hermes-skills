# Substack Pipeline

Substack articles (long-form newsletters) and Notes (short-form posts, may contain video). Text extraction via Firecrawl. Video hosted on Mux (Substack's CDN) — see "Substack Video Notes" section below.

## Phase -1 — Content-type detection (before ticket creation)

Substack Notes can embed video or image attachments. Detect before creating the ticket — this determines assignee and pipeline.

**Two detection layers** — the `"attachments"` JSON in preloads works for some Notes but not all. The SSR HTML fallback catches Notes where video data is loaded client-side.

```bash
HTML=$(curl -sL --max-time 15 "$URL")

# Layer 1: preloads JSON (fast, works for Notes with inline attachment metadata)
HAS_VIDEO=0
HAS_IMAGE=0

if echo "$HTML" | grep -q '"attachments":\[.*"type":"video"'; then
    HAS_VIDEO=1
    VIDEO_NAME=$(echo "$HTML" | grep -oP '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    DURATION=$(echo "$HTML" | grep -oP '"duration":\K[0-9.]+' | head -1)
    echo "VIDEO (preloads): $VIDEO_NAME (${DURATION}s)"
elif echo "$HTML" | grep -q '"attachments":\[.*"type":"image"'; then
    HAS_IMAGE=1
    IMG_URL=$(echo "$HTML" | grep -oP '"type":"image","imageUrl":"[^"]*"' | grep -oP 'https://[^"]+')
    echo "IMAGE (preloads): $IMG_URL"
fi

# Layer 2: SSR HTML fallback — catches Notes whose video data is loaded client-side
# The Substack video player always renders a <div aria-label="Video player"> in SSR HTML
if [ "$HAS_VIDEO" -eq 0 ] && echo "$HTML" | grep -q 'aria-label="Video player"'; then
    HAS_VIDEO=1
    # Count video elements for multi-video posts
    VIDEO_COUNT=$(echo "$HTML" | grep -o 'aria-label="Video player"' | wc -l)
    [ "$VIDEO_COUNT" -gt 1 ] && echo "VIDEO (SSR): ${VIDEO_COUNT} videos detected" || echo "VIDEO (SSR): 1 video detected"
fi

# Decision
if [ "$HAS_VIDEO" -eq 1 ]; then
    # → create ticket with --assignee researcher-videos (see below)
    # Multi-video: mention count in ticket body so worker processes ALL videos
    echo "→ assignee=researcher-videos"
elif [ "$HAS_IMAGE" -eq 1 ]; then
    # → create ticket with --assignee researcher, include image URL in body
    echo "→ assignee=researcher"
else
    echo "TEXT: no media attachment"
    # → create ticket with --assignee researcher (see below)
fi
```

## Prerequisites

- **Firecrawl** : `http://localhost:3002/v2/scrape`
- **Queue file** : `/root/.hermes/queues/skipped_substack.txt` — URLs queued when Firecrawl is down

## Planner (before ticket creation)

### Dedup check

```bash
if grep -rql "source_url: SUBSTACK_URL" "$OBSIDIAN_VAULT_PATH/Knowledge base/" 2>/dev/null; then
    echo "Already in vault — skip"
    exit 0
fi
```

### Firecrawl health check

```bash
curl -s --max-time 5 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"]}' > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "SUBSTACK_URL" >> /root/.hermes/queues/skipped_substack.txt
    exit 0
fi
```

### Create kanban ticket

For **text** (no video attachment):

```bash
hermes kanban --board default create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 600 \
  --body "Substack article — <publication>, <date>. Firecrawl extraction → markdown cleanup → Obsidian note.

1. <URL>

Langue: contenu en langue source, labels en anglais. Save to Knowledge base/. Push après la note." \
  "KB: <publication> — <title>"
```

For **video** (has video player):

```bash
hermes kanban --board default create \
  --assignee researcher-videos \
  --skill knowledge-base \
  --max-runtime 3600 \
  --body "Substack Note WITH VIDEO (<N> video(s)) — <publication> (<author>), <date>.

Download ALL videos via Substack API (see 'Substack Video Notes' section). For each: diarize (scripts/diarize.py) → transcribe (scripts/transcribe.py, large-v3, cpu_threads=6) → Obsidian note. Include all transcriptions in a single note.

1. <URL>

Diarization MANDATORY for every video. Langue: contenu en langue source, labels en anglais. Save to Knowledge base/. Push après la note. Background+wait pour toutes les étapes lourdes." \
  "KB: <publication> — <title> [VIDEO]"
```

For **text+image** (has image attachment):

```bash
hermes kanban --board default create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 600 \
  --body "Substack Note — text + image. <publication> (<author>), <date>.

Content: <1-line summary>. Image: <image_url> (<W>x<H>). Download image, analyze with vision/OCR, describe in note section '## Image'.

1. <URL>

Extraction: web_extract works for Notes text. Image URL from preloads JSON. Langue: contenu en langue source, labels en anglais. Save to Knowledge base/. Push après la note." \
  "KB: <publication> — <title>"
```

## Extraction methods by content type

| Method | Articles | Notes (text) | Notes (image) | Notes (video) |
|--------|----------|-------------|---------------|---------------|
| `web_extract` | ✅ Good | ✅ Good (text + discussion) | ❌ No image content | ❌ No video |
| Firecrawl `markdown` | ✅ Good | ❌ Returns empty | ❌ Returns empty | ❌ Returns empty |
| Firecrawl `html` + JS | ✅ Works | ✅ Works | ✅ Extracts `data-video-id` | ✅ Extracts `data-video-id` |
| curl + preloads JSON | ❌ N/A | ✅ Fast metadata | ✅ `imageUrl` from `attachments` | ✅ `mux_playback_id` |

**Rule**: For Substack Notes, use `web_extract` for text content and `curl` on preloads JSON for attachment metadata. Firecrawl `markdown` mode is unreliable for Notes (returns empty).

## Substack Notes — Image Extraction

Notes with `type: "image"` attachments store the URL in the `window._preloads` JSON under the comment's `attachments` array:

```bash
# Extract image URL from preloads JSON
curl -sL --max-time 15 "$SUBSTACK_URL" | \
  grep -oP '"type":"image","imageUrl":"[^"]*"' | \
  grep -oP 'https://[^"]+\.(jpeg|jpg|png|webp)'
```

The image URL is a direct S3 link (e.g. `substack-post-media.s3.amazonaws.com/public/images/<uuid>_<W>x<H>.jpeg`).

### Phase 0 — Download and OCR

```bash
# Download image
curl -sL -o /tmp/substack_image.jpeg "$IMAGE_URL"

# OCR with Tesseract (auto-detect among installed languages)
tesseract /tmp/substack_image.jpeg /tmp/substack_ocr -l eng+fra+spa+deu+ara 2>&1
cat /tmp/substack_ocr.txt
```

Tesseract installed languages on this machine: `eng`, `fra`, `spa`, `deu`, `ara`. OCR is near-instant (< 1s for typical images) and requires no API credits. For non-text images (photos, abstract art), the output will be empty — include a brief manual note: `⚠️ Image contains no extractable text.`

Include OCR output in the Obsidian note under a `## Image` section:

```markdown
## Image

![description](<image_url>)

**OCR:**
> extracted text here...
```

**Ticket body for text+image notes**: include the image URL so the worker doesn't have to re-extract it:

## Researcher worker

### Phase 0 — Extraction (articles only)

```bash
curl -s --max-time 30 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"SUBSTACK_URL","formats":["markdown"]}'
```

Returns: `data.markdown` (full article), `data.metadata` (title, author, date).

For Notes, use `web_extract` for text content + `curl` on preloads JSON for attachments (see sections above).

## Phase 1 — Metadata

| Field | Source |
|-------|--------|
| `title` | `<title>` or first `#` in markdown |
| `author` | `<meta name="author">` |
| `date` | `<meta property="article:modified_time">` |
| `publication` | Domain name (e.g. `aisisterslab.substack.com` → "AI Sisters Lab") |
| `canonical_url` | `<link rel="canonical">` |

## Phase 2 — Markdown cleanup

```python
import re

md = re.sub(r'\[Prendre rendez-vous avec le Lab\]\([^)]+\)(\n\n)?', '', md)
md = re.sub(r'S\'abonner\n\n', '', md)
md = re.sub(r'Merci d\'avoir lu.*?mon travail\.(\n\n)?', '', md)
md = re.sub(r'={30,}\n', '', md)
md = re.sub(r'-{30,}\n', '', md)
md = re.sub(r'\[!\[Avatar.*?\]\([^)]+\)\]\([^)]+\)\n?', '', md)
md = re.sub(r'#### Discussion à propos de ce post.*', '', md, flags=re.DOTALL)
```

## Phase 3 — Obsidian note

### Template

```markdown
---
topic: [<topics>]
date: YYYY-MM-DD
source: <publication>, <date>
source_url: <canonical_url>
confidence: plausible
tags: [<tags>]
---

# <title>

## Summary
2-3 sentences. The essentials.

## Key Points
- Point 1
- Point 2

## Analysis
Context, trends, implications.

## Reliability
⚠️ plausible — newsletter source.

## Source
- [<original title>](<canonical_url>) — <publication>, <date>
```

### Slug

`<publication-slug>_<title-slug>`. Lowercase.

### Tags

- `substack` always
- `<publication-slug>` always
- `ai`, `regulation`, `ai-act`, `fine-tuning`, `open-source` based on content

## Phase 4 — Git push

```bash
cd "$OBSIDIAN_VAULT_PATH"
git add "Knowledge base/<slug>.md"
git commit -m "add: <slug>"
git push
```

## Substack Video Notes — Researcher-Videos Worker

Substack Notes with video attachments use **Mux** as CDN, but Substack exposes a public API to get the signed Mux URL. No auth, no cookies, no browser needed.

### Phase 0 — Extract video ID and download

The `<video>` element (rendered via Firecrawl JS) has a `data-video-id` attribute. Substack's API at `/api/v1/video/upload/{id}/src?type=mp4` returns a 307 redirect to the signed Mux URL.

```bash
# Step 1: Scrape page with JS rendering, extract video-id
FULL_HTML=$(curl -s --max-time 20 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$SUBSTACK_URL\",\"formats\":[\"html\"],\"waitFor\":5000}")

VIDEO_ID=$(echo "$FULL_HTML" | grep -oP 'data-video-id="[^"]*"' | head -1 | cut -d'"' -f2)
echo "Video ID: $VIDEO_ID"

# Step 2: Download via Substack API (follows 307 → signed Mux URL)
curl -sL --max-time 120 \
  -H "Referer: https://substack.com/" \
  -o /tmp/substack_video.mp4 \
  "https://substack.com/api/v1/video/upload/${VIDEO_ID}/src?type=mp4"

ls -lh /tmp/substack_video.mp4
```

The API is **public** — no cookies or authentication required. The 307 redirect carries the signed `?token=...` parameter automatically.

### Post-download pipeline

Standard video pipeline applies (`video-pipeline-global.md`):
1. `scripts/diarize.py` (pyannote, 8kHz mono)
2. `scripts/transcribe.py` (large-v3, cpu_threads=6, 16kHz mono)
3. Obsidian note per knowledge-base template
4. Upload transcript to MinIO for videos >2min
