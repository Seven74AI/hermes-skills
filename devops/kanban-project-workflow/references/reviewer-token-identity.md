# Reviewer Token Identity Pitfall

**Symptom:** GitHub rejects the reviewer's approval with `"Can not approve your own pull request"` despite the reviewer being a different GitHub account (`hermes-sevenai-reviewer[bot]`).

**Root cause:** The reviewer profile's `.env` contains the same `GITHUB_TOKEN` value as the main account (coder). Both use the same PAT — GitHub sees both accounts as the same identity.

**Detection:**
```bash
echo "Main: $(gh auth token | head -c 10)..."
echo "Reviewer: $(grep '^GITHUB_TOKEN=' /root/.hermes/profiles/reviewer/.env | cut -d= -f2 | head -c 10)..."
```
If they match → same token → "can't approve your own PR".

**Consequences:**
- `reviewDecision: REVIEW_REQUIRED` persists even after the reviewer submits APPROVED
- Dismissing the CHANGES_REQUESTED review doesn't help — GitHub still requires an APPROVED review from a DIFFERENT account
- All CI can be green but the PR remains `mergeStateStatus: BLOCKED`
- The only way to unblock is manual approval from a real different account

**Fix:**
1. Configure a separate PAT for the reviewer bot account
2. Or use GitHub App installation tokens (set `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_INSTALLATION_ID` in reviewer `.env`)
3. In the short term: ask a human to approve the PR manually

**Observed:** 2026-07-16, music-library board. PR #203 had all CI green, reviewer submitted APPROVED in kanban, but `reviewDecision: REVIEW_REQUIRED` because the reviewer token (`ghp_lpVWwt...`) matched the main account token. Resolved by user manual approval.
