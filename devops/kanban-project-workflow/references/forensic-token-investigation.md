# Security Incident Investigation — Foreign Token Trace

Pattern used to investigate how a foreign GitHub token (Rafa-Ross) was used to push a commit on the-swarm (ea988f2, 2026-05-19).

## 1. Identify the anomaly

```bash
# Check commit pusher vs author
gh api /repos/<owner>/<repo>/commits/<sha> --jq '{author: .author.login, committer: .committer.login}'
# Git author (set locally) vs GitHub pusher (determined by token)
```

## 2. Search all repos for foreign contributors

```bash
for repo in $(gh repo list <org> --json name --jq '.[].name'); do
  echo "=== $repo ==="
  gh api /repos/<org>/$repo/collaborators --jq '.[].login' 2>/dev/null | grep -v "<known_user>"
done
```

## 3. Find the session that produced the commit

```bash
# Search session DB for the commit SHA
grep -rl "<commit_sha>" /root/.hermes/profiles/coder/sessions/

# Or use session_search with the commit message keywords
session_search(query="<commit message keywords>")
```

## 4. Reconstruct the token injection mechanism

From the session, extract the git commands to see HOW the token was used:

```python
import json
with open('<session_file>') as f:
    data = json.load(f)
    for m in data['messages']:
        for tc in m.get('tool_calls', []):
            if tc['function']['name'] == 'terminal':
                args = tc['function']['arguments']
                if any(kw in args for kw in ['git', 'GITHUB', 'TOKEN', 'clone', 'push']):
                    print(args)
```

**Common pattern found:** Kanban coder extracts `GITHUB_TOKEN` from `/root/.hermes/.env` and embeds it in the git remote URL: `git remote set-url origin "https://git:$TOKEN@github.com/..."`. GitHub identifies the pusher by the token, not the username in the URL.

## 5. Audit current token state

```python
# Check all GitHub tokens present
import subprocess, json

# From .env
for path in ["/root/.hermes/.env", "/root/.hermes/profiles/coder/.env"]:
    with open(path) as f:
        for line in f:
            if line.startswith("GITHUB_TOKEN="):
                token = line.strip().split("=", 1)[1]

# From git-credentials
with open("/root/.git-credentials") as f:
    for line in f:
        if "://" in line:
            parts = line.split("://")[1].split("@")[0].split(":", 1)
            if len(parts) == 2:
                token = parts[1]

# Test each token
r = subprocess.run(["curl", "-s", "-H", f"Authorization: Bearer {token}", 
    "https://api.github.com/user"], capture_output=True, text=True)
print(json.loads(r.stdout).get("login"))
```

## 6. Check .env modification timeline

```bash
stat /root/.hermes/.env | grep Modify
# If .env was modified AFTER the commit date, the token was changed since
```

## 7. Determine root cause

Most likely: GITHUB_TOKEN in `.env` was temporarily set to a foreign token (copy-paste error, shared credential, test) and later changed back. The `.env` is NOT tracked in git — no version history.

## Real case: Rafa-Ross on the-swarm (2026-05-30)

- Commit ea988f2, pushed May 19 11:27 by coder session `session_20260519_112659_2aff72` (task t_fcb935ea)
- Token extracted from `/root/.hermes/.env` and embedded in git remote URL
- .env last modified May 25 (6 days after commit) — token changed in between
- All current tokens = Seven74AI. Rafa-Ross token absent.
- Rafa-Ross GitHub account: created Apr 26, no bio/org, minimal profile
- Not a collaborator on any Seven74AI repo
- Full report: Notion page under "Hermes Sevenai"