#!/usr/bin/env bash
# Sync API tokens from main .env to all profile .env files.
# Handles duplicate key lines (dedups before syncing).
# Run after any key rotation to prevent workers from crash-looping with HTTP 401.
#
# Usage: bash sync-profile-keys.sh [TOKEN_NAME]
#   TOKEN_NAME defaults to DEEPSEEK_API_KEY. Use 'ALL' to sync every token
#   matching the pattern *_KEY, *_TOKEN, or *_SECRET.
#
# The pre-spawn watchdog (/root/.hermes/scripts/pre-spawn-watchdog.py) also
# does this automatically every 5 minutes as a safety net.

set -euo pipefail

MAIN_ENV="/root/.hermes/.env"
PROFILES_DIR="/root/.hermes/profiles"
TOKEN="${1:-DEEPSEEK_API_KEY}"

if [ ! -f "$MAIN_ENV" ]; then
    echo "ERROR: $MAIN_ENV not found" >&2
    exit 1
fi

if [ "$TOKEN" = "ALL" ]; then
    TOKENS=$(grep -oP '^[A-Z][A-Z_]+(?==)' "$MAIN_ENV" | grep -E '_(KEY|TOKEN|SECRET)$')
else
    TOKENS="$TOKEN"
fi

changed=0
errors=0

for profile_dir in "$PROFILES_DIR"/*/; do
    profile=$(basename "$profile_dir")
    env_file="${profile_dir}.env"

    if [ ! -f "$env_file" ]; then
        continue
    fi

    for tok in $TOKENS; do
        main_val=$(grep "^${tok}=" "$MAIN_ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
        if [ -z "$main_val" ]; then
            continue  # token not in main .env, skip
        fi

        # Count occurrences — if >1, there's a stale duplicate
        occurrences=$(grep -c "^${tok}=" "$env_file" 2>/dev/null || echo 0)
        if [ "$occurrences" -gt 1 ]; then
            # Keep first occurrence, remove rest
            first_line=$(grep -n "^${tok}=" "$env_file" | head -1 | cut -d: -f1)
            tmpfile=$(mktemp)
            awk -v key="$tok" -v keep="$first_line" '
                NR == keep { print; next }
                $0 ~ "^"key"=" { next }
                { print }
            ' "$env_file" > "$tmpfile"
            mv "$tmpfile" "$env_file"
            echo "✓ $profile: deduped ${tok} (${occurrences} → 1)"
        fi

        profile_val=$(grep "^${tok}=" "$env_file" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")

        if [ "$main_val" != "$profile_val" ]; then
            sed -i "s|^${tok}=.*|${tok}=${main_val}|" "$env_file"
            main_suffix="${main_val: -8}"
            profile_suffix="${profile_val: -8}"
            echo "✓ $profile: ${tok} synced (${profile_suffix:-MISSING} → ${main_suffix})"
            changed=$((changed + 1))
        fi
    done
done

echo ""
echo "Profiles checked: $(ls -d "$PROFILES_DIR"/*/ 2>/dev/null | wc -l)"
echo "Keys synced: $changed"
