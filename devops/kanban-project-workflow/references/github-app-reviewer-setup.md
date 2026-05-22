# GitHub App Setup — hermes-sevenai-reviewer

The reviewer agent must approve PRs as a different identity from the coder.
A GitHub App owned by Seven74AI, installed on target repos, is the setup.

## App Configuration

- **Name:** `hermes-sevenai-reviewer`
- **App ID:** 3788528
- **Installation ID:** 134194993
- **Permissions:** `Pull Requests: Read & Write`, `Contents: Read & Write`, `Metadata: Read`
- ⚠️ **CRITICAL: `Contents: Write` is MANDATORY.** Without it, the app's reviews show `authorAssociation: "NONE"` and do NOT count toward the required approval count. GitHub requires write-level access for a review to satisfy branch protection.
- **Private key:** `~/.hermes/profiles/reviewer/home/.config/hermes-sevenai-reviewer.pem`

## Why an App

- Appears as `hermes-sevenai-reviewer[bot]` — distinct from `Seven74AI` (PR author)
- GitHub counts the bot's approve for branch protection
- Fine-grained permissions (just Pull Requests: R&W + Contents: R)
- No GitHub seat consumed
- Tokens are generated fresh each run (1h expiry)
- Same pattern used by Dependabot, Renovate, CodeRabbit

## Token Generation

The reviewer profile has a helper script that generates a fresh installation token:
```
~/.hermes/profiles/reviewer/home/.config/gen-installation-token.py
```

Usage (from reviewer worker):
```bash
TOKEN=$(python3 ~/.config/gen-installation-token.py)
```

The token is valid for 1 hour. The reviewer generates a fresh one at the start
of each run. Tokens are passed inline to `gh api` via `-H "Authorization: Bearer $TOKEN"`.

## Branch Protection (configured via API)

| Repo | Approvals | Required CI checks |
|------|-----------|-------------------|
| `Seven74AI/shop` | 1 | `lint`, `typecheck`, `vitest`, `playwright` |
| `Seven74AI/the-swarm` | 1 | `ci` |

Auto-merge enabled on both repos (`allow_auto_merge: true`).
Dismiss stale reviews on new commits: enabled.

## Approve a PR (reviewer agent)

```bash
TOKEN=$(python3 ~/.config/gen-installation-token.py)
gh api repos/Seven74AI/shop/pulls/42/reviews \
  -H "Authorization: Bearer $TOKEN" \
  -f event=APPROVE -f body='LGTM — reviewed by agent'
```

## Request Changes

```bash
TOKEN=$(python3 ~/.config/gen-installation-token.py)
gh api repos/Seven74AI/shop/pulls/42/reviews \
  -H "Authorization: Bearer $TOKEN" \
  -f event=REQUEST_CHANGES -f body='Please fix X in file Y'
```

## Verify Setup

```bash
python3 ~/.hermes/profiles/reviewer/home/.config/gen-installation-token.py
# → prints a 40-char token
```
