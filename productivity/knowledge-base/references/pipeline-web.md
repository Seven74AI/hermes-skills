# Generic Web Pipeline

Any website without a dedicated pipeline (blogs, reference sites, medical databases, personal sites). Firecrawl → deep analysis → MinIO archive → Obsidian note.

## Phase 0 — Dedup + Firecrawl health check

```bash
# Dedup
if grep -rql "source_url: $URL" "$OBSIDIAN_VAULT_PATH/Knowledge base/" 2>/dev/null; then
    echo "Already in vault — skip"
    exit 0
fi

# Firecrawl health
curl -s --max-time 5 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","formats":["markdown"]}' > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Firecrawl down — skip"
    exit 0
fi
```

## Phase 1 — Extraction

```bash
curl -s --max-time 60 http://localhost:3002/v2/scrape \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"$URL\",\"formats\":[\"markdown\"],\"waitFor\":3000}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['data']['markdown'])" \
  > /tmp/web_raw.md
```

## Phase 2 — Deep analysis (worker)

Follow the deep treatment standard from `knowledge-base` SKILL.md (Template section). No light template. Required depth:

- **Read the ENTIRE source** — never rely on `web_extract` summaries. Use Firecrawl full markdown, save to `/tmp/`, read completely before writing
- **Key Claims** — ≥4 specific claims with direct quotes (`>`) and analysis
- **Section-by-section analysis** — dominant section, longer than Key Claims + Critical Analysis combined
- **Context** — who wrote this, why now, conflicts of interest
- **Critical Analysis** — what's new vs restating, omissions, self-interest
- **Nuances** — limitations, exaggerations, blind spots
- **Size target:** 15 000-25 000 chars for long-form (>5000 words)
- **Coverage verification before pushing:** After writing, check the note covers every section of the source. For structured content, diff section headers. For unstructured, skim every 50th line of the raw file. A note that misses entire sections or chapters is not deep treatment — it's an incomplete read.
- **See Also** — only existing vault notes (grep before linking)

## Phase 3 — MinIO archive

```bash
SLUG="<site>-<title-slug>"
mc cp /tmp/web_raw.md "minio/knowledge-base/articles/${SLUG}.md"
```

## Phase 4 — Obsidian note

Template per SKILL.md with `minio:` field:
```yaml
minio: http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/articles/<slug>.md
```

## Phase 5 — Git push

```bash
cd "$OBSIDIAN_VAULT_PATH"
git add "Knowledge base/${SLUG}.md"
git commit -m "add: ${SLUG}"
git push
```
