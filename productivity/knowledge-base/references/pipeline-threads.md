# Threads Pipeline

Threads (Meta) posts — text, images, and video. No yt-dlp extractor exists for Threads; use direct curl + cookies for everything.

## Prerequisites

- **Cookies:** `/root/.hermes/cookies/threads_cookies.txt` (Netscape format, exported from Chrome). Required — most Threads posts return a login wall without auth.
- **User-Agent:** `Googlebot/2.1` (avoids JS redirect to login page)

## Phase 0 — Pre-ticket: Detect & assign (BEFORE kanban ticket creation)

**Run this detection before creating a kanban ticket.** The result determines which profile the ticket is assigned to.

```bash
curl -sL -b /root/.hermes/cookies/threads_cookies.txt \
  -A "Mozilla/5.0 (compatible; Googlebot/2.1)" \
  "THREADS_URL" | python3 -c "
import sys, re
content = sys.stdin.read()
# Check for video_versions — if it's an array (starts with '[') not null
vv = re.search(r'\"video_versions\":(\[|\s*null)', content)
if vv and vv.group(1).startswith('['):
    print('VIDEO')
else:
    print('TEXT')
"
```

- `VIDEO` → `hermes kanban create ... --assignee researcher-videos`
- `TEXT` → `hermes kanban create ... --assignee researcher`

## Phase 1 — Worker pipeline (run by the assigned worker)

## Step 1A — Text extraction

```bash
curl -sL -b /root/.hermes/cookies/threads_cookies.txt \
  -A "Mozilla/5.0 (compatible; Googlebot/2.1)" \
  "THREADS_URL" | python3 -c "
import sys, re, html
content = sys.stdin.read()
# Collect ALL caption texts (thread items + replies). Thread items come first.
captions = re.findall(r'\"caption\":\{\"text\":\"((?:[^\"\\\\]|\\\\.)*)\"', content)
# Also check og metadata as fallback
og_title = re.search(r'property=\"og:title\" content=\"([^\"]*)\"', content)
og_desc = re.search(r'property=\"og:description\" content=\"([^\"]*)\"', content)
author = re.search(r'\"username\":\"([^\"]+)\"', content)
# Output
if captions:
    for c in captions:
        text = html.unescape(c).replace('\\n', '\n')
        print(text)
        print('---ENDCAPTION---')
if og_title: print('TITLE:', html.unescape(og_title.group(1)))
if og_desc: print('DESC:', html.unescape(og_desc.group(1)))
if author: print('AUTHOR:', author.group(1))
" 2>&1
```

## Step 1B — Video extraction

Threads videos are served from Instagram CDN. The `video_versions` JSON array contains direct CDN URLs.

```bash
# Extract video URL
VIDEO_URL=$(curl -sL -b /root/.hermes/cookies/threads_cookies.txt \
  -A "Mozilla/5.0 (compatible; Googlebot/2.1)" \
  "THREADS_URL" | python3 -c "
import sys, re
content = sys.stdin.read()
m = re.search(r'\"video_versions\":\[\{\"type\":\d+,\"url\":\"(https:[^\"]+)\"', content)
if m:
    print(m.group(1).replace('\\\\/', '/'))
")

# Download
curl -sL -o /tmp/threads_video.mp4 \
  -H "Referer: https://www.threads.net/" \
  -H "User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1)" \
  "$VIDEO_URL"
```

Then follow the canonical video pipeline: extract audio → diarize (`scripts/diarize.py`) → transcribe (`scripts/transcribe.py`, large-v3) → merge → summarize. See `references/video-pipeline-global.md`.

## Quality gate

**Before creating a note, verify real content was extracted:**

- If `captions` is empty AND `og:description` is the generic "Join Threads to share ideas..." → **skip, do not create a note**
- If only `og:description` was extracted but no `caption` → note quality is LOW, flag with `confidence: untested` and note the limitation

## Known pitfalls & edge cases

### 1. Caption truncation (long posts) — ✅ FIXED

The old regex `caption[^}]*"text"` only captured the first JSON object under `caption`. Fixed by using `"caption":{"text":"` which matches ALL caption texts globally. Thread items come first in JSON order, followed by comments. The delimiter `---ENDCAPTION---` separates them for downstream processing.

### 2. Instagram video cross-posts (media_type=19) — ✅ FIXED

`media_type=19` is NOT a carousel and NOT "image-only." It's Threads' post type for Instagram video cross-posts. The post contains a `media_type=2` (video) child hosted on Instagram CDN (`cdninstagram.com`) with full `video_versions`. The detection now checks for `video_versions` directly regardless of outer media_type, so this is caught.

### 3. Video posts not routed to researcher-videos — ✅ FIXED

The detection step was previously inside the worker pipeline (Step 1), but by the time the worker runs, the ticket is already assigned. Detection has been moved to **Phase 0 — Pre-ticket**: run BEFORE kanban ticket creation so the dispatcher knows `VIDEO` → `--assignee researcher-videos` or `TEXT` → `--assignee researcher`.

### 4. Reply posts without parent context

Posts with `is_reply=true` in the JSON are replies to another post. Extracting only the reply text yields a 1-sentence fragment without context (e.g., "The hairdresser explained their hair color changed.").

**Fix**: Check `is_reply` field. If true, extract the parent post URL from `reply_to_media` and fetch BOTH the reply and the parent. Create the note from the combined context, or skip if the parent is inaccessible.

### 5. Thread continuations not fetched — ✅ Fixed by #1

Same root cause as #1. Posts with `self_thread_length > 1` have all thread items in the root JSON as separate `caption` objects. The broader regex from fix #1 collects all of them in order (thread items come first, then comments). No separate fix needed.

### 6. Duplicate notes (no URL dedup) — ✅ FIXED

The same Threads URL can be processed multiple times (via different kanban tickets or manual reprocessing), creating duplicate notes in the vault.

**Fix**: Before creating a note, search the vault for existing notes with the same `source_url` in frontmatter:
```bash
grep -rl "source_url: THREADS_URL" "$OBSIDIAN_VAULT_PATH/Knowledge base/"
```
If found, update the existing note instead of creating a duplicate.

### 7. og:description-only extraction (login wall / no cookies) — ✅ Already handled

Without valid cookies, Threads returns a login wall. `web_extract` or curl without cookies only gets `og:description` — the generic "Join Threads to share ideas..." text. The quality gate (above) already enforces: if only `og:description` is available and it's the login-wall text, **skip the post entirely** — do not create a note.

## Rate-limiting

- Sleep 5–10s between Threads requests
- 2–3 Threads posts per worker session max

## Comparison: Threads vs Instagram

| | Threads | Instagram |
|---|---|---|
| **Extractor** | None (curl only) | yt-dlp (Reels), Playwright (carousels) |
| **Video detection** | `video_versions` JSON field | og:type or URL path |
| **Auth** | threads_cookies.txt | ig_cookies.txt |
| **CDN** | Instagram CDN (same infra) | Instagram CDN |
| **Text extraction** | captions from inline JSON | og:description or Playwright |
