# Substack Pipeline

Substack articles (long-form newsletters). Extraction via Firecrawl only.

## Prerequisites

- **Firecrawl** : `http://localhost:3002/v2/scrape`
- **Queue file** : `/root/.hermes/queues/skipped_substack.txt` — URLs queued when Firecrawl is down

## Planner (before ticket creation)

### Dedup check

```bash
if grep -rql "source_url: SUBSTACK_URL" "$OBSIDIAN_VAULT_PATH/Knowledge base/" 2>/dev/null; then
    echo "Already in vault — skip"
    exit 0
fi
```

### Firecrawl health check

```bash
curl -s --max-time 5 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"]}' > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "SUBSTACK_URL" >> /root/.hermes/queues/skipped_substack.txt
    exit 0
fi
```

### Create kanban ticket

```bash
hermes kanban --board default create \
  --assignee researcher \
  --skill knowledge-base \
  --max-runtime 600 \
  "KB: <publication> — <title>"
```

## Researcher worker

### Phase 0 — Extraction

```bash
curl -s --max-time 30 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"SUBSTACK_URL","formats":["markdown"]}'
```

Returns: `data.markdown` (full article), `data.metadata` (title, author, date).

## Phase 1 — Metadata

| Field | Source |
|-------|--------|
| `title` | `<title>` or first `#` in markdown |
| `author` | `<meta name="author">` |
| `date` | `<meta property="article:modified_time">` |
| `publication` | Domain name (e.g. `aisisterslab.substack.com` → "AI Sisters Lab") |
| `canonical_url` | `<link rel="canonical">` |

## Phase 2 — Markdown cleanup

```python
import re

md = re.sub(r'\[Prendre rendez-vous avec le Lab\]\([^)]+\)(\n\n)?', '', md)
md = re.sub(r'S\'abonner\n\n', '', md)
md = re.sub(r'Merci d\'avoir lu.*?mon travail\.(\n\n)?', '', md)
md = re.sub(r'={30,}\n', '', md)
md = re.sub(r'-{30,}\n', '', md)
md = re.sub(r'\[!\[Avatar.*?\]\([^)]+\)\]\([^)]+\)\n?', '', md)
md = re.sub(r'#### Discussion à propos de ce post.*', '', md, flags=re.DOTALL)
```

## Phase 3 — Obsidian note

### Template

```markdown
---
topic: [<topics>]
date: YYYY-MM-DD
source: <publication>, <date>
source_url: <canonical_url>
confidence: plausible
tags: [<tags>]
---

# <title>

## Summary
2-3 sentences. The essentials.

## Key Points
- Point 1
- Point 2

## Analysis
Context, trends, implications.

## Reliability
⚠️ plausible — newsletter source.

## Source
- [<original title>](<canonical_url>) — <publication>, <date>
```

### Slug

`<publication-slug>_<title-slug>`. Lowercase.

### Tags

- `substack` always
- `<publication-slug>` always
- `ai`, `regulation`, `ai-act`, `fine-tuning`, `open-source` based on content

## Phase 4 — Git push

```bash
cd "$OBSIDIAN_VAULT_PATH"
git add "Knowledge base/<slug>.md"
git commit -m "add: <slug>"
git push
```
