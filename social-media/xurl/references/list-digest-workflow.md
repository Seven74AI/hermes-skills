# List Tweet Digest Workflow

Pattern for cron jobs that fetch, filter, score, and publish tweet digests to Notion + Discord.

## Prerequisites

- `xurl` CLI authenticated with X API credits (read operations require paid credits)
- `NOTION_API_KEY` set in `~/.hermes/.env`
- `ntn` CLI or `curl` for Notion API
- Discord auto-delivery configured (cron jobs with `HERMES_CRON_AUTO_DELIVER_PLATFORM=discord`)

## Step-by-Step

### 1. Fetch Tweets (2+ pages)

Always request expansions to get author usernames and engagement metrics. For digest outputs that include avatars, also request `profile_image_url` and `name`:

```bash
xurl "/2/lists/{LIST_ID}/tweets?max_results=100&expansions=author_id&user.fields=username,name,profile_image_url&tweet.fields=public_metrics,created_at" > /tmp/page1.json
```

Check `meta.next_token` in the response. If present, fetch page 2:

```bash
xurl "/2/lists/{LIST_ID}/tweets?max_results=100&pagination_token={NEXT_TOKEN}&expansions=author_id&user.fields=username,name,profile_image_url&tweet.fields=public_metrics,created_at" > /tmp/page2.json
```

**Security note:** Save to files, don't pipe to `python3 -c`. Hermes blocks ALL `python3 -c` invocations (standalone or piped) under the "script execution via -e/-c flag" rule. Always write `.py` files and execute them with `python3 script.py`. Pipe-to-interpreter patterns (`curl | python3`, `xurl | python3`) are also blocked under a separate tirith rule.

### 2. Filter & Score

Write a Python script that:
1. Loads both JSON files, builds a `author_id → username` map from `includes.users[]`
2. Removes retweets (`text.startswith('RT @')`)
3. Removes link-only/emoji-only tweets (strip URLs and emojis, require ≥15 meaningful chars)
4. Scores each tweet (0-10) based on:
   - Market/trading keywords (+2)
   - Announcements/breaking news (+3)
   - Stats/data points (+2)
   - Insight/analysis language (+2)
   - Content links (video, article) (+2)
   - Original thought (+1)
   - Historical context (+2)
   - Engagement: likes>50 (+2), likes>10 (+1), replies>10 (+1)
   - Penalty: short text (<40 chars after URL removal: -3)
5. Keeps tweets scoring ≥4

### 2b. Alternative: Multi-Dimension Tagging (no scoring)

For digests that just present tweets grouped by type (no summaries, no "Why it matters"), use a 3-dimension tagging schema instead of numeric scoring:

**Dimension 1 — Themes** (multi_select, pick 1-3): Choose from a domain-specific set (e.g., Bitcoin, Trading, DeFi, Regulation, Macro, Privacy, Security, Mining). Detect with keyword dictionaries — each theme maps to a list of case-insensitive keywords.

**Dimension 2 — Signal** (select, pick ONE):
- 🔴 Signal: announcement, launch, news, alpha, exchange listing, protocol update
- 🟡 Insight: opinion, analysis, hot take, prediction, market observation
- 🟢 Discussion: reply, debate, question/answer, conversation
- ⚪ Link/Ref: sharing a link/resource without substantial commentary

**Dimension 3 — Source** (select, pick ONE):
- Builder: sharing their own work/product/project/protocol
- Curator: sharing a link/resource from someone else
- Analyst: giving an opinion/analysis/prediction
- Community: replying, participating in discussion

Use keyword + pattern rules for detection, falling back to text-length heuristics. This approach is faster for cron jobs where manual curation isn't possible.

### 2c. Off-Topic Filtering

Build a list of regex patterns for content that should be excluded. **Critical pitfall:** test all regex patterns against `text.lower()`. If patterns contain uppercase characters (e.g., `r'What (having )?ADD (is|looks) like'`) but the match target is lowercased (`text.lower()` → `"what having add is like"`), the pattern silently fails to match. Write all off-topic patterns in lowercase.

Additional patterns to catch:
- Ukraine war travelogues from crypto personalities (unless they explicitly mention BTC/SOL/ETH fundraising)
- Sports/gaming/personal-life tweets (NBA, vacation snaps, gym advice)
- Generic meme templates with no crypto substance
- Podcast episode announcements (link-forward, low original content)
- Political rants without crypto angle

Override off-topic filtering when the tweet contains strong crypto signals (BTC, Bitcoin, $ETH, Hyperliquid, Clarity Act, Lightning Network, SBR, etc.).

### 3. Curate Top 15+

Manually select the top tweets, ensuring diversity across:
- Authors (avoid one person dominating)
- Topics (Bitcoin, DeFi, macro, altcoins, regulation, culture)
- Engagement variety (mix high-like and thoughtful niche tweets)

Aim for ~10-12 highlights with full quotes and "Why it matters" analysis, plus 5-8 notable mentions in condensed form.

### 4. Digest Structure

```markdown
## Crypto Digest — [Date]

### Key Themes Today
[2-5 thematic observations with 1-2 sentence summary each]

### Highlights
For each top tweet:
**@username** (L:X RT:Y)
"tweet text..."
→ Why it matters: [1 sentence]

### Notable Mentions
[remaining tweets in condensed bullet form]
```

### 5. Write to Notion

**Check database schema first** — newly created databases may have no custom properties:

```bash
curl -s "https://api.notion.com/v1/databases/{DB_ID}" \
  -H "Authorization: Bearer $NOTION_API_KEY" \
  -H "Notion-Version: 2025-09-03" > /tmp/schema.json
```

If only `Name` exists, create page with just the title property:

```python
payload = {
    "parent": {"database_id": "{DB_ID}"},
    "properties": {
        "Name": {"title": [{"text": {"content": "Crypto Digest — May 17, 2026"}}]}
    },
    "markdown": markdown_content
}
```

POST to `https://api.notion.com/v1/pages` with `Notion-Version: 2025-09-03`.

Construct Notion URL by stripping dashes from page ID: `https://notion.so/{page_id.replace('-', '')}`.

### 6. Discord Delivery

Cron jobs with `HERMES_CRON_AUTO_DELIVER_PLATFORM=discord` auto-deliver the final response. Format for Discord:
- Use `**bold**` for usernames and key phrases
- Use `>` for tweet quotes (renders as blockquotes)
- Include the Notion link prominently
- Limit to highlights + notable mentions (Discord has character limits)

## Common Pitfalls
## Common Pitfalls

- **Missing author data:** The list tweets endpoint returns only `id` and `text` without expansions — you'll get no usernames or engagement metrics.
- **Notion property mismatch:** Custom properties like `Date` or `Tweets` may not exist on the database. Always check schema first.
- **Pipe-to-interpreter blocked:** Hermes security prevents `curl | python3 -c` and `xurl | python3 -c`. Save to files, then process.
- **Regex case-sensitivity in off-topic filters:** If your off-topic regex patterns contain uppercase (`r'What ADD'`) but you match against `text.lower()`, the pattern silently fails. Write all off-topic patterns in lowercase (`r'what add'`), or match against the original text.
- **`ntn api` has no `--json` flag:** Despite docs, `ntn api` doesn't accept `--json`. For complex Notion payloads, fall back to curl with `-d @/tmp/payload.json`.
- **Discord 2000-char limit:** Build the Discord message programmatically with a `char_count` tracking loop. First-pass digests routinely produce 15K+ chars — truncation and per-category quotas are essential.
