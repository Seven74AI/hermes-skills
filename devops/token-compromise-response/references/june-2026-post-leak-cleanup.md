# June 2026 Post-Leak Cleanup — Cross-Repo Audit & History Rewrite

Full timeline: `state-backups` branch with `.env` pushed to public `Seven74AI/hermes-agent` fork. Tokens rotated May 29. On June 13, discovered that backup cron was STILL pushing raw `.env`/`auth.json` tar.gz files — this time to `main` of the public repo. Second cleanup required.

## What was found

### Branch `state-backups` existed on TWO repos
- `Seven74AI/hermes-agent` (public fork) — DELETED
- `Seven74AI/hermes-backup` (private) — DELETED

### Backup commits on MAIN of public repo
13 commits on `hermes-agent/main` contained `backups/hermes-critical-*.tar.gz` files. These were pushed by the quick backup cron (every 2h) which was supposed to push to the private backup repo but the LLM agent targeted the wrong repo.

### Old commits accessible by SHA after force push
After `git filter-branch` and force push, the old commits with tar.gz files were STILL accessible via:
- `https://github.com/Seven74AI/hermes-agent/commit/e591c317...` (HTTP 200)
- `https://raw.githubusercontent.com/Seven74AI/hermes-agent/e591c317.../backups/hermes-critical-20260613-184026.tar.gz` (downloadable)

The tar.gz contained `.env` and `auth.json`. GitHub Support must be contacted to purge the object cache.

## Audit methodology (cross-repo)

```
1. List ALL repos (public + private):
   curl -s -H "Authorization: Bearer $TOKEN" \
     "https://api.github.com/users/ORG/repos?per_page=100&type=all"

2. For EACH repo, check ALL branches for tar.gz/.env:
   - Tree scan: GET /repos/ORG/REPO/git/trees/BRANCH?recursive=1
   - Filter for: *.tar.gz, *.zip, .env, auth.json
   - NOTE: trees can be truncated — check multiple branches

3. For EACH repo, search commits for backup patterns:
   git log --all --oneline --diff-filter=A -- '*.tar.gz' '*.zip' '.env' 'auth.json'

4. If the repo is a FORK of a public upstream:
   - It CANNOT be made private without detaching the fork first
   - API returns 422: "Public forks can't be made private"
   - Must use GitHub web UI: Settings → "Detach fork" button
   - Then PATCH /repos/ORG/REPO with {"private": true}

5. After history rewrite, VERIFY old commits are NOT accessible:
   curl -s -o /dev/null -w '%{http_code}' \
     "https://github.com/ORG/REPO/commit/OLD_SHA"
   # 200 = still accessible → contact GitHub Support
   # 404 = purged
```

## History rewrite for large repos (9k+ commits)

```bash
# Clone with blob filtering to speed up
git clone --filter=blob:none https://github.com/ORG/REPO.git

# filter-branch on main only (not --all — too slow with 300+ branches)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch backups/*.tar.gz backups/*.zip 2>/dev/null; true' \
  --prune-empty -- main

# Clean up backup refs filter-branch creates
git for-each-ref --format='%(refname)' refs/original/ | xargs -r git update-ref -d

# Expire reflog and gc before pushing
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push --force origin main
```

**Pitfall**: After `git gc --prune=now`, old objects are gone locally but still on GitHub's cache. Test with `curl` to confirm.

## Cron fix

The LLM-driven quick backup cron (`no_agent=false`) was ignoring explicit security instructions. Replaced with `no_agent=true` + `sanitized-backup.sh` script. The script strips `.env` and `auth.json` unconditionally — the LLM can't skip steps.

See `hermes-backup` skill for the script and deployment instructions.

## False positives

- `.env.example` files in project repos (`music-library`, `shop`) are templates — harmless
- `agent/redact.py` and `tools/skills_guard.py` contain regex patterns for `ghp_`, `sk-ant-` etc. — these are the REDACTION code, not actual secrets
