# May 2026 — Telegram bot token compromise via public backup commit

## Timeline

| Date | Event |
|------|-------|
| 2026-05-23 19:40 | `hermes backup` cron pushes full `.env` (142 lines, ALL tokens) to `state-backups` branch of public repo `Seven74AI/hermes-agent` |
| 2026-05-24 18:45 | First Telegram polling conflict logged — attacker's instance starts polling the token |
| 2026-05-24 → 2026-06-13 | **743 conflicts** in gateway.log — ping-pong between Hermes instance and attacker instance |
| 2026-05-24 16:48 | Next backup: `auth.json` excluded "due to push protection" but `.env` still included |
| 2026-06-03 | Backup tarball still contains `.env` and `auth.json` |
| 2026-06-13 | Backup tarball still contains `.env` and `auth.json` |
| 2026-06-13 | User reports foreign message: "🚀 To use this bot, you must join our channel: https://t.me/A_ToolsX" |

## Root cause

The `hermes-backup` cron job (job ID `8d322a4ec332`) committed the ENTIRE `.env` file (including `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN`, `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `NOTION_API_KEY`, `FIRECRAWL_API_KEY`, `EDGEE_API_KEY`, `AGENTMAIL_API_KEY`, `GOOGLE_CLIENT_SECRET`) to a PUBLIC GitHub repo. The `state-backups` branch was never made private.

The cron used `hermes backup -q` which **explicitly includes `.env` and `auth.json`** in the backup zip. Later backups switched to tar.gz format but still contained both secret files. Neither format stripped secrets before pushing.

The leaked commit `ba2566627` was on a branch `state-backups` that had 4 backup commits:
1. `ba2566627` — first backup with directory structure + full `.env` (May 23)
2. `213ba3662` — `auth.json` excluded but `.env` still present (May 24)
3. `6ffdd6952` — switched to tar.gz, **still contained `.env` and `auth.json`** (June 3)
4. `7eb2ed921` — latest tar.gz, **still contained `.env` and `auth.json`** (June 13)

## Attacker behavior

- The attacker (`@A_ToolsX` channel) runs a bot farm that scans GitHub for Telegram bot tokens
- Within 24h of the commit, their instance started competing for `getUpdates` with the legitimate Hermes gateway
- When their instance wins the polling race, it intercepts the user's message and responds with a "join our channel" prompt
- The user sees BOTH the attacker's response AND (sometimes) Hermes's normal response in their chat

## Detection pattern

The `gateway.log` showed this exact pattern looping continuously:
```
WARNING gateway.platforms.telegram: Telegram polling conflict (1/5) —
  terminated by other getUpdates request;
  make sure that only one bot instance is running
INFO gateway.platforms.telegram: Telegram polling resumed after conflict retry 1/5
```
~20-30 seconds between each conflict (the retry interval).

## Investigation commands used

### Phase 1 — Confirm the leak exists

```bash
# 1. Search codebase for attacker strings
grep -r "A_ToolsX\|must join" /usr/local/lib/hermes-agent/ /root/.hermes/

# 2. Count conflicts
grep -c "polling conflict" /root/.hermes/logs/gateway.log
# Result: 743

# 3. Find when conflicts started
grep "polling conflict" /root/.hermes/logs/gateway.log | head -1
# 2026-05-24 18:45:32

# 4. Verify repo is public
curl -s -o /dev/null -w "%{http_code}" "https://github.com/Seven74AI/hermes-agent"
# HTTP 200 = PUBLIC
```

### Phase 2 — Find the exposed commit

```bash
# 5. Find ALL commits that ever added .env or auth.json across all branches
cd /usr/local/lib/hermes-agent
git log --all --oneline --diff-filter=A -- '*.env' 'auth.json' '*.tar.gz'

# 6. Check which branches exist (local + remote) that might hold secrets
git branch -a | grep -i backup

# 7. Find all remote branches that contain a specific poisonous commit
git branch -r --contains ba2566627
# Output: origin/state-backups  ← this is the vector

# 8. Extract the exposed .env from git history
git show ba2566627:state-snapshots/20260523-193648/.env | grep -E "^[A-Z_]+="

# 9. Check exposed commit on GitHub (publicly accessible?)
curl -s -o /dev/null -w "HTTP %{http_code}" \
  "https://github.com/Seven74AI/hermes-agent/commit/ba2566627"
# HTTP 200 = still accessible to anyone with the hash
```

### Phase 3 — Check if later backups also exposed secrets

```bash
# 10. Inspect tar.gz backups in git history for .env
git show 6ffdd6952:backups/hermes-critical-20260603-193500.tar.gz | tar tzf -
# Look for .env and auth.json in the file list

# 11. Log the branch's full history to understand the backup pattern
git log origin/state-backups --format="%ci %s" -10
```

### Phase 4 — Scan other repos and surface

```bash
# 12. Check all org repos for public visibility + token patterns
# Use GitHub code search API per repo for common token patterns:
#   TELEGRAM_BOT_TOKEN, DISCORD_BOT_TOKEN, ghp_, sk-ant, sk-proj, .env, auth.json

# 13. Web search for token exposure (check if indexed)
web_search("8846059608 telegram bot token")
web_search("ghp_gIPKRC github token")
```

### Phase 5 — Use session_search to reconstruct past investigation

```bash
# 14. If investigating after-the-fact, find past sessions by keyword
session_search(query="polling conflict OR token leak OR .env exposed", limit=5)
# Then scroll into the relevant session to see what was already found
session_search(session_id="...", around_message_id=<match_id>, window=15)
```

### 401 auth errors — secondary signal

When the user rotates a token mid-session (e.g., changes DeepSeek API key), the gateway logs fill with 401 errors. This is NOT a compromise signal — it's a side effect of rotation. Distinguish:
```
WARNING agent.conversation_loop: API call failed (attempt 1/3) error_type=AuthenticationError
ERROR root: Non-retryable client error: Error code: 401 - Authentication Fails, Your api key: **** is invalid
```
If 401s start suddenly and the user confirms they rotated keys → expected. If 401s appear without explanation → investigate.

## Tokens exposed

All tokens from the `.env` committed on May 23 were exposed for 3 weeks:
- `TELEGRAM_BOT_TOKEN` — CONFIRMED exploited (message injection + polling conflict)
- `DISCORD_BOT_TOKEN` — exposed, no confirmed exploitation detected
- `GITHUB_TOKEN` (`ghp_gIPKRC...`) — exposed
- `ANTHROPIC_API_KEY` — exposed
- `DEEPSEEK_API_KEY` — exposed
- `NOTION_API_KEY` — exposed
- `FIRECRAWL_API_KEY` — exposed
- `EDGEE_API_KEY` — exposed
- `AGENTMAIL_API_KEY` — exposed
- `GOOGLE_CLIENT_SECRET` — exposed

## Key lessons

1. **Never assume a repo is private** — verify with `curl` before pushing ANYTHING
2. **`.env` is a nuclear payload** — it contains ALL tokens in one file
3. **Polling conflicts are the canary** — they signal token theft immediately
4. **Revoke tokens FIRST, clean git history SECOND** — the token is the vulnerability, not the commit
5. **GitHub object cache persists** — even after force-push deletion, the commit remains accessible by hash. Contact GitHub Support.
6. **`hermes backup -q` is MORE dangerous than full backup** — the quick backup explicitly targets `.env` and `auth.json` as "critical state files" and includes them unconditionally. The help text confirms: "only critical state files (config, state.db, .env, auth, cron)." This is exactly the opposite of what you want for a public-facing backup.

## Remediation performed

### June 13, 2026 (phase 1 — containment)

1. **Deleted the `state-backups` branch from GitHub**: `git push origin --delete state-backups` → confirmed HTTP 404
2. **Fixed the backup cron job** (`8d322a4ec332`): Updated prompt to unzip → strip `.env` + `auth.json` → rezip → push. Also stripped token from git remote URL.
3. **Deleted local compromised backup tarballs**: `rm -f /root/.hermes/backups/hermes-critical-*.tar.gz`
4. **Fixed git remote on hermes-backup repo**: Switched to clean `git@github.com:Seven74AI/hermes-backup.git`
5. **Scanned all other Seven74AI repos**: Used GitHub Code Search API for token patterns across 10 repos — no other leaks found
6. **User rotated DeepSeek API key** (caused 401 gateway errors that auto-resolved after key update in `.env`)

### June 13, 2026 (phase 2 — full rotation, same day after token change interrupted session)

All exposed tokens rotated and verified:

| Token | Status | Note |
|-------|--------|------|
| TELEGRAM_BOT_TOKEN | ✅ Rotated | Old prefix `8846059608:AAH0-...`, new hash confirmed via `getMe` API |
| DISCORD_BOT_TOKEN | ✅ Rotated | Via Discord Developer Portal → Reset Token |
| GITHUB_TOKEN | ✅ Rotated | Old: `ghp_gIPKRC...` → New: `ghp_lpVWwt...`, confirmed via `GET /user` |
| ANTHROPIC_API_KEY | ✅ Rotated | User did before session |
| DEEPSEEK_API_KEY | ✅ Rotated | User did before session (caused 401 flood, resolved after .env update) |
| NOTION_API_KEY | ✅ Rotated | Via Notion integrations dashboard |
| EDGEE_API_KEY | ✅ Rotated | Via Edgee dashboard |
| GOOGLE_CLIENT_SECRET | ✅ Rotated | Via GCP console → Reset Secret |
| AGENTMAIL_API_KEY | ⚠️ Dead | No API key existed on user's AgentMail account — leaked key was stale/invalid |
| FIRECRAWL_API_KEY | ⏳ Pending | |

### Verification pattern (use after every rotation)

After updating `.env` with a new token, verify it before restarting the gateway:

```bash
# Telegram — bot token still alive?
curl -s "https://api.telegram.org/bot$TOKEN/getMe" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('ok') else d.get('description','fail'))"

# GitHub — classic PAT valid?
curl -s -o /dev/null -w "HTTP %{http_code}" -H "Authorization: bearer $TOKEN" https://api.github.com/user

# DeepSeek — API key active?
curl -s -o /dev/null -w "HTTP %{http_code}" -H "Authorization: Bearer $TOKEN" https://api.deepseek.com/v1/models
```

### Remaining work

- Rotate FIRECRAWL_API_KEY
- Contact GitHub Support to purge commit `ba2566627` from object cache
- Delete local `state-backups` branch when no longer needed
