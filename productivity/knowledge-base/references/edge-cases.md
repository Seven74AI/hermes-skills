# Edge Cases

Load when the standard workflow needs a branch. Each item states what to do.

## Instagram URL routing

| Path | Action |
|------|--------|
| `/reel/` | Video pipeline — `pipeline-instagram.md` |
| `/p/` | Carousel — `scripts/ig-carousel-extract.py` |

When the user's label disagrees with the URL path, confirm before proceeding.

## Cookie validation

All pipelines that require cookies must run a pre-flight check before processing each URL. If the check fails, **do not block the ticket** — skip the URL and continue.

### Skip + notify workflow

When cookie validation fails for a URL:

```bash
# 1. Append URL to the platform's skip queue
echo "URL_HERE" >> /root/.hermes/queues/skipped_<platform>.txt

# 2. Send Telegram notification to home channel
#    (use send_message tool, target=telegram)
#    "⚠️ URL skippée — cookies <platform> invalides : URL_HERE"
```

Queue files:
- `/root/.hermes/queues/skipped_yt.txt` — YouTube
- `/root/.hermes/queues/skipped_threads.txt` — Threads
- `/root/.hermes/queues/skipped_ig.txt` — Instagram

One URL per line. When cookies are refreshed, process the queue file.

### Relaunching skipped URLs

When the user says "cookies updated, relance" or similar:

1. **Validate cookies first** — run the platform-specific check below
2. **If still invalid** → tell the user exactly which cookie is missing, do NOT create tickets
3. **If valid** → load the full `knowledge-base` skill and process the queue file **from the top** — the skill handles batching, chaining, Phase 0 detection, assignee selection, and dedup
4. Clear the queue file after all tickets are created

### Instagram

Before Reel downloads:

```bash
grep -c sessionid /root/.hermes/cookies/ig_cookies.txt   # must be ≥ 1
```

A file with only the Netscape header has no cookies — re-export from Chrome using a Reel URL.

Use cookies for every Reel in a batch (Instagram may allow the first 1–2 without auth, then require login).

### YouTube

Before creating or processing a YouTube ticket, run a **two-tier** validation.
Cookies can be structurally valid (all token fields present) but still rejected
by yt-dlp due to **IP fingerprinting** — YouTube cross-checks the request IP
against the IP that created the cookies (the user's Mac browser). A successful
oembed call proves cookie validity; a yt-dlp rejection after that proves the
IP mismatch.

#### Tier 1: Structural check (file integrity)

```bash
# Check LOGIN_INFO is present (the session cookie that proves auth)
grep -c "LOGIN_INFO" /root/.hermes/cookies/yt_cookies.txt   # must be ≥ 1
# Also verify critical cookies
grep -cP "^(SAPISID|__Secure-3PSID|LOGIN_INFO)" /root/.hermes/cookies/yt_cookies.txt   # must be ≥ 3
```

If any are missing: cookie export is incomplete. The user must re-export from
Chrome Profile 5 while **actively logged into youtube.com**.

#### Tier 2: Functional check (IP fingerprinting)

```bash
# Test with YouTube oembed API — lightweight, rarely blocked
COOKIE_HEADER=$(python3 -c "
lines = [l.strip().split('\t') for l in open('/root/.hermes/cookies/yt_cookies.txt') if not l.startswith('#') and l.strip()]
cookies = [f'{p[5]}={p[6]}' for p in lines if len(p) >= 7 and '.youtube.com' in p[0]]
print('; '.join(cookies))
")
curl -sL --max-time 10 -H "Cookie: $COOKIE_HEADER" \
  "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=VIDEO_ID&format=json"
```

| oembed result | yt-dlp result | Diagnose |
|---------------|---------------|----------|
| ✅ Title + author returned | ❌ "Sign in to confirm you're not a bot" | **IP fingerprinting** — cookies are valid but server IP ≠ browser IP. Must run yt-dlp on the Mac directly with `--cookies-from-browser "chrome:Profile 5"` |
| ❌ Empty / error | ❌ "Sign in to confirm..." | **Cookies expired** — re-export from Chrome |
| ✅ Title + author returned | ✅ Works | Ready to process |

**When IP fingerprinting is the blocker:** the URL goes into the skip queue
as usual. Recovery requires running `yt-dlp --cookies-from-browser "chrome:Profile 5"`
on the Mac itself (via Tailscale SSH), then scp'ing the resulting files to
the server. Do NOT create a kanban ticket — the worker will hit the same bot wall.

#### Tier 3: yt-dlp version

Nightly builds sometimes carry fresher anti-detection patches than the PyPI stable.
Check version first; nightly is only worth trying when oembed works but yt-dlp fails.

```bash
# Current: yt-dlp --version
# Nightly available at: yt-dlp/yt-dlp-nightly-builds (GitHub)
pip install "https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/latest/download/yt-dlp.tar.gz" --force-reinstall
```

If even the nightly (with valid cookies) is rejected, the problem is definitively
IP fingerprinting — not cookie freshness, not yt-dlp version. Stop and flag for
Mac-side execution.

**Pre-flight pattern:** run Tier 1 + Tier 2 checks BEFORE creating a kanban
ticket. If cookies are invalid, skip the URL — do not create a ticket that will
just block or burn 4+ runs as the worker retries.

### Threads

Before creating or processing a Threads ticket:

```bash
# Check cookies file exists and is non-trivial
test -s /root/.hermes/cookies/threads_cookies.txt || echo "MISSING"
# Quick auth test — fetch a known post and verify we got captions, not a login wall
curl -sL -b /root/.hermes/cookies/threads_cookies.txt \
  -A "Googlebot/2.1" \
  "https://www.threads.com/@threads/post/DGxHGfxszuc" 2>/dev/null | \
  grep -c '"caption":{"text":"'   # must be ≥ 1 (login wall returns 0)
```

If the file is missing or the auth test returns 0 captions: cookies are expired or missing. Export from Chrome Profile 5 using a Threads URL.

## Music-only Reels

When transcription segments total < 50 characters:

1. Use caption/metadata via Googlebot UA as primary content
2. Annotate the note: `⚠️ Music-only Reel — analysis based on caption text`
3. Proceed to note creation with caption content

## Kanban parent/child delegation

When a URL moves to a child ticket:

1. Child ticket owns that URL only
2. Parent ticket **body** updated — delegated URL removed or marked `DELEGATED → child <id>`
3. Parent comment + handoff.md track `DONE` / `DELEGATED` / `TO-DO`
4. Resuming parent: read comments and handoff before the next URL

Full template: `kanban-ticket-template.md` (Parent/child delegation).

## Section labels

Content follows source language. Section headers follow the template — English (`Summary`, `The Claim`, `Context / Analysis`, `See Also`).

## Note location

Save at `Knowledge base/<slug>.md`. Categorize with `tags` in frontmatter.

## marker-pdf install

After installing `marker-pdf`, re-pin hermes-agent packages per `dependencies.md`.

## Transcription persistence

Short Reels (≤60s): embed in note. Long videos (>2min): upload to MinIO.
Details: `video-pipeline-global.md`.
