# Substack Paywall Detection

How to determine whether a Substack article was processed with full content or just the free preview.

## The signal: "∙ Paid"

Substack renders **`∙ Paid`** in the byline for hard-paywalled articles. It appears in the head content and is unambiguous:

```
Jun 20, 2026
∙ Paid
```

Articles WITHOUT "∙ Paid" are either free or use a soft paywall (subscription prompts but content is accessible — e.g. Books Behind Borders).

## Checking strategy

### Batch audit (many URLs)

Use `web_extract` with `char_limit=2500` — enough to capture the byline in the head and the "Subscribe to keep reading" gate in the tail.

- **PAID:** "∙ Paid" in head AND total chars < 15K (content gated)
- **FREE:** No "∙ Paid", chars typically 30K–200K
- **DELETED:** "Publication Not Available" or empty content

5 URLs per `web_extract` call, 3 parallel calls per round.

### Single URL check

`web_extract` with any char limit — "∙ Paid" will appear in the head snippet.

## Pitfalls

### ❌ Do NOT use curl from the server IP

Substack rate-limits aggressive curl patterns. After ~60-80 requests the server returns "Too Many Requests" — which contains no "∙ Paid" and produces **false negatives** (everything looks free).

The initial curl script checked all 102 URLs and returned 0 paywalled — all false negatives from rate limiting.

### ❌ Do NOT use web_extract with char_limit < 2000

"∙ Paid" appears after the author avatar and date — it can be outside the head window with very low char limits.

## Paywalled authors (known)

| Author | Pattern |
|--------|---------|
| Dr. Marizelle | Some articles paid ("∙ Paid"), some free |
| Unbekoming | Most free, occasional paid (book reviews/summaries tend to be paid) |
| Jana Sutoova | Some articles paid |

## Notes (vs Articles)

Substack Notes (`substack.com/@user/note/...`) are never paywalled — skip them in audits.
