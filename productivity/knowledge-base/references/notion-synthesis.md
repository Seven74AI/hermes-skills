# KB Synthesis → Notion (Lieutner Journal)

When the user asks to synthesize KB content into a Notion page in their Lieutner Journal.

## Workflow

1. **Search KB** — `search_files(target='content', pattern='...', path='$OBSIDIAN_VAULT_PATH/Knowledge base/')`
2. **Read ALL relevant notes** — do not start writing after 2-3 notes. The user will say "lit tout pour être sûr de rien rater."
3. **Synthesize** — organize by topic, tag each claim with confidence level (✅ ⚠️ 🔬 ❌)
4. **Create Notion page** — use curl, not ntn (ntn not in PATH). Reliable flow: `POST /v1/pages` with markdown body.

## Lieutner Journal

- Data source ID: `521a8761-6839-4db2-81a2-42e92368b79a`
- Database ID: `8846a96e-4457-4861-a637-66eafee25b9c`
- Properties: `Name` (title), `Source`, `URL`, `Date`

## Creating a page

```bash
NOTION_KEY=$(grep NOTION_API_KEY /root/.hermes/.env | cut -d= -f2)
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $NOTION_KEY" \
  -H "Notion-Version: 2025-09-03" \
  -H "Content-Type: application/json" \
  -d '{
    "parent": {"database_id": "8846a96e-4457-4861-a637-66eafee25b9c"},
    "properties": {
      "Name": {"title": [{"text": {"content": "Title here"}}]},
      "Source": {"rich_text": [{"text": {"content": "Knowledge Base"}}]}
    },
    "markdown": "# Title\n\nContent..."
  }'
```

For large markdown bodies, use Python `subprocess.run()` with `-d @file.json` to avoid shell escaping issues.

## Include source URLs

For every claim/solution, include the original source URL in the Notion page. The user wants to see where each piece of information came from. Extract `source_url` from each note's frontmatter via `yaml.safe_load()`.
