# Notion API — Page Creation Template

Exact curl + JSON payload for creating a journal entry in the Hermes Ops Journal database.

## Database IDs

Two IDs refer to the same Notion database — use the right one for the right operation:

- **database_id** (page creation, v2022-06-28): `376511b0-706b-8106-8710-c693d9d28014`
- **data_source_id** (queries, v2025-09-03): `376511b0-706b-8177-8a2e-000bda604705`

⚠️ Historical stale IDs: `365511b0-706b-8146-81bb-d2ecaac5682d`, `365511b0-706b-81d5-be62-000b4f377403`, `365511b0-706b-8160-887c-fba30df98145` — all broken. Recreated under Hermes Sevenai root page 2026-06-05.

## API Version

Use `Notion-Version: 2022-06-28` for page creation (select/date properties break with `2025-09-03`).

## Minimal JSON Payload

```json
{
  "parent": {"database_id": "376511b0-706b-8106-8710-c693d9d28014"},
  "properties": {
    "Entry": {"title": [{"text": {"content": "TITLE HERE"}}]},
    "Date": {"date": {"start": "2026-05-22"}},
    "Category": {"select": {"name": "Infrastructure"}},
    "Impact": {"select": {"name": "🔴 Critical"}}
  },
  "children": [
    {
      "object": "block",
      "type": "paragraph",
      "paragraph": {
        "rich_text": [{"type": "text", "text": {"content": "Paragraph text here."}}]
      }
    }
  ]
}
```

## Curl Command

```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer ${NOTION_API_KEY}" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d @/tmp/notion_entry.json -o /tmp/notion_resp.json
```

## Checking the Response

The `-o` flag writes the HTTP response to a file — do NOT pipe `curl | python3` (Hermes security scanner blocks it).

```bash
python3 -c "
import json
with open('/tmp/notion_resp.json') as f:
    d = json.load(f)
if 'id' in d:
    print('OK:', d['id'][:8])
else:
    print('ERROR:', d.get('message',''), d.get('code',''))
"
```

## Writing JSON from Python

When creating entries programmatically, write JSON with `python3` directly to avoid heredoc issues:

```python
python3 -c "
import json
data = {
    'parent': {'database_id': '376511b0-706b-8106-8710-c693d9d28014'},
    'properties': {
        'Entry': {'title': [{'text': {'content': 'Your title here'}}]},
        'Date': {'date': {'start': '2026-05-22'}},
        'Category': {'select': {'name': 'Infrastructure'}},
        'Impact': {'select': {'name': '🟡 Important'}}
    },
    'children': [
        {'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': [{'type': 'text', 'text': {'content': 'Your content here.'}}]}}
    ]
}
with open('/tmp/notion_entry.json', 'w') as f:
    json.dump(data, f)
print('written OK')
"
```

## Valid Select Values

**Category:** Infrastructure, Tooling, Lesson Learned, Configuration, Debugging

**Impact:** 🔴 Critical, 🟡 Important, 🟢 Nice to Know

## Notes

- Each entry should have 1-3 paragraph blocks in `children` — keep it under 500 words total
- The `Entry` title property is a **title** type — use `{"title": [{"text": {"content": "..."}}]}` not `{"rich_text": [...]}`
- Date property uses ISO format: `{"date": {"start": "YYYY-MM-DD"}}`
