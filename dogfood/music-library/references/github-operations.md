# GitHub Operations

All issue and PR operations on the fork must pass `--repo Seven74AI/music-library` explicitly. The local clone resolves `gh` to upstream by default.

## Issue creation

```bash
gh issue create \
  --repo Seven74AI/music-library \
  --title "..." \
  --body "..." \
  --label "ready-for-agent"
```

## Issue labels

```bash
gh issue edit <number> --repo Seven74AI/music-library --add-label "ready-for-agent"
```

## Issue list

```bash
gh issue list --repo Seven74AI/music-library --state open --label ready-for-agent
```

## PR creation

```bash
gh pr create \
  --repo Seven74AI/music-library \
  --base main \
  --title "..." \
  --body "..."
```

## Consolidation PR to upstream (cross-repo)

When the token doesn't have write access to the upstream fork (`mnlamart/music-library`), use a cross-repo PR. The head branch lives on `Seven74AI/music-library`:

```bash
gh pr create \
  -R mnlamart/music-library \
  --base main \
  --head Seven74AI:main \
  --title "Consolidation: sync from Seven74AI fork" \
  --body "Sync from Seven74AI/music-library main."
```

Auto-merge requires write access to the target repo — consolidation PRs need manual merge by upstream maintainers.

## Token verification (git success ≠ valid token)

Both repos are **public**, so `git fetch`/`git ls-remote` succeed anonymously even with a
dead or bogus token — read-only git ops on a public repo never exercise the token. "git
fetch worked" is NOT proof the token is valid.

```bash
TOKEN=$(git config --get remote.origin.url | sed -E 's#https://[^:]+:([^@]+)@.*#\1#')
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" https://api.github.com/user
# 200 = valid. 401 "Bad credentials" = dead → get a fresh PAT.
```

When `gh` 401s but git works: (1) confirm the repo is public —
`curl -s -o /dev/null -w "%{http_code}\n" https://api.github.com/repos/Seven74AI/music-library` → `200`;
(2) test the token against the API, not git; (3) confirm git isn't using a
`credential.helper store` (`~/.git-credentials`) that overrides the URL token — isolate with
`git -c credential.helper= ls-remote <url>`. A 401 = dead token (revoked/expired); 403 = wrong scopes.
