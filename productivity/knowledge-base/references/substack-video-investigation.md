# Substack Video Download — Investigation

Status: **in progress** — Phase 0 detection works, download approach not yet validated.

## Video hosting

Substack Notes with video use **Mux** as CDN. Video metadata is embedded in `window._preloads` JSON:

```json
"attachments": [{
  "type": "video",
  "mediaUpload": {
    "name": "Yeadon.mp4",
    "duration": 226.56609,
    "is_mux": true,
    "mux_playback_id": "cgt8P02mzP4Kvke7QiHzYR02tB9TanOYJ02Cv91rIpOQ1U",
    "mux_asset_id": "CmgbxlGjD7n11TyE02oXMQQZ2KNRMqJNVJfDMP5985600",
    "primary_file_size": 7283184,
    "state": "transcoded"
  }
}]
```

## What was tested (all failed)

### Direct Mux URLs → 403 "Not Authorized"
```
https://stream.mux.com/{playback_id}.m3u8     → 403
https://stream.mux.com/{playback_id}/low.mp4  → 403
https://stream.mux.com/{playback_id}/medium.mp4 → 403
https://stream.mux.com/{playback_id}/high.mp4 → 403
```
With Origin/Referer headers from substack.com — still 403. Playback requires JWT signed token, generated client-side by Substack's JS.

### yt-dlp → no Substack extractor
```
yt-dlp "https://substack.com/@controlstudies/note/c-264771349"
→ ERROR: No suitable extractor (Substack) found
```
yt-dlp identifies "Substack exclusive embed" but has no handler for it.

### gallery-dl → no Substack extractor
```
gallery-dl --list-extractors | grep substack
→ (no output)
```

### Substack API endpoints → all return HTML, not JSON
```
/api/v1/feed/item/c-264771349   → HTML
/api/v1/note/264771349          → HTML
/api/v1/comment/264771349       → HTML
/api/v1/graphql                 → "Not found"
```
API likely requires authentication or specific Accept headers.

### Firecrawl with JS rendering → empty page
```
curl http://localhost:3002/v2/scrape -d '{"url":"...","formats":["markdown","screenshot"],"waitFor":5000}'
→ returns empty data
```
Substack Notes page is heavily JS-rendered, Firecrawl's rendering may not handle it.

### Browser tool (Playwright) → 404 on /tabs endpoint
```
browser_navigate → "404 Client Error: Not Found for url: http://127.0.0.1:3002/tabs"
```
Playwright service is running but the browser tool targets a different endpoint than what's available.

## Approaches not yet tested

1. **sbstck-dl** (Go CLI, `github.com/alexferrari88/sbstck-dl`) — may handle Notes and video attachments
2. **yt-dlp with Substack cookies** — export cookies from browser logged into Substack, use `--cookies`
3. **Playwright headless (manual)** — outside the browser tool, load page, intercept signed Mux URL from network requests
4. **Chrome extension "Substack Video Downloader"** — reverse-engineer how it accesses Mux URLs

## Detection (Phase 0) — confirmed working

```bash
curl -sL "$URL" | grep -q '"attachments":\[.*"type":"video"'
# exit 0 = video found → assignee: researcher-videos
# exit 1 = no video → assignee: researcher
```
