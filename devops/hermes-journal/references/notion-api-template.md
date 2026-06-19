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
    "Name": {"title": [{"text": {"content": "TITLE HERE"}}]},
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

Two approaches — use the right one for the complexity of your payload.

### Simple: inline `python3 -c` (flat data, no apostrophes)

When your content is simple (short title, no apostrophes, no quotes inside strings), inline `-c` works:

```python
python3 -c "
import json
data = {
    'parent': {'database_id': '376511b0-706b-8106-8710-c693d9d28014'},
    'properties': {
        'Name': {'title': [{'text': {'content': 'Short simple title'}}]},
        'Date': {'date': {'start': '2026-05-22'}},
        'Category': {'select': {'name': 'Infrastructure'}},
        'Impact': {'select': {'name': 'Important'}}
    },
    'children': [
        {'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': [{'type': 'text', 'text': {'content': 'Simple content.'}}]}}
    ]
}
with open('/tmp/notion_entry.json', 'w') as f:
    json.dump(data, f)
print('written OK')
"
```

⚠️ **Pitfall:** Content containing apostrophes (`'s`, `don't`, etc.) will break single-quoted Python strings inside `-c`. The shell has no way to escape a single quote inside single quotes. Use the standalone script approach below for any payload with unpredictable content.

### Complex: standalone `.py` script (multi-entry, apostrophes, long prose)

For journal entries with rich prose, multiple entries, or content containing apostrophes, write a standalone Python script with `cat > /tmp/script.py << 'PYEOF'`, then run it:

```bash
cat > /tmp/write_entries.py << 'PYEOF'
import json, subprocess, os

NOTION_KEY = os.environ.get("NOTION_API_KEY", "")
DB_ID = "376511b0-706b-8106-8710-c693d9d28014"

entries = [
    {
        "title": "Entry title with apostrophes like board's database",
        "date": "2026-06-18",
        "category": "Debugging",
        "impact": "Critical",
        "children": [
            {"type": "paragraph", "content": "Content with apostrophes like can't and don't is safe here."},
            {"type": "paragraph", "content": "Second paragraph."}
        ]
    }
]

for i, entry in enumerate(entries):
    children_blocks = []
    for child in entry["children"]:
        children_blocks.append({
            "object": "block",
            "type": child["type"],
            child["type"]: {
                "rich_text": [{"type": "text", "text": {"content": child["content"]}}]
            }
        })

    payload = {
        "parent": {"database_id": DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": entry["title"]}}]},
            "Date": {"date": {"start": entry["date"]}},
            "Category": {"select": {"name": entry["category"]}},
            "Impact": {"select": {"name": entry["impact"]}}
        },
        "children": children_blocks
    }

    payload_file = f"/tmp/notion_e{i+1}.json"
    with open(payload_file, "w") as f:
        json.dump(payload, f)

    subprocess.run([
        "curl", "-s", "-X", "POST", "https://api.notion.com/v1/pages",
        "-H", f"Authorization: Bearer {NOTION_KEY}",
        "-H", "Notion-Version: 2022-06-28",
        "-H", "Content-Type: application/json",
        "-d", f"@{payload_file}",
        "-o", f"/tmp/notion_resp{i+1}.json"
    ])

    with open(f"/tmp/notion_resp{i+1}.json") as f:
        resp = json.load(f)

    if "id" in resp:
        page_id = resp["id"]
        print(f"Entry {i+1} OK: {page_id}")
        # Verify children
        vrf = subprocess.run([
            "curl", "-s", f"https://api.notion.com/v1/blocks/{page_id}/children",
            "-H", f"Authorization: Bearer {NOTION_KEY}",
            "-H", "Notion-Version: 2025-09-03"
        ], capture_output=True, text=True)
        children = json.loads(vrf.stdout)
        n_blocks = len(children.get("results", []))
        print(f"  Children: {n_blocks} blocks {'OK' if n_blocks > 0 else 'MISSING!'}")
    else:
        print(f"Entry {i+1} ERROR: {resp.get('message')}")

print("Done.")
PYEOF
source ~/.hermes/.env && python3 /tmp/write_entries.py
```

**Advantages of the standalone script:**
- Double-quoted Python strings (`"content"`) handle apostrophes naturally — no escaping headaches
- Batch multiple entries in one script with consistent validation
- `subprocess.run()` avoids the pipe-to-interpreter scanner block
- Children verification is built in — no separate post-check needed

## Valid Select Values

**Category:** Infrastructure, Tooling, Lesson Learned, Configuration, Debugging

**Impact (emoji):** 🔴 Critical, 🟡 Important, 🟢 Nice to Know

**Impact (plain text — scanner-safe fallback):** Critical, Important, Nice to Know, [CRITICAL], [IMPORTANT]

The DB schema actually contains both emoji and non-emoji variants as valid select options (verified 2026-06-16 via `GET /databases/{id}`). When the security scanner blocks emoji inside `python3 -c` strings (`tirith:variation_selector`), use the plain text fallbacks: `Critical`, `Important`, or `Nice to Know`. These produce the same visual result since Notion renders select values from the stored option name.

## Notes

- **Always validate property names before constructing payloads.** Fetch the live schema with `GET /databases/{id}` + `Notion-Version: 2022-06-28` and confirm every property key in your payload exists. Notion silently ignores unrecognized keys — no error, no warning. See `references/notion-schema-validation.md`.
- Each entry should have 1-3 paragraph blocks in `children` — keep it under 500 words total
- The `Name` title property is a **title** type — use `{"title": [{"text": {"content": "..."}}]}` not `{"rich_text": [...]}`
- Date property uses ISO format: `{"date": {"start": "YYYY-MM-DD"}}`
