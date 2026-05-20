# Discord Digest Message Builder — Working Pattern

This is the working Python pattern for building Discord digest messages that fit within the 2000-character limit. It was refined across multiple iterations due to quote-escaping bugs and char-counting edge cases.

## Key Decisions

1. **Unicode quotes only**: Use `\u201c` / `\u201d` (curly quotes) and `\u2014` (em dash) instead of ASCII `"` and `-`. This avoids all Python f-string escaping issues.
2. **Clean text first**: Replace `\n` with space, replace `"` with `\u201c`, truncate to max length.
3. **Char-counting loop**: Build sections, test cumulative length against 1950, cut when nearing limit.
4. **Sort by engagement**: `likes + retweets * 2` descending within each signal group.
5. **Media on separate lines**: Use `📎` prefix, truncate URLs to 55 chars.

## Working Template

```python
#!/usr/bin/env python3
"""Build Discord digest from tweet JSON - fit within 2000 chars"""
import json

with open('/tmp/twitter-digest-data/data/DATE-TYPE.json') as f:
    data = json.load(f)

DATE = data['date']
tweets = data['tweets']

# Separate by signal
signal_tweets = []
insight = []
discussion = []
link_ref = []

for entry in tweets:
    if entry.get('is_reply'):
        discussion.append(entry)
    else:
        s = entry.get('signal', '')
        if 'Signal' in s:
            signal_tweets.append(entry)
        elif 'Insight' in s:
            insight.append(entry)
        elif 'Link' in s:
            link_ref.append(entry)
        else:
            insight.append(entry)

# Sort by engagement
insight.sort(key=lambda x: x.get('likes', 0) + x.get('retweets', 0) * 2, reverse=True)
signal_tweets.sort(key=lambda x: x.get('likes', 0) + x.get('retweets', 0) * 2, reverse=True)

def clean_text(t, max_len=110):
    """Clean text for Discord: replace newlines, convert quotes, truncate"""
    text = t.replace('\n', ' ').replace('"', '\u201c')
    if len(text) > max_len:
        text = text[:max_len-3] + '...'
    return text

def fmt_standalone(entry):
    """Format a standalone tweet line with engagement"""
    text = clean_text(entry.get('text', ''))
    themes = ', '.join(entry.get('themes', ['Unknown']))
    source = entry.get('source', 'Analyst')
    username = entry.get('username', '?')
    likes = entry.get('likes', 0)
    media = entry.get('media', [])
    lines = [f'\u201c{text}\u201d \u2014 @{username} | {themes} | {source} | \u2764{likes}']
    for m in media:
        url = m['url']
        if len(url) > 55:
            url = url[:52] + '...'
        lines.append(f'  \U0001f4ce {url}')
    return '\n'.join(lines)

def fmt_reply(entry):
    """Format a reply thread: parent then reply"""
    parent = entry.get('parent', {})
    reply = entry.get('reply', {})
    lines = []
    p_text = clean_text(parent.get('text', ''), 90)
    r_text = clean_text(reply.get('text', ''), 90)
    themes = ', '.join(reply.get('themes', ['Unknown']))
    source = reply.get('source', 'Community')
    lines.append(f'\u21b3 \u201c{p_text}\u201d \u2014 @{parent.get("username","?")}')
    lines.append(f'    \u21aa \u201c{r_text}\u201d \u2014 @{reply.get("username","?")} | {themes} | {source}')
    for m in reply.get('media', []):
        url = m['url']
        if len(url) > 55:
            url = url[:52] + '...'
        lines.append(f'    \U0001f4ce {url}')
    return '\n'.join(lines)

MAX_MSG = 1950

def build_message():
    header = f'\U0001f5de\ufe0f **Crypto Digest \u2014 {DATE}**'
    
    sections = []
    counts_per_section = [
        ('\U0001f534 **SIGNAL**', signal_tweets, 4),
        ('\U0001f7e1 **INSIGHT**', insight, 7),
        ('\U0001f7e2 **DISCUSSION**', discussion, 4),
        ('\u26aa **LINK/REF**', link_ref, 2),
    ]
    
    for label, grp, max_show in counts_per_section:
        if not grp:
            continue
        s = f'\n{label} ({len(grp)})'
        for t in grp[:max_show]:
            if grp == discussion or (isinstance(t, dict) and t.get('is_reply')):
                s += '\n' + fmt_reply(t)
            else:
                s += '\n' + fmt_standalone(t)
        sections.append(s)
    
    footer = f'\n\U0001f4ca {len(tweets)} tweets | https://seven74ai.github.io/twitter-digest/'
    
    msg = header
    for s in sections:
        test = msg + s + footer
        if len(test) <= MAX_MSG:
            msg += s
        else:
            available = MAX_MSG - len(msg) - len(footer) - 5
            if available > 30:
                msg += s[:available]
            break
    
    msg += footer
    return msg

message = build_message()
with open('/tmp/discord_digest.txt', 'w') as f:
    f.write(message)
```

## Discord Payload Wrapper

```python
#!/usr/bin/env python3
"""Output JSON payload for Discord API"""
import json
with open('/tmp/discord_digest.txt') as f:
    msg = f.read()
print(json.dumps({'content': msg}))
```

## Pitfalls Avoided

- **`f'"\\"{text}\\""'` trap**: Produces `"\"text\""` (literal backslashes). Fixed by using unicode escapes.
- **`python3 -c` blocked**: Hermes blocks inline Python. Always write `.py` files, never pipe.
- **Char overflow**: First builds were 7K-15K chars. The MAX_MSG=1950 loop with section-level truncation is essential.
- **Media URL length**: Full `pbs.twimg.com` URLs are ~120 chars each and consume budget fast. Truncate to 55 chars.
