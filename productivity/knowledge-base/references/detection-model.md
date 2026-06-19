# Detection & Pre-Flight Model

Complete model of all detection and pre-flight steps across all content types.
Sourced from the pipeline references (not generated from memory).

## URL Detection Flow

```
URL submitted
  │
  ├── Platform detection (URL regex, deterministic)
  │     youtube.com/watch, youtu.be/, youtube.com/shorts,
  │       m.youtube.com, youtube.com/embed, music.youtube.com → youtube
  │     threads.net/@                                      → threads
  │     instagram.com/reel/                                → instagram_reel
  │     instagram.com/p/                                   → instagram_post
  │     substack.com/                                      → substack
  │     .epub, .pdf, .mobi, .azw3 (direct upload)         → book
  │     everything else                                    → web
  │
  ├── Dedup check: grep vault for source_url → skip if exists
  │
  ├── Pre-flight health (platform-specific)
  │     youtube:       Tier 1 (grep LOGIN_INFO+SAPISID+3PSID ≥3)
  │                    Tier 2 (curl oembed, IP fingerprinting)
  │                    Tier 3 (yt-dlp version, nightly vs stable)
  │     instagram:     grep -c sessionid ≥1
  │     threads:       cookies file exists + captions test on known post
  │     substack:      curl Firecrawl /scrape health
  │     web:           curl Firecrawl /scrape health
  │     → any fail = PAUSE with reason, do NOT ticket
  │
  └── Content subtype (only for platforms with variants)
        threads:   curl + grep video_versions → VIDEO or TEXT
                   (media_type=19 handled by video_versions check)
        substack:  curl preloads JSON + SSR HTML fallback → TEXT/IMAGE/VIDEO
        instagram_post: always TEXT/IMAGE (carousel alt text extraction)
                        no video-in-carousel detection in current system

All: Dedup check BEFORE queue insertion.
```

## Mega Link Detection

```
mega.nz link submitted
  │
  ├── mega.nz/file/  → check file metadata:
  │     ├── .zip archive → BOOK BATCH (see Book flow)
  │     ├── .mp4/.mkv/.webm → MEGA VIDEO (researcher-videos pipeline)
  │     └── unknown → download metadata, classify
  │
  └── mega.nz/folder/ → list contents → detect per file
```

## Book Flow (Mega Archive)

```
Mega.nz/.zip link → megadl download → unzip to clean directory
  │
  ├── List all books (.epub, .pdf, .mobi, .azw3)
  │
  ├── Pre-flight per PDF (THREE TIER):
  │     Tier 1: pymupdf char count < 500 → SCANNED → queue OCR, do NOT ticket
  │     Tier 2: 500+ chars, quality_score(16 pages) < 80 → DEGRADED OCR
  │              (pre-19th-century PDFs: long-s→f, garbled headers)
  │              → queue for fresh OCR, do NOT ticket
  │     Tier 3: 500+ chars, quality_score(16p) ≥ 80 → GOOD TEXT → ticket
  │     epub/mobi/azw3 → always ticket (extractable text)
  │
  ├── Create one task per ticketed book
  │     Digital: extract → read → note → MinIO → git
  │     Scanned: marker-pdf 1 page at a time → OCR → concatenate → note
  │
  └── Scanned tasks chained AFTER all digital tasks (--parent to last non-OCR)
```

## Music-Only Reels

- Detected POST-transcription: segments total < 50 characters
- Use caption/metadata via Googlebot UA as primary content
- Annotate: `⚠️ Music-only Reel — analysis based on caption text`

## Pre-Flight Sources

| Platform | Check | Source File |
|---|---|---|
| YouTube Tier 1 | grep LOGIN_INFO+SAPISID+3PSID | edge-cases.md |
| YouTube Tier 2 | curl oembed (IP fingerprinting) | edge-cases.md |
| YouTube Tier 3 | yt-dlp version (nightly) | edge-cases.md |
| YouTube n-sig | --js-runtime node required | pipeline-youtube.md |
| Instagram | grep sessionid | edge-cases.md |
| Instagram routing | /reel/ vs /p/ URL path | edge-cases.md |
| Threads cookies | captions test on known post | edge-cases.md |
| Threads subtype | curl video_versions | pipeline-threads.md |
| Substack health | curl Firecrawl /scrape | pipeline-substack.md |
| Substack subtype | preloads JSON + SSR HTML | pipeline-substack.md |
| Web health | curl Firecrawl /scrape | pipeline-web.md |
| Book PDF Tier 1 | pymupdf char count < 500 | books-extraction.md |
| Book PDF Tier 2-3 | quality_score(16p) | SKILL.md + memory (ref below) |
| Music-only Reel | segments < 50 chars | edge-cases.md |

## Related References

- `ocr-scanned-pdfs.md` — quality_score() implementation details
- `pipeline-threads.md` — Phase 0 detection, media_type=19
- `pipeline-substack.md` — Phase -1 detection, two-layer
- `pipeline-instagram.md` — URL routing, sessionid
- `pipeline-youtube.md` — n-sig challenge, bot detection
- `pipeline-web.md` — Firecrawl health
- `pipeline-mega.md` — Mega video pipeline
- `books-extraction.md` — PDF pre-flight, OCR pipeline
- `edge-cases.md` — All cookie validation tiers, music-only Reels
