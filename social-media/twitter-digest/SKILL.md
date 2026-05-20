---
name: twitter-digest
description: "Automated Twitter/X list monitoring: daily digests → Discord + Notion + GitHub Pages with triple-tag categorization (Theme/Signal/Source). NO summaries — raw tweets only."
version: 2.2.0
author: Hermes Agent
license: MIT
platforms: [linux]
prerequisites:
  commands: [xurl, git, curl]
  env_vars: [NOTION_API_KEY, GITHUB_TOKEN]
metadata:
  hermes:
    tags: [twitter, x, digest, monitoring, cron, notion, discord]
    related_skills: [xurl, notion]
---

# Twitter Digest — Automated List Monitoring

Monitor Twitter/X lists daily: fetch new tweets, categorize with a **triple-tag system** (Theme / Signal / Source), store in Notion, deliver to Discord.

**CRITICAL RULE: NO summaries, NO paraphrasing.** The user wants the tweet text verbatim. Do not interpret, do not annotate, do not add "Why it matters." Just the tweets, tagged and grouped.

**CRITICAL RULE: Include reply context.** When a tweet is a reply (text starts with @username or conversation_id != id), fetch the parent tweet via `xurl read PARENT_ID` and display both together as a thread. Without the parent, replies are meaningless.

**CRITICAL RULE: Extract media.** Pull images and videos from tweet entities (entities.urls with media_key or display_url containing pic.x.com). Include media URLs in the JSON so the GitHub Pages site can render them inline.

## When to Use

- Monitoring curated Twitter lists for signal
- Daily digests delivered to Discord + archived in Notion
- Any "fetch tweets → tag → deliver" workflow

## Pipeline

```
xurl list tweets → strip RTs → detect replies + fetch parents → extract media → tag each tweet (Theme+Signal+Source) → group by Signal → Discord + Notion + GitHub Pages
```

## Prerequisites

1. **xurl** installed and authenticated (`xurl auth status` shows app with OAuth2)
2. **Notion** integration token in `$NOTION_API_KEY` (source ~/.hermes/.env)
3. **GitHub** token with repo+pages scope in `$GITHUB_TOKEN` (source ~/.hermes/.env)
4. **Discord** channels created, Hermes gateway running
5. **X API credits**: $5 minimum at https://developer.x.com/en/portal/billing

## GitHub Pages

Each digest is also published to a GitHub Pages site as a Twitter-style dark-theme timeline. The site loads digest JSON from `data/` and renders tweet cards with avatars, badges, and links. Filterable by list and Signal type.

### Setup
- Repo with GitHub Pages enabled from master
- `index.html` — self-contained UI (dark theme, tabs, filter buttons)
- `data/index.json` — JSON array of filenames
- `data/YYYY-MM-DD-TYPE.json` — digest files pushed by the cron job

### push-digest.sh
Script at `/root/.hermes/scripts/push-digest.sh` that the cron job calls:
```
push-digest.sh <json_file> <type> <date>
```
Clones/pulls the repo, copies JSON, updates index.json, commits and pushes. Needs `GITHUB_TOKEN` in env.

See `scripts/push-digest.sh` for the GitHub commit/push script and `scripts/process_digest.py` for the full fetch→filter→tag→format pipeline. Cron job prompt template: `references/cron-prompt-template.md`. GitHub Pages site template: `templates/digest-site.html`.

## The Triple-Tag System

Every tweet gets 3 orthogonal tags. The user tests all 3 for a week, then picks which dimension(s) to keep.

### Dimension 1 — Theme (multi_select, 1-3 per tweet)

Domain-specific topic tags. Define 6-10 options for the list's domain.

*Dev/AI example:* Agent UX, Codex, Claude Code, TypeScript, OSS, Security, DevTools, AI Engineering — full keywords + author-domain mapping + common tagging errors in `references/dev-ai-themes.md`
*Crypto example:* Bitcoin, Trading, DeFi, Regulation, Macro, Privacy, Security, Mining

### Dimension 2 — Signal (select, exactly ONE)

What kind of information does this tweet carry?

- 🔴 **Signal** — announcement, launch, news, alpha, product release, protocol update
- 🟡 **Insight** — opinion, analysis, hot take, prediction, market observation
- 🟢 **Discussion** — reply, debate, question/answer, conversation thread
- ⚪ **Link/Ref** — sharing a link/resource without substantial original commentary

### Dimension 3 — Source (select, exactly ONE)

Who is speaking and in what context?

- **Builder** — sharing their own work/product/project/protocol
- **Curator** — sharing a link/resource from someone else
- **Analyst** — giving an opinion/analysis/prediction (not their product)
- **Community** — replying, participating in discussion

## Notion Database Setup

Create an inline database (`POST /v1/databases` with `is_inline: true`) on a parent page:

| Property | Type | Purpose |
|----------|------|---------|
| Name | title | "Month DD, YYYY" |
| Date | date | ISO date |
| Themes | multi_select | Domain tags (pre-populate options) |
| Signal | select | 🔴🟡🟢⚪ |
| Source | select | Builder / Curator / Analyst / Community |
| Tweets | number | Count of tweets in digest |

Must share the parent page with the integration via Notion UI (Connections → integration name).

## Filtering Rules

- Remove retweets (`text` starts with `RT @`)
- Remove empty/link-only tweets with zero substance
- **Keep everything else** — low-engagement lists need loose filters

## Reply Threading

When a tweet is a reply, its value depends entirely on context. Always fetch the parent:

```bash
# Detect: text starts with @username, or conversation_id != id
# Fetch parent:
xurl read PARENT_TWEET_ID
```

Include both in the JSON:

```json
{
  "is_reply": true,
  "parent": {"text": "...", "username": "...", "tweet_url": "...", "media": []},
  "reply": {"text": "...", "username": "...", "themes": ["OSS"], "signal": "🟢 Discussion", "source": "Community", "tweet_url": "...", "media": []}
}
```

On GitHub Pages, render as a thread: parent shown in a muted box, reply indented with left border. On Discord, show `↳ parent` then `↪ reply`.

## Media Extraction

Extract image and video URLs from tweet entities. In the X API list response, media appears in `entities.urls` — any url with a `media_key` field or `display_url` containing `pic.x.com`:

```python
media = []
for url in t.get('entities', {}).get('urls', []):
    if url.get('media_key'):
        media_type = 'video' if 'video' in url.get('display_url', '') else 'image'
        media.append({'url': url['expanded_url'], 'type': media_type})
```

On GitHub Pages: images rendered inline (max 300px, rounded), videos as "▶️ Watch video" links. On Discord: paste the media URL on its own line — Discord auto-embeds images.

## Discord Format

Group tweets by Signal type. Each tweet shows: @username, full text, Theme badge, Source badge.

**CRITICAL: Discord enforces a 2000-character message limit.** Build the message in a Python script with a char-counting loop — do not guess and hope it fits.

```python
CHAR_BUDGET = 1970  # leave 30 for safety margin
lines = []
char_count = 0

header = f"🗞️ **{list_name} Digest — {date}**\n{'━'*30}"
lines.append(header); char_count = len(header) + 1

for sig in signal_order:
    grp = grouped.get(sig, [])
    section = f"\n{SIG_LABELS[sig]}"
    lines.append(section); char_count += len(section) + 1
    for t in grp:
        line = f"**@{t['username']}** {t['text'][:95]}… — {theme_str} | ❤{t['likes']}|🔄{t['retweets']}"
        if char_count + len(line) + 1 > CHAR_BUDGET:
            break
        lines.append(line); char_count += len(line) + 1

footer = f"\n{'━'*30}\n📊 {len(selected)} tweets | [Web](URL)"
lines.append(footer)
```

**Quota strategy:** Reserve at least 2 tweets per Signal category before filling any single category. This prevents a single category from consuming the entire budget while leaving others empty.

**Format:**

```
🗞️ List Name — Month DD
━━━━━━━━━━━━━━━━━━━━

🔴 SIGNAL
@username "tweet text..." — Theme: X | Source: Y

🟡 INSIGHT
@username "tweet text..." — Theme: X | Source: Y

🟢 DISCUSSION / ⚪ LINKS
...

━━━━━━━━━━━━━━━━━━━━
📊 N tweets | Web: https://seven74ai.github.io/twitter-digest/
```

Keep tweets in their original language. Section headers in English.

**Working reference implementation:** See `references/discord-builder-pattern.md` for the full tested pattern with unicode quotes, char-counting loop, media URL truncation, and the Discord payload wrapper script. Copy that template — don't rebuild from scratch.

## Step 0 — Pre-Flight Auth Health Check (MANDATORY)

Before any fetch, verify the X API token is fresh. Skip this and you risk a silent pipeline failure where all 5 pages return 401.

```bash
xurl whoami
```

If this returns 401 or a JSON error object, the token has expired and the refresh chain is broken. **Stop immediately** — do not attempt to fetch tweets, process, push, or notify. Report the auth failure to the user. The fix requires browser-based OAuth re-auth (see the xurl skill troubleshooting table).

No false positives: if `whoami` succeeds, the token is fresh and the pipeline can proceed. This check also forces xurl to run its auto-refresh while the previous refresh token is still valid, preventing future staleness.

## Step 1 — Fetch Tweets

Fetch 3-5 pages (100 tweets each) to cover ~24 hours on active lists. Stop when ≥300 raw tweets or `next_token` is absent. Always request expansions for author data and metrics:

```bash
# Page 1
xurl "/2/lists/{ID}/tweets?max_results=100&expansions=author_id,referenced_tweets.id&user.fields=username,name,profile_image_url&tweet.fields=public_metrics,created_at,entities,referenced_tweets,conversation_id,in_reply_to_user_id" > /tmp/list-page1.json

# Check meta.next_token, then page 2-5 with pagination_token=...
xurl "/2/lists/{ID}/tweets?max_results=100&pagination_token={NEXT_TOKEN}&expansions=author_id,referenced_tweets.id&user.fields=username,name,profile_image_url&tweet.fields=public_metrics,created_at,entities,referenced_tweets,conversation_id,in_reply_to_user_id" > /tmp/list-page2.json
```

Without `expansions=author_id` and `user.fields=username`, the response has no usernames — only `author_id` numbers and `id`+`text`.
Without `tweet.fields=entities,referenced_tweets,conversation_id,in_reply_to_user_id`, you can't detect replies, extract media, or build reply threads.

## Step 2 — Write to Notion

```bash
source ~/.hermes/.env

# Escape markdown
ESCAPED=$(echo "$DIGEST_MARKDOWN" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d "{
    \"parent\": {\"database_id\": \"DB_ID\"},
    \"properties\": {
      \"Name\": {\"title\": [{\"text\": {\"content\": \"Month DD, YYYY\"}}]},
      \"Date\": {\"date\": {\"start\": \"YYYY-MM-DD\"}},
      \"Tweets\": {\"number\": N},
      \"Signal\": {\"select\": {\"name\": \"DOMINANT_SIGNAL\"}},
      \"Source\": {\"select\": {\"name\": \"DOMINANT_SOURCE\"}}
    },
    \"markdown\": $ESCAPED
  }"
```

## Step 3 — Send to Discord

Use `send_message` tool with target `discord:CHANNEL_ID`. Include the Notion page URL from the create response.

## Cron Job Setup

```yaml
action: create
schedule: "0 7 * * *"        # verify server TZ with timedatectl
deliver: discord:<channel_id>
enabled_toolsets: [terminal, web, file, skills]
skills: [social-media/xurl]
```

## Post-Push Processing

**push-digest.sh deletes the JSON file after commit** (`rm -f "$JSON_FILE"` at end of script). Any post-push processing (Discord message building, Notion page creation) must read the digest from the repo clone at `/tmp/twitter-digest-data/data/YYYY-MM-DD-TYPE.json` — not the original `/tmp/` path.

## Discord Delivery (Two Paths)

**Interactive sessions (user present):** Use `send_message` tool with target `discord:CHANNEL_ID`.

**Cron jobs / autonomous runs:** The `send_message` tool may not be available. Fall back to the Discord Bot REST API:

```bash
source ~/.hermes/.env
curl -s -X POST "https://discord.com/api/v10/channels/CHANNEL_ID/messages" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(python3 /tmp/discord_payload.py)"
```

See `references/discord-builder-pattern.md` for the full working message builder with char-counting and safe quote handling.

## Pitfalls

- **CreditsDepleted**: X API needs credits. $5 minimum at developer.x.com/billing.
- **Python f-string quote escaping**: `f'"\\"{text}\\""'` produces literal backslashes in output (`"\"text\""`). Use unicode escapes (`f'\u201c{text}\u201d'`) or simple `f'"{text}"'`. This is especially error-prone in Discord message builders where tweet text contains both double and single quotes.
- **Notion chunk size safety margin**: When splitting body text into `children[].paragraph.rich_text[].text.content` blocks (max 2000 chars each), use **1990 chars** per chunk. An exactly-2000-char chunk can overflow when a trailing newline pushes it to 2001-2008, triggering a 400 validation error.
- **Notion DB creation**: API v2025-09-03 uses `/v1/databases`, not `/v1/data_sources`.
- **Notion 404**: Must share parent page with integration via Notion UI.
- **Notion DB has zero properties**: Freshly-created databases may have NO properties at all (not even `Name`). The page creation payload can still include a `Name` title property — Notion will accept it. Always check schema with `GET /v1/databases/{id}` first.
- **`ntn api` has no `--json` flag**: Despite documentation hints, `ntn api` does not accept `--json`. For complex payloads (large markdown, nested properties), fall back to curl: `curl -s -X POST "https://api.notion.com/v1/pages" -H "Authorization: Bearer $NOTION_API_KEY" -H "Notion-Version: 2025-09-03" -H "Content-Type: application/json" -d @/tmp/payload.json`. Simple key=value params still work fine with `ntn api`.
- **Discord 2000-char limit hard-cut**: First-pass digest messages routinely produce 15K+ chars. Build the message programmatically with a `char_count` variable that tracks cumulative length, truncating tweets at ~95 chars and stopping when within 30 chars of 2000. Reserve quota per signal category (2 minimum) before filling any single one. See Discord Format section for the code pattern.
- **Security scan blocks piping to interpreter**: Hermes blocks `python3 -c`, `curl | python3`, and `| python3 -m json.tool` patterns. Always save API responses and data to files first, then process with a standalone `.py` script (`python3 /tmp/script.py`).
- **Cron timezone**: `0 7 * * *` = 7h server local. Verify with `timedatectl`.
- **Low engagement**: Don't filter by engagement on niche lists — it kills the signal.
- **Automated tagging is ~50% accurate**: Keyword-based theme/signal/source detection gets about half the tags wrong. Always manually review and correct tags after automated classification. See `references/tagging-guide.md`.
- **Regex case-sensitivity FAILS silently**: If your off-topic/tagging regex patterns contain uppercase (`r'ADD'`, `r'Bitcoin'`) but you match against `text.lower()`, they silently fail to match. Write ALL patterns in lowercase when matching against lowercased text. This caused an ADHD tweet to pass through as "Bitcoin" in one run.
- **Off-topic tweets from crypto personalities**: Crypto Twitter personalities post non-crypto content (Ukraine war travelogues, sports, vacation photos, gym advice). Build a `strong_crypto` signal list (BTC, Bitcoin, $ETH, Hyperliquid, Clarity Act, Lightning Network, SBR, etc.) and skip off-topic filtering only when those signals appear. Without this, you miss real crypto content — with it too lax, you get travelogues.
- **`xurl read` uses different credit pool than list tweets**: The list tweets endpoint (`/2/lists/{ID}/tweets`) works even when individual tweet reads (`xurl read TWEET_ID`) return `CreditsDepleted`. For reply enrichment, rely on **in-data parents only** — build a `tweet_map` from already-fetched list pages and look up parents by their `referenced_tweets[].id`. Parents outside the list's data are simply unavailable; skip them rather than trying external fetches that will fail. In practice, ~95% of reply parents are already in the list data.
- **Date filtering is essential on multi-page fetches**: Fetching 5 pages of 100 tweets each from a moderate-activity list returns ~500 tweets spanning 2+ weeks. Without date filtering, the daily digest gets swamped with old tweets. Always filter by `created_at` to today + yesterday (`CUTOFF = (today - timedelta(days=1)).strftime("%Y-%m-%d")`). This reduces the working set from 400+ to 20–40 tweets for a daily cron job. Weekend-only lists may need a wider window (3 days).
- **OAuth2 auto-refresh can fail silently in cron**: `xurl` claims auto-refresh but the refresh token is one-time-use — if xurl consumed it but failed to persist the new tokens to `~/.xurl`, the pipeline gets 401 on every request with no recovery path (browser-based OAuth required). Mitigation: run `xurl whoami` as a pre-flight check (Step 0) to force a live refresh and detect staleness before the main pipeline runs.
