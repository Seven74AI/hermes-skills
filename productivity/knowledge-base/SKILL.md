---
name: knowledge-base
description: "Manage a personal knowledge base in the Obsidian vault: capture and structure information"
version: 1.12.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [knowledge-management, research, notes]
    related_skills: [obsidian]
---

# Knowledge Base

Personal knowledge base in the Obsidian vault at `Knowledge base/`.
Categorize with Obsidian `tags` in frontmatter.
Uses the `obsidian` skill for file operations. Git push after each note.

## Content sources

### YouTube

Pipeline: download → diarize → transcribe → summarize → archive with faster-whisper `large-v3`.

- Phase A: `references/pipeline-youtube.md`
- Phase B: `references/resume-prompt.md` + `references/youtube-note-template.md`
- Kanban pattern: same two-phase flow as Mega (`references/pipeline-mega.md`)

### Threads

`references/pipeline-threads.md` — detect text vs video via `video_versions` in JSON (NOT `og:type`), session cookies required, content gate (skip login-wall and og-only posts). 7 known pitfalls documented in the pipeline reference.

- Cookies: `/root/.hermes/cookies/threads_cookies.txt` (export from Chrome Profile 5)
- `video_versions` present → `researcher-videos` (video, diarize). No `video_versions` → `researcher` (text).
- **Never create a note from `og:description` alone** — it's a preview, not the post. Skip inaccessible posts.
- yt-dlp does NOT support Threads. Use curl + cookies for extraction.
- Note prefix: `threads-`
- **Phase 0 — Pre-ticket detection** (`references/pipeline-threads.md`): run content-type detection BEFORE creating kanban ticket. `video_versions` present → `--assignee researcher-videos`. Absent → `--assignee researcher`.
- `media_type=19` is an Instagram video cross-post (NOT a carousel). Always check for `video_versions` regardless of outer type. See `references/threads-media-types.md`.
- Dedup: check vault for existing `source_url` before creating a note

### Instagram

Route by URL path:

| Path | Pipeline |
|------|----------|
| `/reel/` | `references/pipeline-instagram.md` |
| `/p/` | `scripts/ig-carousel-extract.py` (first 2 slides; manual screenshots for slides 3+) |

When the user's description disagrees with the URL path, confirm the type first.

- Cookies: validate `sessionid` before Reel downloads (see `references/edge-cases.md`)
- Metadata: `references/instagram-extraction.md`
- Vision: `references/vision-pitfalls.md`

### Video (all platforms)

`references/video-pipeline-global.md` — background execution, mandatory diarization (pyannote), `large-v3` transcription, canonical scripts, rate limits, transcription persistence.

### Books (ePub/PDF)

`references/books-extraction.md` — extract text, read chapter by chapter, synthesize. Template: `templates/book-note-template.md`. Upload source to MinIO (see `references/minio-upload.md`).

**PDF pre-flight: 3-tier quality check mandatory.** The binary `< 500 chars` scan check is NOT sufficient for pre-19th-century PDFs. Many old scans have an OCR layer with millions of chars but the text is degraded (long-s → f, garbled headers). Always run the full quality scoring from `book-extraction` skill → `references/ocr-scanned-pdfs.md` before creating tickets. Score < 80 → queue for fresh OCR, do NOT ticket.

**Scanned PDFs (0 chars pymupdf):** do NOT create kanban tickets. Upload to MinIO, append to `/root/.hermes/queues/ocr_books.txt`, skip. marker-pdf = 8 GB RAM → OOM on 11 GB server. Queue for later processing on better infra.

### Generic web (articles, blogs, reference sites)

`references/pipeline-web.md` — Firecrawl extraction → deep analysis → MinIO archive → Obsidian note. Any website without a dedicated pipeline. Includes Substack, blogs (darioamodei.com), medical references (VIDAL), and other long-form web content.

- **MinIO mandatory.** All web content is ephemeral — pages disappear, sites shut down. Raw markdown from Firecrawl must be uploaded to the `knowledge-base` bucket and referenced via `minio:` in the note frontmatter. See MinIO Architecture below for bucket structure and URL conventions.
- **Deep treatment always.** No light/surface template. Every note gets section-level analysis, critical context, and nuance assessment — regardless of source or length. The KB is a thinking tool, not an aggregator.
- Dedup: check vault for existing `source_url` before processing
- Firecrawl: `http://localhost:3002/v2/scrape` with `formats: ["markdown"]`

### Substack

`references/pipeline-substack.md` — extraction Firecrawl, nettoyage markdown, note Obsidian. Pas besoin de cookies pour les articles publics. **Also serves as the generic web article pipeline** for non-Substack sites (blogs, essays, technical references, news articles).

- Dedup: check vault for existing `source_url` **before creating kanban ticket** (Phase -2).

### Web search

## MinIO Architecture

MinIO runs on the VPS (`vmi3304846`) on port 9000, accessible via Tailscale VPN at `http://vmi3304846.tail5c02a1.ts.net:9000`. All KB source content lives in the **`knowledge-base`** bucket.

### Bucket structure

```
knowledge-base/
  articles/     → raw markdown from Firecrawl (Substack, blogs, web pages)
  reels/        → Instagram Reel videos (.mp4)
  videos/       → YouTube videos (.mp4)
  threads/      → Threads content (text posts, video)
  books/        → ePub and PDF book sources
  transcripts/  → diarized transcriptions (.txt)
  audio/        → extracted audio tracks
```

### URL convention in note frontmatter

Always use the full Tailscale FQDN so files are reachable from MacBook, iPhone, or any device on the Tailnet:

```yaml
minio: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/articles/<slug>.md
```

Never use the `minio://` shorthand — it's not resolvable by other devices on the Tailnet.

### Legacy `source_file:` field

Some older notes use `source_file:` instead of `minio:`. The content IS already archived on MinIO — the field just needs standardizing to `minio:` with the proper Tailscale URL. See Backfill below.

### MinIO CLI

Configured as the `minio` alias in `mc`:
```bash
mc ls minio/knowledge-base/
mc cp <file> minio/knowledge-base/articles/<slug>.md
```

**Pitfall — check existing buckets before creating new ones.** The `knowledge-base` bucket already has a well-organized folder structure (`articles/`, `reels/`, `videos/`, `books/`, `transcripts/`, `audio/`). Never create a new bucket (like `hermes-kb`) without first checking `mc ls minio/`. If a bucket already exists with the right structure, use it. New content goes into the existing folders, not a parallel bucket.

## Backfill

When archiving was not done at note creation time, notes lack the `minio:` field. Backfill procedure:

1. **Identify gaps:** search vault for notes with `source_url` but no `minio:` field (and no `source_file:` pointing to MinIO)
2. **Categorize by content type:** Reels need video download, posts need image extraction, text needs Firecrawl markdown. Archive the actual content, not the page wrapper.
3. **Process by type, easiest first:**
   - **Books with `source_file:`** → just rename field to `minio:`, content already archived
   - **Text (Substack, web)** → Firecrawl → `knowledge-base/articles/`
   - **Threads** → needs cookies, Firecrawl JS rendering → `knowledge-base/threads/`
   - **Instagram Posts** → needs cookies, download images + OCR → `knowledge-base/articles/`
   - **Instagram Reels** → needs cookies, yt-dlp video download → `knowledge-base/reels/`
   - **YouTube** → re-download video or archive existing transcript → `knowledge-base/videos/`
4. **One note per Git commit.** Atomic, rollback-safe.
5. **Idempotent.** If URL is dead (404), skip and log — don't block the batch.

## Kanban batch processing

When the user drops URLs, create tickets on the **`knowledge-base`** board.
The `default` board is a sandbox only — never create KB tickets there.
See `references/kanban-ticket-template.md` and `references/kb-board-plan.md`.

- 5 URLs per ticket; chain with `--parent`
- 2 video transcriptions per worker session (`video-pipeline-global.md`)
- `--max-runtime 3600`
- Assignee: `researcher` (text/image) or `researcher-videos` (video)
- Worker setup: `references/researcher-profile-setup.md`
- Prefix tickets with `KB:` in the title for clarity

## Cookie handling

All pipelines that require cookies (YouTube, Instagram, Threads) must run a pre-flight validation before processing. If validation fails, **skip the URL, do not block the ticket**:

```bash
echo "URL" >> /root/.hermes/queues/skipped_<platform>.txt
```

Queue files: `skipped_yt.txt`, `skipped_threads.txt`, `skipped_ig.txt`, `skipped_substack.txt` under `/root/.hermes/queues/`.

When the user refreshes cookies and says "relance": validate cookies → load `knowledge-base` skill → process queue file from the top. Full procedure: `references/edge-cases.md` (Cookie validation section).

**Protect cookie files from yt-dlp overwrites.** `yt-dlp --cookies FILE` reads AND writes back the cookie jar after every download. Session cookies (`sessionid`) with no expiry get saved with `expires=0`, then treated as expired on next load. This silently breaks all subsequent Instagram/YouTube downloads. After the user exports fresh cookies, make the file read-only:

```bash
chmod 444 /root/.hermes/cookies/ig_cookies.txt
chmod 444 /root/.hermes/cookies/yt_cookies.txt
```

The worker will still be able to read cookies but yt-dlp cannot overwrite them.

## When to add a note

User shares content → extract, verify when possible, save.

If `web_extract` is unavailable: `curl` + Googlebot UA (`references/instagram-extraction.md`) or yt-dlp for Reel transcripts (`references/pipeline-instagram.md`).

## Adding a note — workflow

1. **Load obsidian skill** (`skill_view(name='obsidian')`)
2. **Extract** core claim, fact, or insight
3. **Language:** content in source language; section labels per template (English)
4. **Verify** when possible — search, cross-reference
5. **Tag** via frontmatter (`tags`)
6. **Create** `Knowledge base/<slug>.md` via `OBSIDIAN_VAULT_PATH`
7. **Upload raw source to MinIO** — mandatory for all content. See MinIO Architecture below for bucket structure. Text sources → `knowledge-base/articles/<slug>.md`. Reels → `knowledge-base/reels/<slug>.mp4`. Videos → `knowledge-base/videos/<slug>.mp4`. Threads → `knowledge-base/threads/<slug>.<ext>`. Books/PDFs → `knowledge-base/books/<slug>.<ext>`. Transcripts → `knowledge-base/transcripts/<slug>.txt`. Add `minio: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/<folder>/<slug>.<ext>` to note frontmatter.
   - **Verify each upload** immediately — `mc ls minio/knowledge-base/<folder>/<file>` for every file referenced in the note frontmatter. If a file is missing, re-upload before pushing.
8. **Push:** `cd "$OBSIDIAN_VAULT_PATH" && git add -A && git commit -m "add: <slug>" && git push`
9. **Find related notes** — BEFORE writing See Also, search the vault for notes related to your topic. Use `search_files(target='content', pattern='<keyword1|keyword2>', path='$OBSIDIAN_VAULT_PATH/Knowledge base/')` with keywords from your note's core topics. Then for each candidate, verify the slug exists with `grep -rl`. Only link to notes that actually exist and are genuinely related. If no existing note is relevant, omit the See Also section entirely.
10. **Verify wikilinks** — BEFORE pushing, grep every `[[link]]` to confirm it resolves. Ghost wikilinks are the #1 quality failure.
11. **Confirm** what was saved — re-read the note, verify all `minio://` references resolve (`references/minio-integrity.md`), check diarization was applied (transcripts should have speaker labels, not just `?`)

Edge cases (cookies, music-only Reels, delegation): `references/edge-cases.md`

## Template (deep treatment standard)

All notes follow the same depth standard as `templates/book-note-template.md`. The lightweight "Claim / Context / Nuances" template is **deprecated** — it produces surface-level journalism, not KB-worthy analysis.

Required depth for every note, regardless of source or length:

```markdown
---
date: YYYY-MM-DD
source: <platform/author, date>
source_url: <optional URL>
minio: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/<folder>/<slug>.<ext>
confidence: verified | plausible | emerging | debunked | untested
tags: [tag1, tag2, tag3]
---

# Title

## Summary
3-5 sentences. The essential up top. Why this matters, what's the core argument.

## Key Claims / Points
≥4 specific claims with direct quotes (format `>`) from the source. Each claim gets:
- The claim itself (what is being asserted)
- A direct quote as evidence
- Analysis and context (why it matters, what it implies)

### 1. Claim title
> « direct quote from the source »

Analysis.

### 2. Claim title
...

## Section-by-Section / Thematic Analysis
If the content is structured (essay, article with sections, book chapters), break it down section by section. This is the DOMINANT section — longer than Key Claims + Critical Analysis combined. The reader should understand the full arc of the source.

### Section/Chapter 1: <Title>
What it argues, key evidence, notable quotes.

### Section/Chapter 2: <Title>
...

## Context
Who wrote this, why now, what's their position in the debate. Conflicts of interest, institutional biases, funding sources. 1-2 paragraphs.

## Critical Analysis
What's genuinely new vs restating? What's omitted? What's the self-interest angle? Methodological or factual issues. Keep shorter than the thematic analysis — the reader needs to understand the content before your critique.

## Nuances
What the source omits, exaggerates, or distorts. Limitations. Tone (polemical, academic, popularizer).

## Reliability
✅ verified | ⚠️ plausible | 🔬 emerging | ❌ debunked | ❓ untested

Detailed justification — why this confidence level.

## Sources
- Original source (full citation)
- Consulted sources (verification, cross-reference)
- Raw source archived: `minio:` URL (see frontmatter)

## See Also
- [[existing-note-slug]] — verified with `grep -rl` before linking
- Only link to notes that actually exist. No invented wikilinks.
```

**Red flag: if the note is shorter than the book-note-template, it's too shallow.** Books get chapter-level depth. Articles get section-level depth. The standard is the same — only the scale differs.

**Size target:** 15 000-25 000 chars for long-form (>5000 words). Proportionally less for short-form. A note under 5 000 chars for a long-form source means you did not read enough.

**Read the ENTIRE source.** Never rely on `web_extract` summaries alone — use Firecrawl full markdown extraction, save to `/tmp/`, and read through completely before writing the note. The reading scales with source size:

| Source size | read_file passes needed | Strategy |
|---|---|---|
| <50K chars (<300 lines) | 2-3 passes | Read all |
| 50K-150K chars (300-1000 lines) | 5-8 passes | Read in 200-line chunks, parallel reads where possible |
| >150K chars (>1000 lines) | 8-15+ passes | Read systematically in 200-line chunks, section by section. Do NOT start writing until you've read EVERY section. Count the source sections/parts BEFORE writing and verify your note covers every one — no exceptions. |

**Pitfall — writing a note before finishing the read.** The most common failure mode: you read 3-4 sections, think you have enough, write the note, and miss 70% of the content. The user WILL notice — they'll say "ya une tonne d'info manquante" or "j'ai toujours pas l'impression que ça parle de tout." This happened with a 234K-char (2335-line) source where 3-4 passes covered only ~800 lines. The fix: after writing the note, run a coverage check — `grep -c "^##" /tmp/source_raw.md` vs `grep -c "^##" note.md` — to catch missing sections before pushing. For unstructured sources, skim every 50th line of the raw file to spot sections you didn't cover.

## Confidence levels

| Level | Meaning |
|-------|---------|
| ✅ verified | Confirmed by multiple solid sources |
| ⚠️ plausible | Logical, some sources, no consensus |
| 🔬 emerging | Preliminary, promising but limited |
| ❌ debunked | Contradicted by available evidence |
| ❓ untested | No source found |

## Retrieving information

When the user asks "qu'est-ce qu'on a sur X ?":
1. Load obsidian skill
2. `search_files(target='content', pattern='<keyword>', path='<vault>/Knowledge base/')`
3. Present findings grouped by confidence
4. Offer to research and add if nothing matches

Batch inventory ("titre des done"): `references/kanban-ticket-template.md`

## Working principles

- **Deep treatment always.** Every note gets section-level analysis, critical context, and nuance assessment. No surface summaries — the KB is a thinking tool, not an aggregator. Treat every article, post, or page with the same depth as a book chapter. If the content is too thin for deep analysis, it's not KB-worthy.
- **Archive raw sources on MinIO.** The web is ephemeral — articles disappear, sites shut down, URLs 404. Every source must have its raw content uploaded to the `knowledge-base` MinIO bucket and referenced in the note frontmatter. Text sources go to `knowledge-base/articles/`, videos to `knowledge-base/reels/` or `knowledge-base/videos/`, Threads to `knowledge-base/threads/`, books to `knowledge-base/books/`. The `minio:` field uses the full Tailscale URL: `http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/<folder>/<slug>.<ext>`. The raw archive is never read by the LLM unless explicitly requested — it's insurance against link rot. Tokens are not consumed by storage: content is piped from Firecrawl/curl to disk to MinIO via `mc cp`, bypassing the model entirely.
- **Never launch without confirming the plan.** Present what you're about to do, wait for the user's go. They hate when you start executing unilaterally ("T'es fatiguant à partir tout seul"). This applies to backfill, batch operations, and any multi-step pipeline work.
- Complete every pipeline step — the user will wait for quality
- **Diarization is mandatory for ALL video content** (YouTube, Instagram Reels, Mega). Use canonical `scripts/diarize.py` + `scripts/transcribe.py`. Never skip diarization — even for apparent monologues (guest intros, Q&A segments, off-camera remarks are common in "solo" videos).
- Verify every upload and reference: check MinIO files exist (`references/minio-integrity.md`), confirm diarization was applied (speaker labels must not be `?`), then push.
- Document discoveries in skill files (skills over memory)
- Show non-trivial commands before running them
- **Wait for user go-ahead before launching batch operations.** Multi-step workflows (backfill, bulk patches, pipeline runs) require explicit confirmation. Never chain phases without the user saying "go." If the user says "attends" or "t'es fatiguant à partir tout seul," you launched too early — present the plan, then stop.
- **Grill when asked.** When the user says "grill me," they want adversarial questioning — not politeness, not "makes sense." Challenge assumptions, find holes, push back hard. This is a deliberate decision-quality check, not aggression.
- **Pipeline debugging: diagnose first, then confirm, then fix.** When identifying pipeline problems, present the evidence and root cause to the user BEFORE applying fixes. The user will verify on their end and may correct the diagnosis. Do not rush to patch — wait for confirmation, then apply the fix.
- **Keep skill docs minimal.** Reference files delegate to the main skill or umbrella reference — don't duplicate pipeline steps across files. If a procedure is already covered by loading `knowledge-base`, just say so.
- **Happy path only.** Pipeline references must contain only the workflow: what to do, in what order, with what commands. No edge cases, failure modes, deprecated methods, known pitfalls, "✅ FIXED" markers, or bad-path pollution. Those belong in the operator's journal, not in worker-facing skill files.
- **Sync profiles after editing skill files.** Worker profiles (`researcher`, `researcher-videos`, `planner`, `reviewer`, `coder`, etc.) have their own copies of the skill directory. After creating a new skill, editing any `SKILL.md`, reference, template, or script, run `scripts/sync-to-profiles.sh`. It syncs **all** productivity skills to **all** profiles that have a `skills/productivity/` directory — not just `knowledge-base` to `researcher`. Workers crash-loop with `Error: Unknown skill(s)` when a ticket references a skill via `--skill` that hasn't been synced to their profile.
  - **Verify sync succeeded.** After running, check that a profile has the full skill: `ls <profile>/skills/productivity/knowledge-base/` must show `SKILL.md` + `references/` + `templates/` + `scripts/`. If only `SKILL.md` appears, the sync flattened the skills — check `scripts/sync-to-profiles.sh` line has `$dest/$skill_name/`, not just `$dest/` (bug fixed 2026-06-11).

## Reference index

| Topic | File |
|-------|------|
| Substack | `references/pipeline-substack.md` |
| Generic web | `references/pipeline-web.md` |
| Edge cases | `references/edge-cases.md` |
| Video global rules | `references/video-pipeline-global.md` |
| YouTube pipeline | `references/pipeline-youtube.md` |
| Threads pipeline | `references/pipeline-threads.md` |
| Threads media types | `references/threads-media-types.md` |
| Instagram pipeline | `references/pipeline-instagram.md` |
| Mega / external video | `references/pipeline-mega.md` |
| Video summarization | `references/resume-prompt.md` |
| YouTube note template | `references/youtube-note-template.md` |
| Books | `references/books-extraction.md` |
| Kanban tickets | `references/kanban-ticket-template.md` |
| Worker profiles | `references/researcher-profile-setup.md` |
| MinIO | `references/minio-storage.md`, `references/minio-upload.md`, `references/minio-integrity.md` |
| Dependencies / fresh install | `references/dependencies.md`, `references/fresh-install-checklist.md` |
| Fact-checking | `references/fact-check-workflow.md` |
| Web search | `references/web-providers.md` |
| **KB board plan** | `references/kb-board-plan.md` |
| **Backfill** | `references/backfill.md` |

Vault path: `OBSIDIAN_VAULT_PATH` (from `~/.hermes/.env`). Git sync: obsidian skill `references/git-sync.md`.
Persist transcripts and source files to MinIO
