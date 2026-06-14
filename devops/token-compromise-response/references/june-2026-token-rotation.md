# June 2026 — Token Rotation Follow-Up

After the May 2026 compromise (Telegram bot token stolen, attacker injecting
"Join @A_ToolsX" messages), the user initiated a full token rotation of all
exposed credentials on June 13, 2026.

## Context

The initial breach was discovered in May, but the full rotation was deferred.
By June, the user returned to complete the cleanup after changing the DeepSeek
token mid-session (which caused 401 auth floods in the gateway).

## Tokens rotated (June 13)

| Token | Status | Notes |
|-------|--------|-------|
| ANTHROPIC_API_KEY | ✅ User did | |
| DEEPSEEK_API_KEY | ✅ User did | Caused 401 cascade, used as signal to restart |
| TELEGRAM_BOT_TOKEN | ✅ | Bot ID (8846059608) unchanged, hash renewed |
| GITHUB_TOKEN | ✅ | New classic PAT `ghp_lpVW...` with `repo` scope |
| DISCORD_BOT_TOKEN | ✅ | First attempt: user rotated Client Secret by mistake. Second attempt: correct Bot Token |
| NOTION_API_KEY | ✅ | |
| EDGEE_API_KEY | ✅ | |
| GOOGLE_CLIENT_SECRET | ✅ | |
| FIRECRAWL_API_KEY | ✅ | |
| AGENTMAIL_API_KEY | N/A | No active key on user's account — old one likely invalid |

## Pitfalls hit

### Discord: Client Secret vs Bot Token
The user first went to OAuth2 → General and rotated the Client Secret. The
gateway rejected it as "Improper token." The fix: go to Bot → Reset Token.
Token format confirmed: `MT...` (base64-encoded bot user ID).

### `hermes backup -q` includes .env
The tar.gz backups on the `state-backups` branch contained `.env` and
`auth.json` inside the archive. Even after the May fix that excluded
auth.json from the state-snapshot directory, the tar.gz format packed
everything. Check with: `git show <commit>:backup.tar.gz | tar tzf -`

### Local branch persistence
The GitHub `state-backups` branch was deleted (HTTP 404 confirmed), but the
local branch still existed. Deleted with `git branch -D state-backups`.

## Cleanup completed

- GitHub `state-backups` branch: deleted
- Local `state-backups` branch: deleted
- Compromised local backup tarballs: removed from `/root/.hermes/backups/`
- Cron job `8d322a4ec332`: patched to strip `.env` and `auth.json` before push
- Git remote: fixed to not embed token in URL
- Gateway: restarted, Telegram + Discord connected cleanly

## Remaining risk

The commit `ba2566627` is orphaned on GitHub (no branch references it) but
still directly accessible via its URL. GitHub Support purge was not requested.
