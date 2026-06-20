# KB Agent — Complete Pipeline Registry

Generated via `grep register_pipeline agent/pipelines/*.py`.

## All 17 Registered Pipelines

| Pipeline | Module | Extraction | Synthèse |
|----------|--------|-----------|----------|
| `web` | web.py | Firecrawl | LLM → note |
| `substack` | web.py | Firecrawl + cleanup | LLM → note |
| `substack_text` | web.py | Firecrawl + cleanup | LLM → note |
| `substack_video` | web.py | Video download (paused) | — |
| `substack_image` | web.py | Firecrawl + image extract | LLM + vision → note |
| `threads_video` | threads.py | curl + yt-dlp | LLM two-pass |
| `threads_text` | threads.py | curl + regex captions | LLM → note |
| `instagram_reel` | instagram.py | yt-dlp + diarize | LLM video synthesis |
| `instagram_post` | instagram.py | yt-dlp metadata + Playwright alt text | LLM synthesis |
| `youtube` | youtube.py | yt-dlp + diarize | LLM two-pass |
| `book` | books.py | Legacy (epub alias) | ⚠️ Deprecated — use book_epub/book_pdf |
| `book_epub` | books.py | ebooklib | LLM progressive chapter synthesis |
| `book_pdf` | books.py | pymupdf | LLM progressive chapter synthesis |
| `mega` | books.py | megadl + classify | delegate → per-book |
| `book_batch` | books.py | megadl + classify | delegate → per-book |

## Detection Flow

```
detect_platform(url) → platform string
   ↓
detect_content_subtype(url, platform) → subtype string
   ↓
PIPELINE_STEPS[platform] → step list
   ↓
create_task(conn, url, platform, slug, steps)
   ↓
Consumer: get_pipeline(content_type) → fallback to web
```

**⚠️ Bug: `threads` platform → no `register_pipeline("threads")`**

`detect_platform` returns `"threads"` for Threads URLs. `PIPELINE_STEPS["threads"]` exists. But `register_pipeline("threads")` does NOT exist — only `"threads_text"` and `"threads_video"`. The consumer's `get_pipeline("threads")` returns None → falls back to `"web"` pipeline. Step functions resolve via global `STEP_REGISTRY` fallback. This works because all pipeline modules are imported at startup and their step functions populate STEP_REGISTRY. But error modes (on_error) use web defaults, not threads-specific ones.

## Text Pipelines (6)

Only these 6 are non-video, non-image text pipelines:

1. `web` — generic web articles via Firecrawl
2. `substack_text` — Substack articles with markdown cleanup
3. `threads_text` — Threads text posts via curl + regex
4. `instagram_post` — Instagram `/p/` posts (carousel) via Playwright
5. `book_epub` — ePub extraction via ebooklib
6. `book_pdf` — PDF extraction via pymupdf

## Book Pipeline Split (FIXED 2026-06-19)

**Before:** `.epub$` and `.pdf$` both matched `"book"` in `detect_platform`. The `"book"` pipeline hardcodes `step_extract_epub` → PDFs fail with "No ePub file found".

**After:** `.epub$` → `book_epub`, `.pdf$` → `book_pdf`, `.(mobi|azw3)$` → `book` (legacy). `preflight_health` updated to accept all three.

## Video Pipelines (4)

- `youtube` — yt-dlp + diarize + transcribe + two-pass synthesis
- `instagram_reel` — yt-dlp + diarize + transcribe
- `threads_video` — curl video URL + diarize + transcribe
- `substack_video` — PAUSE (unimplemented, Mux CDN JWT)

## Non-content Pipelines (3)

- `mega` — megadl download + classify + delegate
- `book_batch` — same as mega, routed from mega subtype
- `book` — legacy alias for book_epub
