# Tracing Git Token Identity in Kanban Workers

> When a commit pushed by a kanban worker shows an unexpected GitHub user as the
> pusher, this recipe reconstructs how the token was used and identifies the source.

## Background

Kanban coders authenticate to GitHub by extracting `GITHUB_TOKEN` from
`~/.hermes/.env` and embedding it directly in the git remote URL:

```bash
TOKEN=$(grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-)
git clone "https://git:${TOKEN}@github.com/Seven74AI/REPO.git" repo
```

The username in the URL (`git`) is cosmetic — GitHub identifies the **pusher**
by the **token value**, not by the URL username. If `GITHUB_TOKEN` contains a
Rafa-Ross token, the pusher shows as Rafa-Ross regardless of the `git` username.

## Investigation Recipe

### 1. Confirm the anomaly

```bash
gh api /repos/Seven74AI/REPO/commits/<sha> --jq '.author.login, .committer.login, .parents[0].html_url'
```

The `committer.login` is the GitHub user whose token was used for the push.
The `author.login` is the git `user.name`/`user.email` set in the local config.

### 2. Verify the rogue user has no current access

```bash
gh api /repos/Seven74AI/REPO/collaborators/<username>  # 404 = not a collaborator
gh api /repos/Seven74AI/REPO/collaborators --jq '.[].login'  # list all
```

### 3. Find the coder session that pushed the commit

```bash
grep -rl "<commit-sha>" /root/.hermes/profiles/coder/sessions/
```

### 4. Extract the token-source command from the session

```python
import json
with open('session_20260519_131049_5b4a1c.json') as f:
    msgs = json.load(f)['messages']
    for i, m in enumerate(msgs):
        if m.get('role') == 'assistant' and m.get('tool_calls'):
            for tc in m['tool_calls']:
                args = tc['function'].get('arguments', '')
                if 'GITHUB_TOKEN' in args:
                    print(f'[{i}] {tc["function"]["name"]}: {args[:500]}')
```

Look for the command that extracts `GITHUB_TOKEN` from `.env` — typically
`grep '^GITHUB_TOKEN=' ~/.hermes/.env | head -1 | cut -d= -f2-`. This
confirms the token source.

### 5. Compare current tokens across all credential stores

```bash
# Main .env (used by coder workers)
grep '^GITHUB_TOKEN=' ~/.hermes/.env | cut -d= -f2 | head -c 20; echo

# gh CLI auth
gh auth token | head -c 20; echo

# git credential store
grep '^https://git:' ~/.git-credentials | head -1 | cut -d: -f3 | cut -d@ -f1 | head -c 20; echo
```

**Tokens can differ across stores.** The `git` credential store entry may hold a
different token than `.env` or `gh auth`. The coder uses `.env` — but if the
token was changed between the incident and now, the `.env` value today won't
match what was used at commit time.

### 6. Check .env modification time vs. commit time

```bash
stat ~/.hermes/.env | grep Modify  # when was it last changed?
```

If `.env` was modified AFTER the suspicious commit date, the token may have
been changed since the incident. Without version history, the original value
is unrecoverable.

### 7. Search for the rogue username in plaintext on the VPS

```bash
find /root/.hermes -maxdepth 3 -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.env" \) \
  ! -path "*/sessions/*" ! -path "*/node_modules/*" | xargs grep -l "<username>" 2>/dev/null
```

If the username appears nowhere in configs — the token was injected at runtime,
not stored in config. Most likely: `.env` `GITHUB_TOKEN` was temporarily set to
the rogue token and later changed back.

## Prevention

- **Periodic verification:** `gh auth status` confirms the active account
- **Never rotate tokens without checking .env:** `GITHUB_TOKEN` in `.env` is the
  source of truth for kanban git pushes; changing it changes the pusher identity
- **If you discover a rogue token in .env:** check ALL recent commits across all
  repos for unexpected pushers — the token was used for every push while it was
  active
