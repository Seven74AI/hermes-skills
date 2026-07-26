---
name: kb-agent
description: "KB Agent project — custom Python agent replacing Hermes KB pipeline. Code, vault, kanban, Edgee toggle, infrastructure isolation."
version: 1.4.0
metadata:
  hermes:
    tags: [kb-agent, project, knowledge-base, agent, reference]
---

# KB Agent — Project Configuration

Custom Python agent replacing Hermes KB pipeline layers A (ingestion), B (orchestration), D (synthesis). Load this skill when working on the KB Agent codebase or discussing its architecture.

Also load `edgee-setup` for LLM gateway configuration — Edgee is the optional gateway, DeepSeek direct is the default.

## Repos

| Repo | URL | Purpose |
|------|-----|---------|
| `Seven74AI/kb-agent` | `github.com/Seven74AI/kb-agent` | Agent source code |
| `Seven74AI/kb-agent-obsidian-vault` | `github.com/Seven74AI/kb-agent-obsidian-vault` | Notes produced by KB Agent |

Both **private**.

- Code working directory: `/root/kb-agent/`
- Vault path: `/root/kb-agent-vault/`
- Git credential helper: `git config credential.helper '!gh auth git-credential'` (set in both repos)

## Kanban

- **Board:** `kb-agent`
- **Assignees:** `coder` (implementation), `reviewer` (auto-swarm)
- **Pattern:** Swarm v1 — coder → reviewer → auto-unblock. Tickets chained with `--parent`.
- **Ticket count:** 58 tickets (all done) — run `hermes kanban --board kb-agent list` for live count; the number grows with drift-fix and bug-fix tickets
- **Current status:** `hermes kanban --board kb-agent list` (0 pending)

## Tech Stack

**Tech Stack:** Python 3.11+, Flask, sqlite3 (stdlib), httpx, asyncio, PyYAML
- LLM: DeepSeek v4 Pro (OpenAI-compatible `/v1/chat/completions`)
- Optional: Edgee gateway (`https://api.edgee.ai/v1/chat/completions`) — toggle via `config.yaml: llm_provider`
- Canonical scripts: Symlinked from `/root/.hermes/skills/productivity/knowledge-base/scripts/`
- Templates: Copied from knowledge-base skill
- No agent frameworks (no LangChain, CrewAI, etc.)
- No timeouts anywhere (HTTP calls only: ~30s built-in)
- Systemd unit: `references/kb-agent.service` (installed at `/etc/systemd/system/kb-agent.service`)

## LLM — Edgee Toggle

Both DeepSeek and Edgee use identical OpenAI-compatible format. **Live toggle on dashboard** — no config edit or restart needed. Click "Switch to edgee/deepseek" on the dashboard. The `/provider/toggle` endpoint mutates `config.llm_provider` and `config.llm_base_url` in-memory. New tasks use the switched provider immediately.

Config fallback (for permanent changes):
```yaml
llm_provider: deepseek       # deepseek or edgee
llm_base_url: https://api.deepseek.com/v1
# For edgee: set llm_base_url: https://api.edgee.ai/v1
```

API key comes from `EDGEE_API_KEY` in `~/.hermes/.env` (loaded via systemd `EnvironmentFile`). No key needed in config.yaml. See `edgee-setup` skill for full API reference.

**Edgee model prefix:** Edgee routes by provider prefix — the model name sent to Edgee MUST include the provider path, e.g. `deepseek/deepseek-v4-pro`, NOT bare `deepseek-v4-pro`. The `get_llm_client()` factory in `agent/llm.py` auto-prepends `deepseek/` when `llm_provider=edgee` and the model name has no `/`. Direct DeepSeek keeps the bare name. See `edgee-setup` skill for full API reference.

## Infrastructure Isolation

KB Agent and Hermes KB pipeline run on the same VPS but fully isolated:

| Resource | Hermes | KB Agent |
|----------|--------|----------|
| MinIO bucket | `knowledge-base/` | `kb-agent-archive/` |
| Obsidian vault | `OBSIDIAN_VAULT_PATH` | `/root/kb-agent-vault/` |
| Cookies | `/root/.hermes/cookies/` | `/root/kb-agent/cookies/` |
| Config | `~/.hermes/` | `/root/kb-agent/` |
| Firecrawl | `localhost:3002` (shared, stateless) | Same |

## Architecture

Single Python process — Flask (sync, main thread) + asyncio consumer (background thread). SQLite ×2: `agent.db` (tasks + steps) and `logs.db` (step output + LLM archives). FTS5 search on both.

Detection → dedup → pre-flight health → task creation → consumer claims → mechanical steps → LLM synthesis → quality gates → See Also → MinIO upload → Git push.

No timeouts. Streaming progress via `readline()` to logs.db. Hang detection via dashboard staleness.

## Key Docs

- `/root/kb-agent/CONTEXT.md` — Architecture, glossary, all decisions
- `/root/kb-agent/.hermes/plans/2026-06-19_000000-kb-agent-v1.md` — Full implementation plan (28 tasks)
- Edgee API reference: `edgee-setup` skill → `references/edgee-api-reference.md`

### Pipeline Reference

- `references/pipeline-registry.md` — **Complete pipeline map.** All 17 registered pipelines, detection flow, platform→pipeline mapping, pitfalls. Run `grep register_pipeline agent/pipelines/*.py` to refresh. Always consult this before answering pipeline coverage questions — never answer from memory.
- `references/book-progressive-synthesis.md` — **Book synthesis design.** Why the original group-summarize approach was wrong and how progressive chunk-by-chunk synthesis (CONTEXT.md design) works.

## Templates & Scripts

Templates copied from knowledge-base skill (identical format for A/B comparison):
- `templates/book-note-template.md`
- `templates/youtube-note-template.md`
- `templates/resume-prompt.md`

Canonical scripts symlinked:
- `scripts/diarize.py` → `/root/.hermes/skills/productivity/knowledge-base/scripts/diarize.py`
- `scripts/transcribe.py` → `/root/.hermes/skills/productivity/knowledge-base/scripts/transcribe.py`

## Testing Against Hermes KB Output

For A/B comparison between kba and the existing Hermes pipeline, use URLs from **already-processed** Hermes KB notes. These are the ground truth — the Hermes vault contains the note that was produced, so the output can be compared directly.

### Finding test URLs

1. Search the **Hermes Obsidian vault** at `/root/Documents/Obsidian Vault/Knowledge base/`
2. Scan `.md` files for `source_url:` in frontmatter
3. Filter by pipeline type: Web (exclude books/PDFs/archive.org), Threads, Instagram, Substack
4. Pick one URL per pipeline — the note filename confirms it was successfully processed

### Pitfall — skipped queue files

Do NOT pull test URLs from `/root/.hermes/queues/skipped_*.txt`. These are URLs that failed processing (login walls, dead links, cookie failures) — they are the backlog to fix, not a source of known-good test data. Using skipped URLs for kba testing means testing against content that might be inaccessible, wasting time on false negatives.

### Vault path

- Hermes vault: `/root/Documents/Obsidian Vault/Knowledge base/` (from `OBSIDIAN_VAULT_PATH` in `~/.hermes/.env`)
- kba vault: `/root/kb-agent-vault/` (fresh, separate repo)

## Known Bugs (verified 2026-06-19 — see `references/code-review-2026-06-19.md`)

### 🔴 Bugs

**1. Triple orphan recovery** — `_recover_orphans()` runs 3× at startup. Root cause: `consumer.run()` calls `await self.startup()` (line 220) but `_run_consumer` already called it (run.py line 126). Module-level `_recover_orphans()` in `run.py:163` runs first, then consumer startup twice. DB init is idempotent but orphan recovery isn't — same task can be reset by multiple passes.

**2. `_kb_shutdown` dead code** — Set in `run.py:188`, never read anywhere. ✅ **FIXED** (PR #24 merged 2026-06-19) — the 6 lines deleted from run.py.

**3. Flask shutdown broken in production** — `run.py:194-199` calls `request.environ.get("werkzeug.server.shutdown")` but this only exists in Werkzeug dev server. In production (gunicorn/waitress/systemd), Flask never stops on SIGTERM — the try/except silently catches the RuntimeError.

**4. Book quality gate + consumer double-retry** — `step_book_quality_gate` raises `StepError(RETRY)` with `on_error="retry"` → consumer adds 5 retries on top of the quality check. Each retry re-runs the full LLM quality gate. Other quality gates (web, youtube, threads, instagram) correctly raise `StepError(FAIL)`.

### 🟡 Code smells

**5. `streaming.py` (196 lines) entirely dead** — `run_with_streaming()` and `stream_to_logs()` never called outside the module.

**6. `archive_llm_call()` never called** — Function exists in `db.py:296`, table `llm_archives` in schema, zero callers.

**7. `rotate_logs.py` not scheduled** — Script complete but no cron job, no integration.

**8. MinIO + Git push duplicated 4×** — threads.py, instagram.py, books.py, youtube.py each reimplement their own minio_upload + git_push steps. `archival.py` exists but only web.py uses it.

**9. `start_consumer()` zombie function** — `consumer.py:436-467` defines a standalone `start_consumer()` that creates its own thread. `main()` ignores it. ✅ **FIXED** (PR #23 merged 2026-06-19) — 33 lines deleted, consumer.py 442→408 lines.

### ❌ Previously claimed bugs that do NOT exist (verified)

- Quality gates web/youtube/threads DO raise `StepError(FAIL)` — web.py:639, youtube.py:1058, threads.py:996+1002.
- See Also IS registered in all pipelines — books:989, instagram:1049, threads:1147, youtube:1264.
- `CHUNK_TOKEN_THRESHOLD` IS 50_000 (not 80K) — web.py:30.
- `fact_check_count` IS implemented for books (`quality.py:156`), only missing for web articles.

### Threads: empty captions (login wall) — UNFIXED

Threads extraction may succeed at fetching the page but `captions: []` in the saved JSON. The `threads_text_synthesize` step correctly fails with `"No caption text found for synthesis"`. Likely cause: stale cookies — the page loads but content is behind authentication. The `_is_login_wall` check catches obvious login walls but some posts load the page shell without content.

**Cookie shelf life confirmed: < 2 weeks.** Cookies from June 6 tested on June 19 (13 days) → HTTP 302 redirect to `instagram.com/accounts/login`. Fix: re-export cookies from Chrome → upload via dashboard. Rotate before they hit 10 days old.

### Instagram carousel: headless Playwright blocked — UNFIXED

Even with valid cookies injected, Instagram serves a login wall to headless Chrome. Playwright extracts 0 slides reliably. The `carousel_extract` step is set to `on_error="fail"` (no retries — anti-bot makes them pointless). Instagram carousel extraction is effectively non-functional until a non-headless or cookie-blessed browser profile approach is implemented.

### Config defaults updated (2026-06-19)

- `max_retries: 2` (was 5) — 5s → 15s → PAUSE
- `book_min_lines: 40` (was 100) — 100 was too strict for concise chapter-by-chapter summaries
- `book_min_quotes: 4` and `book_min_size: 8000` unchanged

### Dashboard: no submit form in original plan — FIXED (added)

The original plan specified curl-only submission ("Zero JS dependencies. 2 routes."). A pure HTML submit form was added to the dashboard. When asked about features not present, always check the plan first (`/root/kb-agent/.hermes/plans/2026-06-19_000000-kb-agent-v1.md`).

## Service Management

KB Agent runs as a systemd service. Config: `/etc/systemd/system/kb-agent.service`.

```bash
systemctl status kb-agent
systemctl restart kb-agent
journalctl -u kb-agent -f
```

Uses the Hermes venv Python (`/usr/local/lib/hermes-agent/venv/bin/python3`) — the system Python lacks dependencies. The `EnvironmentFile=/root/.hermes/.env` directive injects `DEEPSEEK_API_KEY` and `EDGEE_API_KEY`.

**PATH must include venv bin:** The service needs `Environment=PATH=/usr/local/lib/hermes-agent/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`. Without this, `subprocess.run(["yt-dlp", ...])` fails with `FileNotFoundError` because yt-dlp is in the venv bin, not system PATH. Added 2026-06-19.

## Dashboard

- URL: `http://vmi3304846.tail5c02a1.ts.net:5000/dashboard` (Tailscale-only — iptables DROP on public IP)
- Submit form: built into the dashboard (POST /submit with `<form>`)
- Cookie upload: also on the dashboard (POST /upload-cookies)
- LLM toggle: live switch between deepseek/edgee (POST /provider/toggle — no restart)
- Retry: resume a paused/failed task from its failing step (POST /task/<id>/retry)
- Restart: restart a paused/failed task from scratch (POST /task/<id>/restart)
- DB paths: tasks in `data/agent.db`, logs in `data/logs.db`

## DB Wipe

To reset all tasks:

```bash
systemctl stop kb-agent
rm -f /root/kb-agent/data/agent.db /root/kb-agent/data/logs.db
systemctl start kb-agent
```

## Kanban Worker Pitfalls (critical — 2026-06-19)

### 1. `--skill kb-agent` kills workers under `coder` profile

The `kb-agent` skill is registered for the **default** Hermes profile only. When a kanban task is created with `--skill kb-agent` and assigned to `coder`, the worker gets `Unknown skill(s): kb-agent` at startup and crashes immediately (pid not alive). The gateway dispatcher then loops: spawn → crash → auto_block → promote → spawn... every 60 seconds, flooding notifications.

**Fix:** For `coder`-assigned tasks, use ONLY `--skill knowledge-base`. The `kb-agent` dogfood skill is for interactive sessions with the default profile.

**Detection:** Worker logs at `/root/.hermes/kanban/boards/kb-agent/logs/t_<id>.log` show repeated `Error: Unknown skill(s): kb-agent`. Gateway log shows `spawned=N crashed=N auto_blocked=N` every 60s.

**After fixing skills in DB:** Update `tasks.skills` via SQLite, then restart gateway to clear the crash cycle.

### 2. `max_spawn: 1` — prevent parallel worker floods

Default `kanban.max_spawn: 7` spawns all ready tickets in parallel. When workers crash, this means 7× crash → 7× auto_block → 7× repromote per tick, generating notification storms. Set to 1 for sequential execution:
```bash
hermes config set kanban.max_spawn 1
```

### 3. Gateway restart cuts the restarting session

`systemctl restart hermes-gateway` kills the gateway process — including the Telegram connection that issued the restart command. The command times out. Accept this — after restart, the connection re-establishes and the conversation continues normally.

## Known Pitfalls

### 1. Quality gates MUST raise StepError on failure — do NOT return `{"passed": false}`

The consumer loop ONLY stops on exceptions. If a quality gate step returns a JSON dict like `{"passed": false, "failures": [...]}`, the consumer treats it as success and continues to the next step (MinIO upload, Git push), pushing garbage notes.

**Rule:** Every quality gate that detects failure MUST `raise StepError(...)`. The return value is only for the `passed: true` case. Never return a failure-flagging dict from a step.

### 2. Book synthesis — follow CONTEXT.md progressive design

The CONTEXT.md (lines 214-222) specifies **progressive chunk-by-chunk synthesis**, not group-summarize-then-combine:

```
chunk 1 → write partial note → chunk 2 + previous note → append → ... → final polish
```

Context stays clean: current chunk ~50K tokens + growing note ~20K. The note GROWS naturally across chunks — the LLM appends to existing content rather than compressing everything into one final call. This produces substantially longer, more detailed notes.

**Do NOT** implement: regex split → summarize groups → combine summaries → single final call. That forces compression and produces one-line chapter summaries.

See `agent/pipelines/books.py` → `_chunked_book_synthesis` for the canonical implementation.

### 3. Book detection — epub vs pdf split
The detection originally returned `book` for both `.epub` and `.pdf`. But the `book` pipeline hardcodes `step_extract_epub` (ePub only) — PDFs would fail with "No ePub file found". Fixed by splitting patterns: `.epub$` → `book_epub`, `.pdf$` → `book_pdf`. Also updated `preflight_health` to handle both new platforms.

### 2. step_extract_epub/pdf didn't download remote files — ✅ FIXED (2026-06-19)
The extraction steps checked `Path(source).exists()` for local files, then fell back to `/tmp/mega_{slug}/*.epub`, then failed. Remote URLs (MinIO, archive.org) were never downloaded. Fixed: download via `mc cp` (MinIO) or `curl` (external HTTP) before extraction. Both `step_extract_epub` and `step_extract_pdf` now handle remote URLs.

### 3. preflight_health didn't cover book_epub / book_pdf — ✅ FIXED (2026-06-19)
After the detection split, `preflight_health` still only checked `platform == "book"`. `book_epub` and `book_pdf` fell through to the default `return True, ""` — harmless (books don't need cookies) but fragile. Fixed.

### 5. Instagram carousel pipeline — requirements

**Playwright:** Must be installed. `playwright install chromium` downloads Chrome for Testing (~175 MB). Without this, `BrowserType.launch` fails with "Executable doesn't exist."

**Cookie injection:** The Playwright script MUST inject cookies from `ig_cookies.txt` via `context.add_cookies()`. Without cookies, Instagram serves a login wall even with valid session cookies in the file — headless Chrome needs them explicitly injected. Parser converts Netscape format (tab-separated) to Playwright cookie dicts `{name, value, domain, path}`.

**0 slides → FAIL:** If Playwright extracts 0 slides (login wall, deleted post, private), the step MUST raise `StepError(FAIL)`, not silently succeed with empty JSON. Prevents garbage notes from being pushed.

**on_error for carousel_extract:** Set to `"fail"` — Instagram anti-bot detection makes retries pointless. If extraction fails once, it will fail every time with the same cookies.

### 6. Threads cookies — shelf life < 2 weeks

Cookies from June 6 tested on June 19 (13 days) → HTTP 302 redirect to `instagram.com/accounts/login`. Fix: re-export cookies from Chrome → upload via dashboard. Rotate before they hit 10 days old.

For Instagram, the `ig_reel_validate` step checks `grep -c sessionid >= 1` — but even with valid `sessionid`, Playwright headless may hit login walls without explicit cookie injection (see pitfall #5).
A post can pass detection (no login wall) but still have `captions: []` — the content simply isn't extractable. The quality gate correctly FAILs synthesis with "No caption text found". This is expected behavior, not a bug. Stale cookies (from June) may cause silent login walls that don't trigger the og:description check — re-export cookies from Chrome if Threads posts consistently return empty captions.

## No Hermes Carryover

May 2026 Edgee streaming bugs were Hermes-specific (HTTP/2, h11, agent loop). KB Agent calls Edgee directly via httpx — standard OpenAI-compatible endpoint. Both streaming and non-streaming supported per Edgee SDK docs. Do NOT carry Hermes conclusions to KB Agent — clean slate.

## Pitfalls

- **⚠️ "KB" is ambiguous — clarify which board.** When the user says "KB tickets" or "KB board," they may mean `kb-agent` (this board — the agent codebase) OR `knowledge-base` (content processing — Substack batches, book notes, video digests). The `knowledge-base` board has its own ticket lifecycle (researcher → reviewer). Defaulting to `kb-agent` without checking causes wrong answers. **Pattern:** when asked about "KB," check BOTH boards: `hermes kanban --board kb-agent list` AND `hermes kanban --board knowledge-base list`. If only one has recent activity, that's the one the user means. If still unclear, ask "kb-agent or knowledge-base?"

- **Verify before asserting.** When asked "is that all?" or "are you sure?", grep the code before confirming. Never answer coverage questions from memory. Run `grep register_pipeline agent/pipelines/*.py`. The user catches every omission — "t'es sûr de toi ?" means you missed something. Answer once, completely, with evidence.
- **Test URLs from vault, not skipped queues.** The Hermes vault at `/root/Documents/Obsidian Vault/Knowledge base/` contains notes with `source_url:` in frontmatter — these were successfully processed. The `/root/.hermes/queues/skipped_*.txt` files contain failed URLs (login walls, dead links). Skipped ≠ processed.
- **6 text pipelines, not 4 or 5.** web, substack_text, threads_text, instagram_post, book_epub, book_pdf. book_pdf is a separate pipeline from book_epub (uses pymupdf, not ebooklib). See `references/pipeline-registry.md` for the full map.
- **Use venv Python for systemd service.** The Hermes venv at `/usr/local/lib/hermes-agent/venv/bin/python3` has all deps. System Python lacks dotenv, flask, httpx, pyyaml. First failure: `ModuleNotFoundError: No module named 'dotenv'`.
- **Check infrastructure before acting.** Before creating services or modifying system files, verify current state: `systemctl status`, `ps aux | grep`, `ls /etc/systemd/system/<name>*`. Consult Context7 for best practices before writing unit files.
- **Clean test data before real runs.** Phase 6 leaves rickroll URLs, example.com, and httpbin.org tasks in the DB. Wipe: `systemctl stop kb-agent && rm /root/kb-agent/data/agent.db /root/kb-agent/data/logs.db && systemctl start kb-agent`.
- **CONTEXT.md is the spec — do NOT let subagents drift from it.** When kanban workers implement pipeline features, they operate from ticket descriptions, not the full CONTEXT.md. The result can be a completely different architecture (e.g., group-summarize-then-combine instead of progressive synthesis). Always cross-reference the implementation against CONTEXT.md after merge. If a feature has a design in CONTEXT.md, the ticket must reference the relevant lines.

- **Code review: verify every claim by reading the codebase. Do NOT invent.** When the user asks "check if X is implemented" or "compare the code against the spec", you must grep/read the actual code files for each claim — never assert from memory or assumption. The user catches every fabricated claim ("tu inventes", "t'as vraiment checké la codebase ?"). Pattern: (1) extract every verifiable claim from the spec, (2) for each claim, grep the codebase to confirm or deny, (3) list only claims with code evidence. This applies to all codebases, not just kb-agent.

**Critical: after context compaction, re-read all files.** Compaction summaries are lossy and often contain claims the previous agent fabricated without verification. If you arrive mid-session with a compaction handoff, assume every file-reference claim in the summary is suspect. Re-read the actual files before repeating any claim. The user's "t'invente encore ?" means you're repeating a fake claim from compaction. Pattern: when you see a compaction note at the top, do NOT trust any code claims in it — grep/read fresh.

**🚫 NEVER create kanban tickets from unverified audit claims.** When asked to create tickets from a drift audit or spec-vs-code comparison, verify EVERY claim against the actual code BEFORE running `hermes kanban create`. Pattern that burns: (1) extract claims from CONTEXT.md, (2) create 10 tickets, (3) user asks "t'as vraiment checké ?", (4) verification reveals 5/10 false, (5) reviewers already coded on false tickets → useless PRs, (6) PR-URL-COMMENTS stuck in DB blocking respawn, (7) must close tickets + PRs + delete DB comments. Correct pattern: verify → cross out false claims → create tickets ONLY for confirmed issues. See `references/code-review-2026-06-19.md` — the 5 false claims (See Also, chunk threshold, LLM tools, quality gate ValueError, threads text) are documented there as anti-patterns.

**PR cleanup after closing false tickets:** When false tickets generated PRs that must be closed, also delete the `pr_url` comments from the kanban DB to stop the watchdog from flagging `PR-URL-COMMENTS(N)`. Run: `sqlite3 /root/.hermes/kanban/boards/kb-agent/kanban.db "DELETE FROM task_comments WHERE task_id='<id>' AND body LIKE '%pr_url%'"`. Then close PRs: `gh pr close <N> --comment "Closed: false drift claim" --delete-branch`.

**Two watchdog PR-URL patterns:** (1) `PR-URL-COMMENTS(N)` — a task comment contains `pr_url` in its JSON body (e.g., `"pr_url": "https://github.com/..."`). Fix: delete the comment from `task_comments`. (2) `PR-URL-IN-BODY` — the ticket's `body` field itself contains a PR URL. Fix: either complete the ticket (if PR is merged/done) or edit the body to remove the URL. The watchdog scans both locations.

**Rebasing stale PRs with merged intermediate commits:** When a PR branch has N commits but only the last one is relevant (earlier commits were merged differently), `git rebase origin/main` will conflict on the stale commits. Solution: `git rebase --skip` to drop commits already upstream. Only the last commit matters. Then `git push --force-with-lease`. Example: `feat/smell-start-consumer` had 3 commits, first 2 were `archive_llm_call` and test fixes already merged via other PRs — skipping them left only the `start_consumer()` deletion.

**CONTEXT.md → code audit workflow.**

## Systemd Service

KB Agent runs as `systemctl start kb-agent`. Service file at `/etc/systemd/system/kb-agent.service`. See `references/systemd-service.md` for the full unit and deployment commands.

To access the dashboard: `http://vmi3304846.tail5c02a1.ts.net:5000/dashboard` (Tailscale-only, port 5000).
