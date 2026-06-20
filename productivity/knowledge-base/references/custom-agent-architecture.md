# Custom KB Agent Architecture

Architecture decisions from the 2026-06-18 grill session. A custom agent replacing Hermes
for KB pipeline layers A (ingestion), B (orchestration), and D (synthesis). Extraction (C)
and archival (E) remain unchanged.

Full CONTEXT.md at `/root/kb-agent/CONTEXT.md` on the VPS.

## Key Decisions

| # | Decision |
|---|----------|
| 1 | Python from scratch. No agent framework (LangChain, CrewAI). Edgee as LLM gateway. |
| 2 | SQLite WAL mode for task queue + logs. Two files: `agent.db` + `logs.db`. |
| 3 | Flask web dashboard — submit URLs + view queue status. Tailscale-only, no auth. |
| 4 | Deterministic routing by URL pattern (Python, no LLM). Extensible via SQL tables. |
| 5 | Hybrid pipeline: Python for mechanical (download, diarize, transcribe, MinIO, git), LLM for synthesis only. |
| 6 | LLM is stateless (prompt → response). Tools: `read_file`, `write_file`, `search_files` always; `web_search` conditional per content type. |
| 7 | Template injected into system prompt by Python orchestrator. Varies by content type. |
| 8 | Chunking at ~50K token boundary with overlap at natural boundaries for large content. |
| 9 | Quality gates run by orchestrator AFTER LLM writes note: line count, quote count, coverage, multi-pass. **MUST raise StepError(FAIL) when gate fails** — returning JSON with `passed: false` is silently ignored by the consumer, which continues to minio_upload + git_push. "Never push v1" enforced programmatically via exception, not return value. |
| 10 | See Also as separate post-synthesis LLM call using vault search results. Eliminates ghost wikilinks. |
| 11 | Single async process. Semaphore(1) for video (sequential, RAM safety). Text parallel. |
| 12 | Error model: RETRY (5s→15s→PAUSE after 2 retries) / PAUSE (operator resumes via web button) / FAIL (unrecoverable). Max retries=2 per user preference — short backoff, fast human review. |
| 13 | Level D logs — every step output, every LLM prompt archived. FTS5 searchable. |
| 14 | No push notifications. Website is the dashboard. |
| 15 | Fully separate infrastructure from Hermes for A/B comparison. |
| 16 | No user confirmation for book processing. Mega link → extract → auto-create one task per book. |
| 17 | No timeouts anywhere. Step durations unpredictable (24h video = 24h diarization). Monitor via streaming stdout to dashboard. Operator handles pathological hangs. |

## Pipeline Steps (per content type)

Generated from `pipelines` table in SQL, not hardcoded. Mechanical steps run as Python functions:

- `validate_cookies` — grep + curl, pass/fail
- `extract_metadata` — yt-dlp or curl
- `download_video` — yt-dlp with cookies
- `extract_audio_16k` / `extract_audio_8k` — ffmpeg
- `diarize` — canonical `scripts/diarize.py`, background+wait
- `transcribe` — canonical `scripts/transcribe.py`, background+wait
- `merge_diarization_transcript` — Python merge
- `speaker_identification` — heuristic from metadata
- `chapter_generation` — YouTube native or NLP fallback
- `firecrawl_extract` — curl to localhost:3002
- `markdown_cleanup` — regex
- `epub_extract` — ebooklib + BeautifulSoup
- `synthesize_note` — **LLM call** (the only synthesis step)
- `upload_minio` / `verify_minio` — mc cp + mc ls
- `git_push` — git add/commit/push

## Process Management & Timeouts

**No timeouts — anywhere.** Step durations are unpredictable: a 24h video means 24h
diarization. A blanket timeout will inevitably kill legitimate work. Steps take as long
as they take. HTTP calls are the only exception — `requests`/`httpx` have built-in
timeouts (~30s), fine for cookie validation and Firecrawl.

**Monitoring via streaming, not timeouts.** Use `proc.stdout.readline()` to read
subprocess output line-by-line WHILE it runs (not `communicate()` which buffers).
Stream progress to `logs.db` in real time. The dashboard shows staleness naturally:
if a process stops producing output, the operator spots "last update: 2h ago" and
intervenes. No heuristic timeout, no guessing — visible progress.

Key Python pattern from the docs:
```python
proc = await asyncio.create_subprocess_exec(
    'python3', 'diarize.py', audio_path,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
while True:
    line = await proc.stdout.readline()
    if not line:
        break
    log_to_db(line.decode())  # live progress → dashboard
await proc.wait()
```

`asyncio.subprocess.Process` has no timeout parameter (`wait()` and `communicate()`
do not accept `timeout` — confirmed via Context7 from CPython docs). Only the
sync `subprocess.Popen` does. For the async consumer, use `proc.returncode is None`
to check liveness without blocking.

**Crash cleanup — PR_SET_PDEATHSIG.** In canonical scripts (`diarize.py`,
`transcribe.py`): `libc.prctl(1, signal.SIGKILL)` — kernel kills child when parent
dies for any reason (OOM, SIGKILL). No orphans. Combined with Python's GC behavior
(Process object garbage collected → child killed), two layers of orphan protection.

**Graceful shutdown:** Consumer catches SIGTERM/SIGINT, waits for running steps
to finish, then exits. `asyncio` cancellation with proper cleanup.

**Pathological hangs:** Operator intervenes via dashboard. Distinguishing a hang
from slow-but-valid work requires human judgment — no automated kill.

## Edgee Integration

Used as LLM gateway for provider routing and prompt compression. LLM backend is swappable —
architecture does not depend on Edgee.

### Endpoint
```
POST https://api.edgee.ai/v1/chat/completions  (OpenAI-compatible)
```
Same format as DeepSeek direct. Toggle is a one-line `base_url` change.

### Compression
Transparent, enabled via `compression_model: "claude"` field in request.
Response includes `compression.saved_tokens`, `compression.reduction` (%), `compression.cost_savings` (micro-units), `compression.time_ms`.

### Streaming vs Non-Streaming
- ❌ Streaming: 3 server-side bugs — do NOT use with Hermes Agent
- ✅ Non-streaming (`stream=False`): Works correctly — no known issues

KB Agent uses non-streaming calls exclusively, so Edgee is viable. Known Hermes HTTP/2
issues do not apply (custom agent uses standard httpx with `stream=False`).

Compression will be tested empirically on 2-3 books before committing to `compression_model`.

Full API reference: `edgee-setup` skill → `references/edgee-api-reference.md`
