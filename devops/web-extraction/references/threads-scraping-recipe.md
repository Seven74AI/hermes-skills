# Threads.com Scraping Recipe

Threads (Meta) is a fully JS-rendered React SPA. The HTML shell contains only the first line, nav chrome, and engagement counts. All body content — the thread replies, the actual post text — loads via client-side JavaScript.

## Working cURL (Firecrawl REST API)

```bash
curl -s -X POST http://localhost:3002/v1/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.threads.com/@adhd.thriver/post/DYneGuxCrm-","formats":["markdown"],"waitFor":3000}'
```

Key parameters:
- `waitFor: 3000` — 3 second delay for React hydration. Without this, only the static shell is returned.
- `formats: ["markdown"]` — cleaner output than HTML

## Working Python SDK

```python
from firecrawl import Firecrawl
fc = Firecrawl(api_url='http://localhost:3002')
result = fc.scrape(
    url='https://www.threads.com/@adhd.thriver/post/DYneGuxCrm-',
    formats=['markdown'],
    wait_for=3000
)
md = result.model_dump().get('markdown', '')
```

## Expected Output Size

- Shell only (no JS): ~2000 chars — just "If you date someone with ADHD..." + engagement counts + login prompt
- Full render (wait_for=3000): ~8800 chars — all thread replies, tools/tips, comments

Use this size test as a quick diagnostic: if `len(md) < 3000`, JS didn't render.

## Verified Content Markers

These phrases should ALL be present in the full render:
- "Text Spirals"
- "Sharp Feedback"
- "Infinite Check"
- "Apology Habbit"
- "RSD VIGILANCE"
- "Sensory Grounding"
- "Update Silence"
- "Rejection Sensitive Dysphoria"

If any are missing, the page didn't fully render — increase `wait_for` or check playwright logs.
