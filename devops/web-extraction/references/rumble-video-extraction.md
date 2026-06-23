# Rumble Video Extraction via oembed API + yt-dlp

Rumble's public page URLs are protected by Cloudflare anti-bot (403 for yt-dlp,
`document_antibot` retry-exceeded for Firecrawl). The **oembed API** bypasses this
entirely by exposing the real embed URL.

## Quick Recipe

```bash
# 1. Get the real embed URL from oembed API
curl -sL "https://rumble.com/api/Media/oembed.json?url=<FULL_PAGE_URL>" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['html'])"
# → <iframe src="https://rumble.com/embed/v4z2u26/" ...>

# 2. Extract just the embed URL and download
EMBED_URL=$(curl -sL "https://rumble.com/api/Media/oembed.json?url=$PAGE_URL" \
  | python3 -c "import sys,json,re; d=json.load(sys.stdin); \
     m=re.search(r'src=\"([^\"]+)\"', d['html']); print(m.group(1))")

# 3. Download with yt-dlp (embed URL is not bot-protected)
yt-dlp -o "/root/Videos/%(title)s.%(ext)s" "$EMBED_URL"
```

## How It Works

The public page URL (`v51f30f-healing-is-voltage...`) is a JS-rendered wrapper protected by
Cloudflare. The actual video player loads via an embed iframe at a different ID (`v4z2u26`).
The oembed JSON endpoint (`/api/Media/oembed.json?url=...`) exposes this embed URL in the
`html` field without any anti-bot checks.

yt-dlp can download directly from the embed URL — no cookies, no user-agent tricks needed.

## oembed Response Fields

| Field | Example | Notes |
|-------|---------|-------|
| `title` | "Healing Is Voltage..." | Clean title |
| `author_name` | "Humanity United Now..." | Channel name |
| `duration` | 4332 | Seconds |
| `html` | `<iframe src="...v4z2u26/...">` | **Extract src= for the real video URL** |
| `thumbnail_url` | `hugh.cdn.rumble.cloud/...` | CDN thumbnail |
| `provider_name` | "Rumble.com" | Always "Rumble.com" for rumble.com |

## Pitfalls

- **Public page URL ≠ embed URL**: The slug-based URL (`v51f30f-...`) is NOT the video ID.
  Always resolve through oembed first.
- **Embed API direct hit fails**: `https://rumble.com/embed/v51f30f/` returns "Video not found"
  if you use the slug prefix as the ID. The real ID is only in the oembed response.
- **yt-dlp 403 on public page**: Expected. Don't fight it — go through oembed immediately.
- **File naming**: oembed `title` may contain special characters (em-dash, en-dash, commas).
  Use yt-dlp's `%(title)s.%(ext)s` which sanitizes automatically.
- **No cookies needed**: The embed URL has no bot protection. User-agent not required.
