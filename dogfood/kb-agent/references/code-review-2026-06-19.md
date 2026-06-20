# Code Review — 2026-06-19

Full codebase review of `/root/kb-agent` (6867 lines, 18 `.py` files).

## Verified Bugs (4)

| # | File | Line | Issue |
|---|------|------|-------|
| 1 | `run.py` + `consumer.py` | 163, 126, 220 | Triple orphan recovery — `_recover_orphans()` runs 3× at startup |
| 2 | `run.py` | 188 | `_kb_shutdown` dead code — set but never read |
| 3 | `run.py` | 194-199 | Flask shutdown broken — `werkzeug.server.shutdown` only in dev |
| 4 | `books.py` | 840 | Book quality gate raises `StepError(RETRY)` → consumer adds 5 retries |

## Verified Code Smells (5)

| # | File | Issue |
|---|------|-------|
| 5 | `streaming.py` | 196 lines dead — `run_with_streaming()` never called |
| 6 | `db.py:296` | `archive_llm_call()` never called — table `llm_archives` empty |
| 7 | `rotate_logs.py` | Not scheduled — no cron, no integration |
| 8 | 4 pipelines | MinIO + Git push duplicated in threads/instagram/books/youtube — `archival.py` unused |
| 9 | `consumer.py:436` | `start_consumer()` zombie — creates its own thread, `main()` ignores it |

## False Claims from Earlier Audit (10-ticket drift)

The initial audit produced 10 tickets. 5 were false — created without verifying against actual code:

| Ticket | Claim | Reality |
|--------|-------|---------|
| `t_ea9c5b41` | See Also absent | `see_also.py` imported by all 5 pipelines |
| `t_48ff2e77` | Chunk threshold 80K | `CHUNK_TOKEN_THRESHOLD = 50_000` in `web.py:30` |
| `t_cb878ee3` | LLM sans tools | `LLMClient.call()` accepts `tools: list[dict]` |
| `t_06caa051` | Quality gate ValueError → double-retry | Raises `StepError(FAIL)`, not `RETRY` |
| `t_91a82b90` | Threads text ne raise pas | Raises `StepError(FAIL)` at `threads.py:1002` |

**Root cause:** Audit extracted claims from CONTEXT.md but never verified against code. Reviewers coded on false tickets → PR #17, #20 created and closed.

## Lessons

1. **Never create tickets from unverified audit claims.** Verify every claim with `grep`/`read_file` before running `hermes kanban create`.
2. **After closing false tickets:** delete `pr_url` comments from kanban DB + close associated PRs.
3. **Kanban workers:** `--skill kb-agent` only works for default profile. `coder` profile needs `--skill knowledge-base` only.
4. **`max_spawn: 1`** prevents parallel crash floods.
