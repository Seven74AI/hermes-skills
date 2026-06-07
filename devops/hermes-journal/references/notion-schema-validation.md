# Notion Schema Validation — Preventing Silent Property Drift

Notion's API is permissive: it returns HTTP 200 for page creation even when your payload references property names that don't exist in the database schema. Unrecognized keys are silently dropped — the page is created but those properties are empty. This allows template/schema drift to persist undetected for months.

## The Pattern

Before constructing a page creation payload, validate your property names against the live database schema:

```bash
# Step 1: Fetch the live schema (MUST use 2022-06-28 — 2025-09-03 omits properties!)
curl -s "https://api.notion.com/v1/databases/${DATABASE_ID}" \
  -H "Authorization: Bearer ${NOTION_API_KEY}" \
  -H "Notion-Version: 2022-06-28" \
  -o /tmp/notion_schema.json

# Step 2: Extract property names
python3 -c "
import json
with open('/tmp/notion_schema.json') as f:
    db = json.load(f)
for name, prop in db.get('properties', {}).items():
    print(f'{name}: {prop[\"type\"]}')
"
```

Expected output for Hermes Ops Journal:
```
Impact: select
Date: date
Category: select
Name: title
```

## Why 2022-06-28 Matters

| API Version | `GET /databases/{id}` response |
|-------------|-------------------------------|
| `2022-06-28` | Includes full `properties` dict with names, types, and select options |
| `2025-09-03` | **Omits `properties`** — returns only metadata (id, title, parent, url, data_sources) |

Using `2025-09-03` for schema inspection silently returns a valid response with no property information — you cannot validate payload keys against it.

## Real-World Example: Entry → Name Drift

The `hermes-journal` skill's `notion-api-template.md` referenced `"Entry"` as the title property name for months (May–June 2026), while the actual database schema uses `"Name"`. The skill was patched on 2026-06-05 after discovery during a Morning Report run.

**Symptoms:** Pages were created successfully (HTTP 200), had `has_children: true`, and children blocks were present — but the title property was silently ignored because `"Entry"` didn't match any live property. The page appeared as "Untitled" in Notion.

**Detection:** Running the schema validation command above would have immediately shown `Name: title` — not `Entry: title`.

## After Validation: Construct Payload

Once you've confirmed the property names, use them exactly as returned:

```python
# CORRECT — property names match live schema
payload = {
    'parent': {'database_id': '376511b0-706b-8106-8710-c693d9d28014'},
    'properties': {
        'Name': {'title': [{'text': {'content': 'Your title here'}}]},       # ← confirmed via schema
        'Date': {'date': {'start': '2026-06-05'}},
        'Category': {'select': {'name': 'Infrastructure'}},
        'Impact': {'select': {'name': '🟡 Important'}}
    }
}
```

## Related Pitfalls

- **Stale database_id:** A different silent-failure mode — pages are created with correct properties but children blocks are silently dropped. Always verify children after creation with `GET /blocks/{page_id}/children`.
- **Integration not shared:** Writes silently 404 if the Notion integration isn't connected to the database. Verify in Notion UI before assuming API calls work.
