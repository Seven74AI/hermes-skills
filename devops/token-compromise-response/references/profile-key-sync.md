# Profile Key Sync — After Every Token Rotation

When you rotate an API key (DeepSeek, Anthropic, etc.), updating `~/.hermes/.env` is NOT enough. Hermes profile `.env` files are **independent copies** — they do NOT source the main `.env`. A new key in the main `.env` will NOT reach workers running under profiles.

## Automated protection

The **pre-spawn watchdog** (`/root/.hermes/scripts/pre-spawn-watchdog.py`, cron every 5 min) auto-syncs ALL keys from main `.env` to every profile `.env`. If you rotate a key and forget to sync profiles, the watchdog fixes it within 5 minutes. It also deduplicates stale duplicate lines in profile `.env` files (a common problem when keys are updated with `sed` which only replaces the first occurrence).

**This is a safety net, not a replacement for proper rotation.** Run the sync script below as part of any rotation to prevent even a single failed worker spawn.

## The trap

You rotate the key → update main `.env` → restart gateway → everything looks fine. But workers spawned under stale profiles keep using the OLD key. They die in 4 seconds with HTTP 401, the dispatcher respawns them, and the cycle continues silently. **185 crash-loops in 4.5 hours** before the watchdog noticed (2026-06-16, DeepSeek key rotation).

## Which profiles need syncing

| Profile | Worker role | Has own .env |
|---------|------------|-------------|
| `researcher` | KB text extraction | Yes |
| `researcher-videos` | KB video/transcription | Yes |
| `coder` | Code/PR work | Yes |
| `planner` | Task decomposition | Yes |
| `reviewer` | Code review | Yes |
| `hermes-devops` | Ops tasks | Yes |
| `edgee-planner` | Edgee-specific | Yes |
| `twitter-coder` | Twitter automation | Yes |

All 8 profiles have independent `.env` files. A key rotation MUST touch all of them.

## Sync procedure (after any key rotation)

```bash
# Sync a specific key
bash /root/.hermes/skills/devops/token-compromise-response/scripts/sync-profile-keys.sh DEEPSEEK_API_KEY

# Sync ALL tokens (after a full rotation)
bash /root/.hermes/skills/devops/token-compromise-response/scripts/sync-profile-keys.sh ALL
```

The script is idempotent — only changes profiles where the key differs. It also removes duplicate lines for the same key (a common silent bug from repeated `sed` replacements).

## Verification

**Use `head -1`, not `tail -1`.** Duplicate keys in a `.env` file mean `tail -1` shows the stale copy even after syncing:

```bash
for p in /root/.hermes/profiles/*/; do
    name=$(basename "$p")
    key=$(grep DEEPSEEK_API_KEY "$p.env" 2>/dev/null | head -1 | awk -F= '{print substr($2, length($2)-7)}')
    echo "  $name: ...${key:-MISSING}"
done
echo "  main: ...$(grep DEEPSEEK_API_KEY /root/.hermes/.env | head -1 | awk -F= '{print substr($2, length($2)-7)}')"
```

All profiles should show the same suffix as `main`.

## Real case (2026-06-16)

DeepSeek key was rotated (old → new). Main `.env` + `researcher` + `researcher-videos` were updated. Six other profiles (`coder`, `planner`, `reviewer`, `hermes-devops`, `edgee-planner`, `twitter-coder`) retained the old key. A task assigned to `coder` crash-looped 185 times with HTTP 401 before the kanban block watchdog detected it.

**Follow-up (same day):** The pre-spawn watchdog was expanded to dynamically sync ALL keys (not just a hardcoded list) and deduplicate stale copies. On its first dynamic run it found 50+ stale keys across 7 profiles — Telegram, Discord, GitHub, Notion, Firecrawl tokens were all frozen at profile creation time. Even after syncing values, duplicate `FIRECRAWL_API_KEY` lines caused the watchdog to re-report the same key every 5 minutes. Root cause: `sed -i` only replaced the first occurrence; the stale duplicate survived and `tail -1` (or dict-overwrite) kept picking it up. Fixed in the watchdog by deduplicating before comparing.
