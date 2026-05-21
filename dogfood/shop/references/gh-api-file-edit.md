# GitHub API File Edit (No Clone)

Edit a single file directly on GitHub via `gh api` — useful when the local
clone is corrupted or you need an atomic one-file fix without cloning the
entire repo.

## When to Use

- Local clone is corrupted (`bad object`, `unresolved deltas`)
- Fork is out of sync with upstream and only one file needs fixing
- Quick hotfix without setting up a full clone
- Working copy exists but git operations fail

## Prerequisites

- `gh` authenticated as the repo owner (check: `gh auth status`)
- The target repo must be writable by the authenticated user

## Steps

### 1. Get current file SHA

```bash
gh api repos/OWNER/REPO/contents/PATH/TO/FILE --jq '.sha'
```

### 2. Download current content

```bash
gh api repos/OWNER/REPO/contents/PATH/TO/FILE --jq '.content' | base64 -d > /tmp/file.yml
```

Verify the content has what you expect to change:
```bash
grep 'pattern' /tmp/file.yml
```

### 3. Patch the file

```bash
sed -i 's/OLD_TEXT/NEW_TEXT/' /tmp/file.yml
# Or use any editor
```

Verify the change:
```bash
grep 'NEW_TEXT' /tmp/file.yml
```

### 4. PUT the patched file back

```bash
SHA="abc123..."  # from step 1
gh api --method PUT repos/OWNER/REPO/contents/PATH/TO/FILE \
  -f message="fix: description of change" \
  -f content="$(base64 -w0 /tmp/file.yml)" \
  -f sha="$SHA"
```

## Pitfall: Shell Quoting Breaks base64 Content

The `-f content="$(base64 -w0 ...)"` pattern in bash can fail with
`"does not match <sha>"` (HTTP 409) even when the SHA is correct.
This happens because shell interpolation corrupts the base64 string
(especially with special characters or long content).

**Fix:** Use `execute_code` (Python) for the PUT call instead of bash:

```python
import base64, json, subprocess

# Read patched file
with open("/tmp/file.yml") as f:
    content = f.read()

# Get SHA (if needed fresh)
sha_result = subprocess.run(
    ["gh", "api", "repos/OWNER/REPO/contents/PATH/TO/FILE", "--jq", ".sha"],
    capture_output=True, text=True
)
sha = sha_result.stdout.strip()

# Encode and PUT
encoded = base64.b64encode(content.encode()).decode()
body = json.dumps({
    "message": "fix: description",
    "content": encoded,
    "sha": sha
})

result = subprocess.run(
    ["gh", "api", "--method", "PUT",
     "repos/OWNER/REPO/contents/PATH/TO/FILE",
     "--input", "-"],
    input=body, capture_output=True, text=True
)
print(result.stdout[:300])
```

This avoids all shell quoting issues by piping JSON directly to `gh api --input -`.

## Verification

```bash
# API (always current, no CDN cache)
gh api repos/OWNER/REPO/contents/PATH/TO/FILE --jq '.content' | base64 -d | grep 'pattern'

# raw.githubusercontent.com may be cached — wait a few minutes
curl -s https://raw.githubusercontent.com/OWNER/REPO/main/PATH/TO/FILE | grep 'pattern'
```

## Real Example (Shop, 2026-05-21)

Fixed `|| true` on `Seven74AI/shop`'s `deploy.yml` when the local clone at
`/tmp/shop-original` was corrupted (`bad object`). Upstream `mnlamart/shop`
was already clean. Used `execute_code` to avoid shell quoting issues with
the 8500-char base64 payload.
