# Pipeline Architecture — Mechanical vs LLM Boundary

Analysis of the knowledge-base pipeline through the lens of a custom agent rebuild
(no Hermes, no Kanban). Documents which stages are deterministic shell/Python and
which require an LLM call.

## Architecture principle

The pipeline has a natural split: everything before "raw source ready in /tmp/"
is mechanical. Only note synthesis and fact-checking require the LLM.

## Mechanical stages (deterministic, no LLM)

These are shell commands or Python functions that either succeed or fail.
They never need an agent loop.

| Stage | Pipeline | Tool |
|-------|----------|------|
| Cookie validation (Tier 1: structural) | YouTube | `grep -c LOGIN_INFO` |
| Cookie validation (Tier 2: functional) | YouTube | `curl oembed` |
| Cookie validation (sessionid) | Instagram | `grep -c sessionid` |
| Cookie validation (captions) | Threads | `curl + grep captions` |
| Content-type detection (video vs text) | Threads | `curl + grep video_versions` |
| Content-type detection (text/video/image) | Substack | `curl + preloads JSON + SSR` |
| Metadata extraction | YouTube, Instagram | `yt-dlp --print` |
| Video download | YouTube, Instagram | `yt-dlp -f ...` |
| Video download (Substack API) | Substack | `curl -L substack.com/api/v1/video/upload/<id>/src?type=mp4` |
| Text extraction | Threads | `curl + cookies + regex captions` |
| Firecrawl extraction | Substack, Web | `curl localhost:3002/v2/scrape` |
| Markdown cleanup | Substack | Python `re.sub` boilerplate removal |
| Dual audio extraction (16k + 8k WAV) | All video | `ffmpeg` fixed commands |
| Diarization | All video | `scripts/diarize.py` (background+wait) |
| Transcription | All video | `scripts/transcribe.py` (background+wait) |
| Diarization + transcription merge | All video | Fixed Python JSON merge |
| Speaker identification | All video | Regex heuristic on metadata |
| Chapter generation | YouTube | Native chapters or NLP gap detection |
| ePub extraction | Books | `ebooklib` + `BeautifulSoup` |
| PDF text extraction | Books | `pymupdf` |
| Dedup check | All | `grep -rl source_url` |
| MinIO upload | All | `mc cp` |
| Git push | All | `git add; git commit; git push` |

## LLM stages (require model intelligence)

Only these stages call the LLM. The rest is execution.

| Stage | Pipeline | Tokens (est.) | Notes |
|-------|----------|---------------|-------|
| Two-pass YouTube resume | YouTube | 50-150K in, 3-8K out | Passe 1: concept extraction. Passe 2: full note per `resume-prompt.md` |
| Deep-treatment text note | Threads, Instagram, Substack, Web | 10-150K in, 3-8K out | Key Claims (≥4), Section-by-section, Context, Critical Analysis, Nuances |
| Book note | Books | 50-200K in, 5-10K out | Chapter summaries (dominant section), ≥4 quotes, per `book-note-template.md` |
| Fact-checking | Books, health claims | 5-10K in, 500 out | 6-step per `fact-check-workflow.md` |
| Coverage verification | All | ~2K in, 100 out | Did the note cover every section of the source? |

## LLM call count per note type

| Content type | LLM calls | Dominant cost |
|---|---|---|
| YouTube video | 2 (concept extraction + note synthesis) | Note synthesis |
| Instagram Reel (short) | 1 (note synthesis) | Note synthesis |
| Instagram Post / Threads text | 1 (note synthesis) | Note synthesis |
| Substack / Web article | 1 (note synthesis) | Note synthesis |
| Book | 1 (note synthesis) + 2-4 (fact-checks) = 3-5 | Note synthesis + web_search |
| Substack Note with video | 1 (note synthesis, transcript inline) | Note synthesis |

## Why hybrid vs agent loop

An agent-driven pipeline (LLM decides what to run next) on a task that is 80%
mechanical has three failure modes documented in the current system:

1. **Missed mandatory steps.** Diarization was skipped by a worker despite being
   mandatory — now codified as HARD RULE in `video-pipeline-global.md`.
2. **Token waste.** Each agent tool call costs context tokens on a task that a
   Python function can do deterministically.
3. **Wandering.** The LLM can "decide" to deviate from the pipeline (wrong model,
   wrong order). A hard-coded pipeline cannot.

A hard-coded pipeline has one failure mode: an unhandled edge case crashes.
But the edge cases are documented — and new ones get added as branches in the
Python code, not as LLM prompts.

## SQLite state machine sketch

```
tasks
├── id (TEXT PK)
├── source_url (TEXT URL)
├── content_type (TEXT) — youtube|threads|instagram_reel|instagram_post|substack|web|book
├── status (TEXT) — pending|validating|downloading|transcribing|synthesizing|archiving|done|failed|skipped
├── slug (TEXT)
├── error (TEXT)
├── created_at
└── updated_at
```

One process runs the mechanical stages in order. The LLM is called only when
status reaches `synthesizing`. A separate cron sweeps for stalled tasks.
