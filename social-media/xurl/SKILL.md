---
name: xurl
description: "X/Twitter via xurl CLI: post, search, DM, media, v2 API."
version: 1.1.1
author: xdevplatform + openclaw + Hermes Agent
license: MIT
platforms: [linux, macos]
prerequisites:
  commands: [xurl]
metadata:
  hermes:
    tags: [twitter, x, social-media, xurl, official-api]
    homepage: https://github.com/xdevplatform/xurl
    upstream_skill: https://github.com/openclaw/openclaw/blob/main/skills/xurl/SKILL.md
---

# xurl — X (Twitter) API via the Official CLI

`xurl` is the X developer platform's official CLI for the X API. It supports shortcut commands for common actions AND raw curl-style access to any v2 endpoint. All commands return JSON to stdout.

Use this skill for:
- posting, replying, quoting, deleting posts
- searching posts and reading timelines/mentions
- liking, reposting, bookmarking
- following, unfollowing, blocking, muting
- direct messages
- media uploads (images and video)
- raw access to any X API v2 endpoint
- multi-app / multi-account workflows

This skill replaces the older `xitter` skill (which wrapped a third-party Python CLI). `xurl` is maintained by the X developer platform team, supports OAuth 2.0 PKCE with auto-refresh, and covers a substantially larger API surface.

---

## Secret Safety (MANDATORY)

Critical rules when operating inside an agent/LLM session:

- **Never** read, print, parse, summarize, upload, or send `~/.xurl` to LLM context.
- **Never** ask the user to paste credentials/tokens into chat.
- The user must fill `~/.xurl` with secrets manually on their own machine.
- **Never** recommend or execute auth commands with inline secrets in agent sessions.
- **Never** use `--verbose` / `-v` in agent sessions — it can expose auth headers/tokens.
- To verify credentials exist, only use: `xurl auth status`.

Forbidden flags in agent commands (they accept inline secrets):
`--bearer-token`, `--consumer-key`, `--consumer-secret`, `--access-token`, `--token-secret`, `--client-id`, `--client-secret`

App credential registration and credential rotation must be done by the user manually, outside the agent session. After credentials are registered, the user authenticates with `xurl auth oauth2` — also outside the agent session. Tokens persist to `~/.xurl` in YAML. Each app has isolated tokens. OAuth 2.0 tokens auto-refresh.

---

## Installation

Pick ONE method. On Linux, the shell script or `go install` are the easiest.

```bash
# Shell script (installs to ~/.local/bin, no sudo, works on Linux + macOS)
curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash

# Homebrew (macOS)
brew install --cask xdevplatform/tap/xurl

# npm
npm install -g @xdevplatform/xurl

# Go
go install github.com/xdevplatform/xurl@latest
```

Verify:

```bash
xurl --help
xurl auth status
```

If `xurl` is installed but `auth status` shows no apps or tokens, the user needs to complete auth manually — see the next section.

---

## Pitfalls discovered in practice

- **`xurl` not in PATH after install**: The install script puts the binary in `~/.local/bin`. If `which xurl` fails, check `/usr/local/bin` or `~/.local/bin`. On this setup it landed in `/usr/local/bin/xurl`.
- **OAuth callback fails with `ERR_CONNECTION_REFUSED`**: `xurl auth oauth2` starts a local HTTP server on port 8080 to catch the callback. If xurl runs on a remote Linux server, the browser on the user's machine can't reach it. Fix: use SSH port forwarding (`ssh -L 8080:localhost:8080 user@server`) before running the OAuth command, or run xurl locally and copy `~/.xurl` to the server.
- **`unauthorized_client` / "Missing valid authorization header"**: App type in X Developer Portal is set to "Native App". Must be changed to **"Web app, automated app or bot"** in User Authentication Settings. After changing, remove and re-add the app credentials (`xurl auth apps remove my-app` then re-add) — the old credentials may be cached with wrong settings.
- **Client ID and Secret swapped**: The X Developer Portal UI sometimes shows two values both labeled "Client Secret". The first one is actually the **Client ID**. Verify on the "Keys and tokens" page.
- **`CreditsDepleted` on all read operations**: The X API Free plan has zero credits. Search, timeline, list tweets — all require credits. Minimum $5 purchase at https://developer.x.com/en/portal/billing. Pay-per-use; $5 lasts a long time for read-only use cases.
- **List tweets endpoint**: Use `xurl /2/lists/{LIST_ID}/tweets` (raw API call). No `-n` flag available on raw calls unlike shortcut commands.

## One-Time User Setup (user runs these outside the agent)

These steps must be performed by the user directly, NOT by the agent, because they involve pasting secrets. Direct the user to this block; do not execute it for them.

1. Create or open an app at https://developer.x.com/en/portal/dashboard
2. In "Paramètres d'authentification utilisateur" (User Authentication Settings):
   - App type: **"Application web, app automatisée ou bot"** (NOT "Native app")
   - Redirect URI: `http://localhost:8080/callback`
   - Website URL: `https://example.com` (obligatoire mais pas utilisée)
   - Permissions: **Lecture, Écriture et Messages directs** (maximum)
3. Copy the Client ID and Client Secret from "Clés et jetons" — **UI bug**: if you see two "Client Secret" values, the first is actually the Client ID (IDs end in `MTpjaQ`)
4. Register the app locally:
   ```bash
   xurl auth apps add my-app --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
   ```
5. Authenticate (pass the handle explicitly to avoid `/2/users/me` 403 issues):
   ```bash
   # If on a remote server, first open SSH tunnel in another terminal:
   # ssh -L 8080:localhost:8080 user@server
   xurl auth oauth2 --app my-app YOUR_USERNAME
   ```
6. Set as default:
   ```bash
   xurl auth default my-app
   ```
7. Verify:
   ```bash
   xurl auth status
   xurl whoami
   ```

After this, the agent can use any command below without further setup. OAuth 2.0 tokens auto-refresh.

> **Common pitfall:** If you omit `--app my-app` from `xurl auth oauth2`, the OAuth token is saved to the built-in `default` app profile — which has no client-id or client-secret. Commands will fail with auth errors even though the OAuth flow appeared to succeed. If you hit this, re-run `xurl auth oauth2 --app my-app` and `xurl auth default my-app`.

---

## Quick Reference

| Action | Command |
| --- | --- |
| Post | `xurl post "Hello world!"` |
| Reply | `xurl reply POST_ID "Nice post!"` |
| Quote | `xurl quote POST_ID "My take"` |
| Delete a post | `xurl delete POST_ID` |
| Read a post | `xurl read POST_ID` |
| Search posts | `xurl search "QUERY" -n 10` |
| Who am I | `xurl whoami` |
| Look up a user | `xurl user @handle` |
| Home timeline | `xurl timeline -n 20` |
| Mentions | `xurl mentions -n 10` |
| Like / Unlike | `xurl like POST_ID` / `xurl unlike POST_ID` |
| Repost / Undo | `xurl repost POST_ID` / `xurl unrepost POST_ID` |
| Bookmark / Remove | `xurl bookmark POST_ID` / `xurl unbookmark POST_ID` |
| List bookmarks / likes | `xurl bookmarks -n 10` / `xurl likes -n 10` |
| Follow / Unfollow | `xurl follow @handle` / `xurl unfollow @handle` |
| Following / Followers | `xurl following -n 20` / `xurl followers -n 20` |
| Block / Unblock | `xurl block @handle` / `xurl unblock @handle` |
| Mute / Unmute | `xurl mute @handle` / `xurl unmute @handle` |
| Send DM | `xurl dm @handle "message"` |
| List DMs | `xurl dms -n 10` |
| Upload media | `xurl media upload path/to/file.mp4` |
| Media status | `xurl media status MEDIA_ID` |
| List apps | `xurl auth apps list` |
| Remove app | `xurl auth apps remove NAME` |
| Set default app | `xurl auth default APP_NAME [USERNAME]` |
| Per-request app | `xurl --app NAME /2/users/me` |
| Auth status | `xurl auth status` |

Notes:
- `POST_ID` accepts full URLs too (e.g. `https://x.com/user/status/1234567890`) — xurl extracts the ID.
- Usernames work with or without a leading `@`.

---

## Command Details

### Posting

```bash
xurl post "Hello world!"
xurl post "Check this out" --media-id MEDIA_ID
xurl post "Thread pics" --media-id 111 --media-id 222

xurl reply 1234567890 "Great point!"
xurl reply https://x.com/user/status/1234567890 "Agreed!"
xurl reply 1234567890 "Look at this" --media-id MEDIA_ID

xurl quote 1234567890 "Adding my thoughts"
xurl delete 1234567890
```

### Reading & Search

```bash
xurl read 1234567890
xurl read https://x.com/user/status/1234567890

xurl search "golang"
xurl search "from:elonmusk" -n 20
xurl search "#buildinpublic lang:en" -n 15
```

### Lists

```bash
# Tweets d'une liste publique (par ID ou URL)
xurl /2/lists/LIST_ID/tweets

# Infos sur la liste
xurl /2/lists/LIST_ID

# L'ID est dans l'URL : https://x.com/i/lists/1153202943035879424 → 1153202943035879424
```

Note: `-n` ne fonctionne pas sur les endpoints raw (`/2/...`). Utiliser les paramètres query string si besoin de pagination : `xurl "/2/lists/LIST_ID/tweets?max_results=10"`

**IMPORTANT — The list tweets endpoint only returns `id` and `text` by default.** To get author usernames and engagement metrics (likes, retweets, replies), you MUST request expansions and fields:

```bash
# Full fetch with author usernames + engagement metrics
xurl "/2/lists/LIST_ID/tweets?max_results=100&expansions=author_id&user.fields=username&tweet.fields=public_metrics"

# Pagination: use next_token from meta in the response
xurl "/2/lists/LIST_ID/tweets?max_results=100&pagination_token=NEXT_TOKEN&expansions=author_id&user.fields=username&tweet.fields=public_metrics"
```

The response includes `includes.users[]` mapping `author_id` → `username`, and `public_metrics` on each tweet with `like_count`, `retweet_count`, `reply_count`, `quote_count`, `impression_count`.

**Agent workflow:** When fetching list tweets for digest/summary purposes, save the JSON output to a file first (`xurl "..." > /tmp/tweets.json`), then process with a Python script from disk. **Hermes blocks ALL `python3 -c` and pipe-to-interpreter patterns** (`xurl | python3`, `curl | python3 -c`, standalone `python3 -c "..."`). Always write `.py` files and run them with `python3 script.py` instead.

### Users, Timeline, Mentions

```bash
xurl whoami
xurl user elonmusk
xurl user @XDevelopers

xurl timeline -n 25
xurl mentions -n 20
```

### Engagement

```bash
xurl like 1234567890
xurl unlike 1234567890

xurl repost 1234567890
xurl unrepost 1234567890

xurl bookmark 1234567890
xurl unbookmark 1234567890

xurl bookmarks -n 20
xurl likes -n 20
```

### Social Graph

```bash
xurl follow @XDevelopers
xurl unfollow @XDevelopers

xurl following -n 50
xurl followers -n 50

# Another user's graph
xurl following --of elonmusk -n 20
xurl followers --of elonmusk -n 20

xurl block @spammer
xurl unblock @spammer
xurl mute @annoying
xurl unmute @annoying
```

### Direct Messages

```bash
xurl dm @someuser "Hey, saw your post!"
xurl dms -n 25
```

### Media Upload

```bash
# Auto-detect type
xurl media upload photo.jpg
xurl media upload video.mp4

# Explicit type/category
xurl media upload --media-type image/jpeg --category tweet_image photo.jpg

# Videos need server-side processing — check status (or poll)
xurl media status MEDIA_ID
xurl media status --wait MEDIA_ID

# Full workflow
xurl media upload meme.png                  # returns media id
xurl post "lol" --media-id MEDIA_ID
```

---

## Raw API Access

The shortcuts cover common operations. For anything else, use raw curl-style mode against any X API v2 endpoint:

```bash
# GET
xurl /2/users/me

# POST with JSON body
xurl -X POST /2/tweets -d '{"text":"Hello world!"}'

# DELETE / PUT / PATCH
xurl -X DELETE /2/tweets/1234567890

# Custom headers
xurl -H "Content-Type: application/json" /2/some/endpoint

# Force streaming
xurl -s /2/tweets/search/stream

# Full URLs also work
xurl https://api.x.com/2/users/me
```

---

## Global Flags

| Flag | Short | Description |
| --- | --- | --- |
| `--app` | | Use a specific registered app (overrides default) |
| `--auth` | | Force auth type: `oauth1`, `oauth2`, or `app` |
| `--username` | `-u` | Which OAuth2 account to use (if multiple exist) |
| `--verbose` | `-v` | **Forbidden in agent sessions** — leaks auth headers |
| `--trace` | `-t` | Add `X-B3-Flags: 1` trace header |

---

## Streaming

Streaming endpoints are auto-detected. Known ones include:

- `/2/tweets/search/stream`
- `/2/tweets/sample/stream`
- `/2/tweets/sample10/stream`

Force streaming on any endpoint with `-s`.

---

## Output Format

All commands return JSON to stdout. Structure mirrors X API v2:

```json
{ "data": { "id": "1234567890", "text": "Hello world!" } }
```

Errors are also JSON:

```json
{ "errors": [ { "message": "Not authorized", "code": 403 } ] }
```

---

## Common Workflows

### List Tweet Digest (→ Notion + Discord + GitHub Pages)

For the full fetch→filter→tag→digest→publish pipeline used in cron jobs, see the **twitter-digest** skill. Quick xurl-specific notes for list tweets:

### Post with an image
```bash
xurl media upload photo.jpg
xurl post "Check out this photo!" --media-id MEDIA_ID
```

### Reply to a conversation
```bash
xurl read https://x.com/user/status/1234567890
xurl reply 1234567890 "Here are my thoughts..."
```

### Search and engage
```bash
xurl search "topic of interest" -n 10
xurl like POST_ID_FROM_RESULTS
xurl reply POST_ID_FROM_RESULTS "Great point!"
```

### Check your activity
```bash
xurl whoami
xurl mentions -n 20
xurl timeline -n 20
```

### Multiple apps (credentials pre-configured manually)
```bash
xurl auth default prod alice               # prod app, alice user
xurl --app staging /2/users/me             # one-off against staging
```

---

## Error Handling

- Non-zero exit code on any error.
- API errors are still printed as JSON to stdout, so you can parse them.
- Auth errors → have the user re-run `xurl auth oauth2` outside the agent session.
- Commands that need the caller's user ID (like, repost, bookmark, follow, etc.) will auto-fetch it via `/2/users/me`. An auth failure there surfaces as an auth error.

### Critical Pitfall: List Tweets Endpoint Has No User Data

`xurl /2/lists/LIST_ID/tweets` returns only `edit_history_tweet_ids`, `text`, and `id`.
It does NOT include `author_id`, `entities`, or `public_metrics`. The `includes.users`
array is absent. You cannot get usernames, avatars, like counts, or media from this endpoint.

**Workaround for usernames:** Call `xurl /2/lists/LIST_ID/members` to get all list members,
but without `author_id` on tweets you can't correlate them. For individual tweet enrichment,
use `xurl read TWEET_ID` (expensive if done per-tweet).

**Workaround for media:** Parse `entities.urls` from an enriched tweet (via `xurl read`).
URLs with `media_key` or `display_url` containing `pic.x.com` are images/videos.

For high-volume digest workflows where per-tweet enrichment is impractical, accept that
list tweets come bare and design the UI to handle missing user/media gracefully.

---

## Agent Workflow

1. Verify prerequisites: `xurl --help` and `xurl auth status`.
2. **Check default app has credentials.** Parse the `auth status` output. The default app is marked with `▸`. If the default app shows `oauth2: (none)` but another app has a valid oauth2 user, tell the user to run `xurl auth default <that-app>` to fix it. This is the most common setup mistake — the user added an app with a custom name but never set it as default, so xurl keeps trying the empty `default` profile.
3. If auth is missing entirely, stop and direct the user to the "One-Time User Setup" section — do NOT attempt to register apps or pass secrets yourself.
4. Start with a cheap read (`xurl whoami`, `xurl user @handle`, `xurl search ... -n 3`) to confirm reachability.
5. Confirm the target post/user and the user's intent before any write action (post, reply, like, repost, DM, follow, block, delete).
6. Use JSON output directly — every response is already structured.
7. Never paste `~/.xurl` contents back into the conversation.

---

## Troubleshooting

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Auth errors after successful OAuth flow | Token saved to `default` app (no client-id/secret) instead of your named app | `xurl auth oauth2 --app my-app` then `xurl auth default my-app` |
| `unauthorized_client` during OAuth | App type set to "Native App" in X dashboard | Change to "Web app, automated app or bot" in User Authentication Settings |
| `UsernameNotFound` or 403 on `/2/users/me` right after OAuth | X not returning username reliably from `/2/users/me` | Re-run `xurl auth oauth2 --app my-app YOUR_USERNAME` (xurl v1.1.0+) to pass the handle explicitly |
| 401 on every request | Token expired or wrong default app | Check `xurl auth status` — verify `▸` points to an app with oauth2 tokens |
| `client-forbidden` / `client-not-enrolled` | X platform enrollment issue | Dashboard → Apps → Manage → Move to "Pay-per-use" package → Production environment |
| Browser can't reach `localhost:8080` during OAuth | Running on a remote server (SSH) | Open a local terminal and run `ssh -L 8080:localhost:8080 user@server`, keep it open, then run `xurl auth oauth2` on the server |
| `CreditsDepleted` | $0 balance on X API | Buy credits (min $5) in Developer Console → Billing |
| `media processing failed` on image upload | Default category is `amplify_video` | Add `--category tweet_image --media-type image/png` |
| Two "Client Secret" values in X dashboard | UI bug — first is actually Client ID | Confirm on the "Keys and tokens" page; ID ends in `MTpjaQ` |
| OAuth callback `ERR_CONNECTION_REFUSED` | `xurl auth oauth2` ouvre un serveur sur le serveur Linux — le browser du client ne peut pas l'atteindre | SSH port forwarding : `ssh -L 8080:localhost:8080 user@server`, puis relancer `xurl auth oauth2 --app my-app USERNAME` |
| `xurl auth apps add` refuse si l'app existe déjà | Impossible de modifier les credentials d'une app existante | `xurl auth apps remove my-app` puis re-`add` avec les bons credentials |
| 401 on every request but `auth status` shows token | Auto-refresh consumed the refresh token but failed to persist new tokens to disk — `~/.xurl` has a stale refresh token | User must re-run browser-based OAuth: `ssh -L 8080:localhost:8080 user@server` then `xurl auth oauth2 --app my-app USERNAME`. Prevent by scheduling `xurl whoami` 30min before cron jobs — forces a live refresh |

---

## Notes

- **Rate limits:** X enforces per-endpoint rate limits. A 429 means wait and retry. Write endpoints (post, reply, like, repost) have tighter limits than reads.
- **List tweets endpoint limitation:** `GET /2/lists/{id}/tweets` does NOT return `author_id` or user `includes` by default. The response only contains `id`, `text`, and `edit_history_tweet_ids`. To get usernames and avatars, you must add query params: `?expansions=author_id&user.fields=username,name,profile_image_url`. Without these, all tweets show as "unknown" user.
- **Scopes:** OAuth 2.0 tokens use broad scopes. A 403 on a specific action usually means the token is missing a scope — have the user re-run `xurl auth oauth2`.
- **Token refresh:** OAuth 2.0 tokens auto-refresh — but the refresh can fail silently. If xurl consumes the refresh token during a failed save-back, the on-disk refresh token becomes stale and the access token expires with no recovery path. Headless/cron environments are especially vulnerable because the browser-based OAuth flow can't run. Mitigation: schedule a cheap health-check call (`xurl whoami`) 30 minutes before any scheduled pipeline job — this forces a refresh while the previous refresh token is still valid, keeping the on-disk tokens fresh.
- **Multiple apps:** Each app has isolated credentials/tokens. Switch with `xurl auth default` or `--app`.
- **Multiple accounts per app:** Select with `-u / --username`, or set a default with `xurl auth default APP USER`.
- **Token storage:** `~/.xurl` is YAML. Never read or send this file to LLM context.
- **Cost:** X API access is typically paid for meaningful usage. Many failures are plan/permission problems, not code problems.

---

## Attribution

- Upstream CLI: https://github.com/xdevplatform/xurl (X developer platform team, Chris Park et al.)
- Upstream agent skill: https://github.com/openclaw/openclaw/blob/main/skills/xurl/SKILL.md
- Hermes adaptation: reformatted for Hermes skill conventions; safety guardrails preserved verbatim.
