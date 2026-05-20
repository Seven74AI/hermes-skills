# GitHub Pages — Twitter-style Timeline

The digest site is a single `index.html` with embedded CSS/JS, hosted on GitHub Pages.

## Design

- Dark theme (#000 background, #e7e9ea text) — Twitter/X style
- Tweet cards with avatar, name, handle, text, badges, engagement metrics
- Tabs at top: All / Dev/AI / Crypto
- Filter buttons: All / 🔴 Signal / 🟡 Insight / 🟢 Discussion / ⚪ Link/Ref
- Responsive, max-width 600px, mobile-friendly

## Key JS Functions

### renderTweet(t)
Renders a single tweet card with avatar, text, media grid, badges, and engagement.

### renderTweetPair(t)
Renders a reply thread: parent tweet in a muted `.parent-tweet` box, reply indented with left border.

### renderMedia(media)
Renders media array:
- `type: "image"` → `<img>` with `.tweet-media` class (max 300px, rounded 12px)
- `type: "video"` → "▶️ Watch video" link
- Other → generic "📎 Media" link

### loadDigests()
Fetches `data/index.json`, then loads each digest file, sorts by date descending, calls `render()`.

## Data Format

`data/index.json` — array of filenames:
```json
["2026-05-18-dev-ai.json", "2026-05-18-crypto.json", "2026-05-17-dev-ai.json"]
```

Each digest JSON:
```json
{
  "date": "2026-05-18",
  "list": "Dev/AI",
  "tweets": [
    {"text": "...", "username": "...", "name": "...", "avatar": "...",
     "media": [{"url": "...", "type": "image"}],
     "themes": ["Agent UX"], "signal": "🟡 Insight", "source": "Analyst",
     "likes": 5, "retweets": 2, "tweet_url": "..."}
  ]
}
```

## CSS Classes

| Class | Purpose |
|-------|---------|
| `.tweet` | Card container (flex, gap 10px, bottom border) |
| `.parent-tweet` | Muted background (#0a0a0a), rounded 8px |
| `.thread` | Flex column for reply threads |
| `.media-grid` | Flex wrap, 4px gap |
| `.tweet-media` | Max 100% width, max 300px height, rounded 12px, 1px border |
| `.badge-signal` | Blue tint (#1d9bf01a) |
| `.badge-theme` | Green tint (#00ba7c1a) |
| `.badge-source` | Pink tint (#f918801a) |
| `.day-header` | Blue (#1d9bf0), 18px bold |
| `.signal-sig` | Red (#f91880) text for 🔴 Signal |
| `.signal-insight` | Orange (#f5a623) text for 🟡 Insight |
| `.signal-disc` | Green (#00ba7c) text for 🟢 Discussion |
| `.signal-link` | Gray (#71767b) text for ⚪ Link/Ref |
