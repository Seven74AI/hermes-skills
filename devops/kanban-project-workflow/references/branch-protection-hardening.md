# Branch Protection Hardening

Standard branch protection configuration to prevent admin bypass of CI gates.

## Default Configuration

```bash
REPO="Seven74AI/shop"  # or any fork/direct repo

echo '{
  "required_status_checks": {
    "strict": false,
    "contexts": ["lint", "typecheck", "vitest", "playwright-gate"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}' | gh api "repos/$REPO/branches/main/protection" -X PUT --input -
```

## Key settings

| Setting | Value | Why |
|---------|-------|-----|
| `enforce_admins` | `true` | Even repo admins must pass required checks |
| `required_approving_review_count` | `1` | Reviewer (different identity) must approve |
| `dismiss_stale_reviews` | `true` | New push invalidates old approval — prevents bypass |
| `allow_force_pushes` | `false` | No force push to main |
| `required_status_checks.contexts` | `["lint","typecheck","vitest","playwright-gate"]` | All must be green to merge |

## Verification

```bash
gh api "repos/$REPO/branches/main/protection" --jq '{
  enforce_admins: .enforce_admins.enabled,
  required_reviews: .required_pull_request_reviews.required_approving_review_count,
  checks: .required_status_checks.contexts,
  dismiss_stale: .required_pull_request_reviews.dismiss_stale_reviews
}'
```

## Limitation: Cannot Stop Owner `--admin`

Even with `enforce_admins: true`, the repo **owner** can still use
`gh pr merge --admin` to bypass ALL protection. The only way to prevent this
is to ensure the coder does not have owner/admin access:

- Transfer repo ownership to a bot account
- Or use a GitHub App for coder operations (app is never admin)

## Applied To

- `Seven74AI/shop` — 2026-05-28 (after 7 red-CI merges)
