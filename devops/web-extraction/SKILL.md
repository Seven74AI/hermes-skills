---
name: web-extraction
description: "Diagnose and fix web content extraction failures — JS-rendered pages, Firecrawl self-hosted, API fallbacks."
version: 1.0.0
author: agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, firecrawl, extraction, debugging, js-rendering]
    created_by: agent
---

# Web Extraction Debugging

When `web_extract` returns incomplete content — just the page shell, nav links, and "Log in" prompts instead of actual body text — the page is almost certainly JS-rendered. Hermes's built-in `web_extract` tool calls Firecrawl's scrape endpoint but historically did not pass `wait_for` (JS rendering delay). As of May 2026 the provider has been patched to include `wait_for=3000` by default, but it only takes effect after a process restart.

## Tool Priority for Web Extraction

Choose the right tool in order of cost/speed:

1. **`web_extract`** — first choice. Fast, cheap, works for most pages (static HTML, PDFs, many SPAs). Respects `extract_backend` in config.
2. **Firecrawl direct API** — when `web_extract` returns shell HTML (JS-rendered pages like Threads, Twitter/X, Instagram). Self-hosted at `http://localhost:3002/v1/scrape`.
3. **`browser` tools** — last resort. Heavy, slow, requires a running browser service. Use only when you need to interact (click, type, scroll), not just extract.

## Triggers

- `web_extract` returns a title + first line but no body content
- The result has shell elements (nav, "Log in", "Sign up") but no article text
- The target is a known SPA: Threads, Twitter/X, Instagram, any React/Vue/Angular site
- You're on a system where Firecrawl is self-hosted (Docker on `localhost:3002`)
- `web_extract` returns content that looks like nav/UI chrome with no article body — the page is likely JS-rendered

## Diagnosis Steps

### 1. Confirm Firecrawl is running

```bash
docker ps | grep firecrawl
# Should show firecrawl-api-1, playwright-service, redis, rabbitmq, postgres
curl -s http://localhost:3002/v1/scrape -X POST \
  -H "Content-Type: application/json" \
  -d '{"url":"https://httpbin.org/get","formats":["markdown"]}' | head -c 200
```

### 2. Check that `FIRECRAWL_API_URL` is set

```bash
grep FIRECRAWL_API_URL ~/.hermes/.env
# Should show: FIRECRAWL_API_URL=http://localhost:3002
```

Without it, the Firecrawl plugin won't find the local instance and falls through to the managed gateway or errors out.

### 3. Test with `wait_for` directly

```bash
cd /usr/local/lib/hermes-agent && source venv/bin/activate && python3 -c "
from firecrawl import Firecrawl
fc = Firecrawl(api_url='http://localhost:3002')
result = fc.scrape(url='https://www.threads.com/@adhd.thriver/post/DYneGuxCrm-',
                   formats=['markdown'], wait_for=3000)
print(len(result.model_dump().get('markdown','')))
"
# >8000 chars = JS rendered and content loaded; <3000 chars = still just the shell
```

### 4. If `wait_for` works from the SDK but not from `web_extract`

The provider module is cached in-process. Either:
- Start a new session (`/reset`)
- Restart the gateway (`hermes gateway restart`)
- Use the SDK directly via `execute_code` (sandboxed, fresh process)

### 5. If Firecrawl itself returns empty content

Check the playwright service logs:
```bash
docker logs firecrawl-playwright-service-1 --tail 50
```

Common causes: rate-limiting by the target site, bot detection, or the page needing authentication.

## The Provider Patch

The canonical fix lives in `plugins/web/firecrawl/provider.py`, line ~487. The scrape call was:

```python
_get_firecrawl_client().scrape, url=url, formats=formats,
```

Patched to:

```python
_get_firecrawl_client().scrape, url=url, formats=formats, wait_for=3000,
```

3000ms is a safe default — most SPAs hydrate well within this window. For exceptionally slow pages, use the SDK directly with a longer `wait_for`.

## Configuration Reference

| Config key | Env var | Purpose |
|-----------|---------|---------|
| `web.extract_backend: firecrawl` | — | Selects Firecrawl as extraction backend |
| `web.backend: ddgs` | — | Search backend (separate from extract) |
| — | `FIRECRAWL_API_URL` | Self-hosted Firecrawl URL (e.g. `http://localhost:3002`) |
| — | `FIRECRAWL_API_KEY` | Cloud Firecrawl API key (mutually exclusive with URL for direct mode) |
| — | `FIRECRAWL_GATEWAY_URL` | Nous tool-gateway URL (subscribers only) |

## Firecrawl Direct Access (Python SDK)

When `web_extract` fails, use the Firecrawl Python SDK directly:

```python
from firecrawl import FirecrawlApp
app = FirecrawlApp(api_url="http://localhost:3002")
result = app.scrape_url(url, params={"formats": ["markdown"], "waitFor": 3000})
```

Key params:
- `waitFor` — milliseconds to wait for JS rendering (3000 is a good default)
- `formats` — `["markdown"]` gives clean text
- No API key needed for self-hosted

## Pitfalls

- **Don't assume Firecrawl isn't available**: it's self-hosted and doesn't need an API key. Check `docker ps | grep firecrawl` before telling the user you can't extract content.
- **`FIRECRAWL_API_URL` set but no Docker container running**: the provider will try to connect and time out after 60s. Check `docker ps` first.
- **Provider module caching**: code changes to `plugins/web/firecrawl/provider.py` require a process restart to take effect. The `execute_code` sandbox always gets fresh imports.
- **`execute_code` sandbox doesn't inherit `.env`**: it runs in an isolated environment. Pass `os.environ["FIRECRAWL_API_URL"]` explicitly when testing from `execute_code`.
- **Firecrawl v4 SDK returns Pydantic models, not dicts**: use `.model_dump()` to inspect, or access fields directly (`result.markdown`).
- **Firecrawl `video` format is cloud-only**: the self-hosted Docker SDK rejects `"video"` as an invalid format (Pydantic validation: not in the literal enum). Instagram video extraction requires yt-dlp — see `references/instagram-video-extraction.md` for the CDN URL + curl + ffmpeg recipe.
- **Instagram Reels: Firecrawl gets text/metadata, not video**: `web_extract` can summarize the caption, comments, and creator profile via LLM summarization, but the video itself is JS-loaded and unreachable. Use yt-dlp (reference above).

## Reference Files

- `references/threads-scraping-recipe.md` — cURL + Python SDK recipe for Threads.com, expected output sizes, content markers for verification.
- `references/instagram-video-extraction.md` — yt-dlp recipe for Instagram Reel video extraction when Firecrawl's cloud-only `video` format isn't available. CDN URL extraction + curl + ffmpeg merge.
