# Detecting Placeholder Tokens

When terminal output shows `***` for a token, you can't tell if it's Hermes redacting a real token or a literal placeholder. Use `xxd` to see the raw bytes.

## Quick check

```bash
grep "KEY_NAME" /path/to/.env | xxd | head -2
```

## Interpreting results

**Real token (Hermes-redacted):**
```
00000000: 414e 5448 524f 5049 435f 4150 495f 4b45  ANTHROPIC_API_KE
00000010: 593d 736b 2d61 6e74 2d61 7069 3033 2d50  Y=sk-ant-api03-P
```
→ The raw bytes show the real token prefix (e.g. `sk-ant-api03-P...`). The `***` in display is Hermes redaction. This token is real.

**Literal placeholder:**
```
00000000: 4749 5448 5542 5f54 4f4b 454e 3d22 4d4f  GITHUB_TOKEN="MO
00000010: 434b 5f47 4954 4855 425f 544f 4b45 4e22  CK_GITHUB_TOKEN"
```
→ The raw bytes show `"MOCK_GITHUB_TOKEN"` — the `***` in display is Hermes treating the mock string itself as a secret to hide, but it's actually a placeholder. This token is NOT real.

## Common placeholder patterns

| Display | Raw bytes | Meaning |
|---|---|---|
| `GITHUB_TOKEN="***"` | `"MOCK_GITHUB_TOKEN"` | Placeholder |
| `GITHUB_TOKEN=***` | `ghp_xxxx...` (40 chars) | Real token (classic PAT) |
| `API_KEY=***` | `sk-ant-api03-xxxx...` | Real token |
| `SECRET="***"` | `"MOCK_SESSION_SECRET"` | Placeholder |

## When you find a placeholder

Don't block the task asking the user to "put the token in the project .env" unless you've confirmed the token is actually needed AT THE APPLICATION LEVEL (e.g., external API calls from the app code). For git operations, the token should come from the git remote URL or the main Hermes environment — not the project .env.
