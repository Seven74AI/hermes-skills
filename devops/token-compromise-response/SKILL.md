---
name: token-compromise-response
description: Detect, investigate, and remediate API token / bot token compromises. Systematic workflow from first suspicion to full rotation.
---

Detect and respond to compromised API keys, bot tokens, and credentials. A compromise means an attacker has your tokens and can read messages, send as your bot, or consume your API credits.

## Trigger

Use when:
- User reports suspicious bot messages ("I keep seeing messages I didn't send")
- Gateway logs show persistent polling conflicts or auth errors
- Unauthorized API charges appear
- A `.env` or credential file was accidentally committed to a public repo

## Detection signals

### Telegram

**Polling conflict** — the strongest signal. Another instance is polling the same bot token:
```
WARNING gateway.platforms.telegram: Telegram polling conflict (1/5) —
  terminated by other getUpdates request;
  make sure that only one bot instance is running
```
Check: `grep "polling conflict" ~/.hermes/logs/gateway.log | wc -l`

Any count > 0 over a sustained period = another instance has your token.

**Foreign messages in chat** — the user sees messages they didn't send AND the agent didn't send. Classic sign of an attacker interleaving responses.

### Discord

- Gateway logs: `discord connect timed out` or auth failures when the token was working before
- Suspicious bot activity in channels (unrecognized messages, DM spam)

### GitHub

- `ghp_...` token (classic PAT) committed to a public repo → GitHub automatically revokes it within minutes
- Check: `https://github.com/settings/tokens` for revoked tokens
- Check repo audit logs for unauthorized pushes or PRs

### API providers (Anthropic, DeepSeek, etc.)

- Unexpected usage spikes or charges
- Rate limiting on your key when you're not using it heavily

### False positive: 401 auth errors after token rotation

When the user rotates a token (e.g., changes their DeepSeek API key mid-session), the gateway logs will fill with 401 Authentication errors. The active sessions were started with the old key and can't recover. This is NOT a compromise — it's a side effect of legitimate rotation:

```
WARNING agent.conversation_loop: API call failed (attempt 1/3)
  error_type=AuthenticationError provider=deepseek
ERROR root: Non-retryable client error: Error code: 401 -
  Authentication Fails, Your api key: **** is invalid
```

Distinguish: if 401s start suddenly AND the user confirms they rotated keys → expected, restart the gateway. If 401s appear without explanation → investigate as potential compromise.

## Investigation workflow

### 1. Search the codebase for suspicious strings
```bash
grep -r "suspicious_message_or_url" /usr/local/lib/hermes-agent/ ~/.hermes/
```
If the user reports a specific message (e.g., "Join our channel: t.me/X"), search for every substring.

### 2. Check gateway logs for platform conflicts
```bash
grep -i "conflict\|unauthorized\|terminated by other" ~/.hermes/logs/gateway.log | tail -30
```
Telegram polling conflict = token stolen. Discord connect failures after previously working = possible.

### 3. Check git history for committed secrets
```bash
cd /usr/local/lib/hermes-agent

# Pickaxe search — finds commits that added/removed lines matching the pattern
git log --all --oneline -S "BOT_TOKEN" -- .
git log --all --oneline -S "API_KEY" -- .
git log --all --oneline -S "ghp_" -- .   # GitHub PATs

# Stronger: find all commits that ADDED .env, auth.json, or backup archives
git log --all --oneline --diff-filter=A -- '*.env' 'auth.json' '*.tar.gz' '*.zip'

# Find which remote branch(es) contain a poisonous commit
git branch -r --contains <commit_hash>

# Inspect a tar.gz backup for secrets without extracting
git show <commit>:path/to/backup.tar.gz | tar tzf - | grep -E '\.env$|auth\.json'
```

### 4. Verify repo visibility
```bash
curl -s -o /dev/null -w "%{http_code}" "https://github.com/ORG/REPO"
```
HTTP 200 = public. HTTP 404 = private or doesn't exist. **Any backup or state repo containing tokens MUST be private.**

### 5. Check the actual exposed commit
```bash
git show <commit_hash>:path/to/.env
```
Confirm what was exposed. Look for every `TOKEN`, `_KEY`, `SECRET` line.

### 6. Check all repos under the org
```bash
curl -s "https://api.github.com/users/ORG/repos?per_page=50" | python3 -c "
import json,sys
for r in json.load(sys.stdin):
    print(f\"{r['name']} — {'PRIVATE' if r.get('private') else 'PUBLIC'}\")
"
```

### 7. Reconstruct past investigation with session_search
If you're picking up a partially-completed investigation (e.g., user changed a token and stopped the agent mid-work), use session_search to find and scroll through past sessions:
```bash
session_search(query="polling conflict OR token leak OR .env exposed", limit=5)
# Then scroll into the match: session_search(session_id="...", around_message_id=<id>, window=15)
```
This avoids re-doing work already completed in prior sessions.

### 8. Scan for tokens on public indexes
Search the web for token prefixes (first 8-10 chars of the numeric ID part):
```
web_search("8846059608 telegram bot token")
web_search("ghp_gIPKRC github token")
```

## Scope assessment

When `.env` is exposed, **assume ALL tokens in it are compromised.** The attacker gets everything in one file. List every token and its platform:

| Token | Platform | Risk if compromised |
|-------|----------|-------------------|
| `TELEGRAM_BOT_TOKEN` | Telegram | Read/send messages, modify bot |
| `DISCORD_BOT_TOKEN` | Discord | Read/send in all channels |
| `GITHUB_TOKEN` | GitHub | Push/PR/access all repos |
| `ANTHROPIC_API_KEY` | Anthropic | Use your credits |
| `DEEPSEEK_API_KEY` | DeepSeek | Use your credits |
| `NOTION_API_KEY` | Notion | Read/edit all databases |
| `FIRECRAWL_API_KEY` | Firecrawl | Use your quota |
| etc. | etc. | etc. |

## Routine key rotation (non-compromise)

When you rotate keys proactively (not because of a compromise), the procedure is simpler but has one critical pitfall: **profile `.env` files are independent copies.**

After updating `~/.hermes/.env`, you MUST sync to ALL profile `.env` files. Profiles do NOT source the main `.env` — each has its own copy. If you forget, workers under stale profiles crash-loop silently with HTTP 401.

**Automated safety net:** The pre-spawn watchdog (`/root/.hermes/scripts/pre-spawn-watchdog.py`, cron every 5 min) auto-syncs ALL keys from main `.env` to every profile `.env`, and deduplicates stale copies. If you rotate a key and forget to sync profiles, it catches the drift within minutes. Still, run the sync script below as part of rotation to prevent even one failed spawn.

**Sync procedure:**
```bash
# Sync a specific key to all profiles
bash /root/.hermes/skills/devops/token-compromise-response/scripts/sync-profile-keys.sh DEEPSEEK_API_KEY

# Or sync ALL tokens
bash /root/.hermes/skills/devops/token-compromise-response/scripts/sync-profile-keys.sh ALL
```

**Verification** — all profiles should show the same key suffix (use `head -1`, not `tail -1` — duplicate lines mean `tail` shows the stale copy):
```bash
for p in /root/.hermes/profiles/*/; do
    name=$(basename "$p")
    key=$(grep DEEPSEEK_API_KEY "$p.env" 2>/dev/null | head -1 | awk -F= '{print substr($2, length($2)-7)}')
    echo "  $name: ...${key:-MISSING}"
done
```

See `references/profile-key-sync.md` for the full procedure and the list of profiles that need syncing.

**Real case (2026-06-16):** DeepSeek key rotated. Main `.env` + `researcher` updated. Six other profiles retained the old key. A `coder` task crash-looped 185 times with HTTP 401 before the watchdog caught it. Investigation revealed 50+ stale keys across 7 profiles — every key rotation since profile creation had left frozen copies. The watchdog was extended to sync ALL keys dynamically (not a hardcoded list) and to deduplicate stale duplicate lines.

### Discord: Client Secret ≠ Bot Token

Discord's developer portal has TWO secrets. The **Client Secret** (under OAuth2 → General) is for OAuth2 flows. The **Bot Token** (under Bot → Reset Token) is what the gateway needs. Rotating the wrong one wastes time and doesn't fix the leak. The Bot Token always starts with the base64-encoded bot user ID (e.g., `MTUwNT...`). The Client Secret is a shorter hex string.

### `hermes backup -q` includes .env and auth.json

The `hermes backup -q` (quick snapshot) command explicitly packs `.env` and `auth.json` into the archive. If you're pushing these backups to a repo, the archive ITSELF contains the secrets — even if the repo has `.env` in `.gitignore`. The tar.gz inside the backup commit still leaks tokens.

Check what's inside a committed tar.gz without extracting:
```bash
cd /usr/local/lib/hermes-agent
git show <commit>:backups/hermes-critical-*.tar.gz | tar tzf -
```

If `.env` or `auth.json` appear, the backup leaked tokens.

**Fix**: After `hermes backup -q`, unzip, delete `.env` and `auth.json`, rezip BEFORE pushing. Or use a post-backup script that strips them.

### Notion: integration re-sharing required after token rotation

When you regenerate a Notion integration secret (after a compromise), the NEW integration is effectively a different entity. It does NOT inherit the old integration's sharing permissions. Every database that the old integration had access to must be manually re-shared with the new integration:

1. In Notion, open each database → `...` → `Connect to` → select the new integration name
2. Verify: `curl -s -X POST "https://api.notion.com/v1/search" -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" -H "Content-Type: application/json" -d '{"filter":{"property":"object","value":"database"}}'` — should return your databases
3. Without this step, ALL Notion API writes will fail with `"Could not find database"` or `object_not_found`

**This is self-referencing**: the `hermes-journal` skill that documents Notion pitfalls relies on Notion itself. After rotation, journal entries cannot be written until the integration is re-shared — creating a bootstrapping problem. Fallback: write entries as markdown in `cron/output/` until sharing is restored.

### Telegram: bot ID doesn't change on rotation

Telegram bot tokens are `BOT_ID:BOT_HASH`. When you revoke and regenerate via @BotFather, the bot ID stays the same. Don't be alarmed that the new token starts with the same numeric prefix — it's expected. Verify by checking the hash portion has changed.

### Public fork can't be made private without detaching

If the repo is a fork of a public upstream (e.g., `Seven74AI/hermes-agent` forks `NousResearch/hermes-agent`), the GitHub API returns 422: "Public forks can't be made private." The `network_count` field shows 33k+ repos in the fork network. You must use the GitHub web UI to detach: Settings → scroll to bottom → "Detach fork" button. After detachment, the API PATCH with `{"private": true}` will succeed.

### Cross-repo tree audit: use /user/repos, not /users/ORG/repos

`/users/ORG/repos` only returns public repos. For a full scan including private repos, use `/user/repos?type=all&per_page=100` — this requires the token to have access to all org repos. Private repos containing backup tar.gz files are lower risk but still need cleanup.

### Old commits stay accessible by SHA after force push

Force push removes old commits from branch history, but GitHub keeps them in its object cache. Test: `curl -s -o /dev/null -w '%{http_code}' https://github.com/ORG/REPO/commit/OLD_SHA`. HTTP 200 means the commit is still fetchable. Only GitHub Support can purge the cache — this is a separate step from force push.

## Remediation

### Immediate (do NOW)

1. **Revoke every exposed token** — go to each platform's dashboard and regenerate. The tokens themselves are the vulnerability, not the git commit.

2. **Token rotation guide per platform**:

| Platform | URL | What to click | Token format |
|----------|-----|---------------|--------------|
| Telegram | @BotFather → `/mybots` → your bot | API Token → Revoke | `BOT_ID:HASH` |
| Discord | https://discord.com/developers/applications → your app | **Bot** (left menu) → Reset Token (NOT OAuth2 Client Secret) | `MT...` (base64) |
| GitHub | https://github.com/settings/tokens | Delete old → Generate new token | `ghp_...` (classic) or `github_pat_...` (fine-grained) |
| Anthropic | https://console.anthropic.com/settings/keys | Regenerate | `sk-ant-...` |
| DeepSeek | https://platform.deepseek.com/api_keys | Regenerate | `sk-...` |
| Notion | https://www.notion.so/my-integrations → your integration | Regenerate secret | `ntn_...` or `secret_...` |
| Firecrawl | https://firecrawl.dev → Dashboard → API Keys | Regenerate | `fc-...` |
| Google Cloud | https://console.cloud.google.com/apis/credentials | Reset Secret | hex string |
| AgentMail | https://agentmail.to → Settings → API Keys | Regenerate | — |
| Edgee | https://edgee.ai → Dashboard → API Keys | Regenerate | — |

**GitHub token scopes**: Classic PAT needs only `repo` (covers push/pull/clone + API). Fine-grained PAT: repository access to relevant repos + Contents: Read & Write. `workflow` scope only if GitHub Actions are used.

3. **Verify each new token** before restarting the gateway:
   ```bash
   # Telegram
   curl -s "https://api.telegram.org/bot$TOKEN/getMe"
   # GitHub
   curl -s -o /dev/null -w "HTTP %{http_code}" -H "Authorization: bearer $TOKEN" https://api.github.com/user
   # Discord
   curl -s -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me
   # DeepSeek
   curl -s -o /dev/null -w "HTTP %{http_code}" -H "Authorization: Bearer $TOKEN" https://api.deepseek.com/v1/models
   ```
4. **Update `.env`** with all new tokens. Clean up any commented-out old tokens (they're dead weight and confusing).
5. **Delete the offending branch AND audit all repos** — the same branch name may exist on multiple repos. The leak often spans both public and private repos. **Also check MAIN/MASTER on every repo** — backup cron jobs can push to the wrong repo's main branch without creating a named branch:
   ```bash
   # Delete from remote
   git push origin --delete state-backups
   # Delete local tracking branch
   git branch -D state-backups
   # Scan ALL repos for the same branch AND for backup files on main
   curl -s -H "Authorization: Bearer $TOKEN" \
     "https://api.github.com/user/repos?per_page=100&type=all" | \
     python3 -c "
   import json,sys
   for r in json.load(sys.stdin):
       name = r['full_name']
       # Check for backup tar.gz in tree
   " 

### Within 24h

6. **Contact GitHub Support** to purge the leaked commit from their object cache. Without this, anyone with the commit hash can still access it, even after branch deletion.
7. **Restart the gateway**: `systemctl restart hermes-gateway`
8. **Audit the backup cron job** that pushed the tokens. Fix it to exclude `.env` and `auth.json`. **Critical**: if the cron uses an LLM agent (not `no_agent=true`), the agent WILL ignore security instructions in the prompt — observed June 2026 where the prompt said "Ne JAMAIS pousser .env" but every run pushed raw backups. Convert to a script-based cron (`no_agent=true` with a shell script). See `hermes-backup` skill's "Do NOT use an LLM agent for backup cron jobs" and `scripts/sanitized-backup.sh`.

### Long-term

9. Add `.env` and `auth.json` to a global `.gitignore` in the backup repo.
10. Set up a pre-commit hook that blocks any file containing `_TOKEN=` or `_KEY=` patterns.
10. Make the backup repo private permanently.

## Real-world incidents

- `references/may-2026-telegram-compromise.md` — Full trace: `state-backups` branch with `.env` committed to public fork, Telegram token stolen within 24h, 743 polling conflicts, attacker injecting "Join @A_ToolsX" messages.
- `references/june-2026-token-rotation.md` — Follow-up rotation of all 10 exposed tokens. Pitfalls: Discord Client Secret vs Bot Token confusion, `hermes backup -q` tar.gz containing `.env`, local branch persistence after remote deletion.
- `references/june-2026-post-leak-cleanup.md` — Second cleanup wave (June 13): backup cron still pushing tar.gz to public repo main branch. Cross-repo audit methodology (ALL repos, ALL branches, tree scan). History rewrite for 9k+ commit repos. Old commits accessible by SHA after force push. Fork detachment required before making public repo private.
