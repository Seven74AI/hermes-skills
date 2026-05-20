#!/usr/bin/env python3
"""
Twitter digest processor with reply threading (v2.3.0).

Load JSON pages, filter RTs/empty tweets, tag with Theme/Signal/Source,
detect replies and include parent context with name/avatar/metrics,
output JSON and Discord/Notion formats.

Usage: python3 process_digest.py --list-name "Crypto" [--pages 5]
  Expects /tmp/list-page{1..N}.json from xurl fetches.
  Outputs /tmp/YYYY-MM-DD-{list-slug}-final.json, -discord.md, -notion.md
"""
import json, re, html, sys, os, subprocess, argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# === LIST CONFIGURATIONS ===
LIST_CONFIGS = {
    "crypto": {
        "themes": {
            "Bitcoin": ["bitcoin", "btc", "satoshi", "lightning", "bip-", "nakamoto", "21m", "halving"],
            "Trading": ["chart", "price", "bull", "bear", "support", "resistance", "breakout", "dump",
                        "pump", "volatility", "market cap", "trend", "trade", "position", "long", "short"],
            "DeFi": ["defi", "dex", "swap", "liquidity", "yield", "lending", "borrow", "amm", "staking"],
            "Regulation": ["sec", "cftc", "regulation", "regulatory", "law", "legal", "lawsuit", "court",
                           "congress", "bill", "legislation", "ban", "government", "policy", "trump"],
            "Macro": ["fed", "federal reserve", "inflation", "cpi", "interest rate", "gdp", "recession",
                      "economy", "dollar", "treasury", "gold", "sp500", "nasdaq", "dow", "war", "iran"],
            "Privacy": ["privacy", "anonymous", "mixer", "coinjoin", "wasabi", "samourai", "encryption"],
            "Security": ["hack", "exploit", "vulnerability", "audit", "bug", "patch", "wallet",
                         "custody", "multisig", "private key", "phishing", "scam"],
            "Mining": ["mining", "miner", "hashrate", "difficulty", "asic", "pool", "block reward", "pow"],
            "Stablecoins": ["usdt", "usdc", "dai", "stablecoin", "tether", "circle", "usdy", "usde"],
            "NFT/Gaming": ["nft", "gamefi", "gaming", "p2e", "metaverse", "virtual"],
        },
        "default_theme": "Trading",
    },
    "dev-ai": {
        "themes": {
            "Agent UX": ["agent", "ui", "ux", "interface", "cli", "tui", "chat", "widget", "terminal", "tool use"],
            "Codex": ["codex", "openai codex", "chatgpt code"],
            "Claude Code": ["claude code", "claude agent", "anthropic code", "claude dev"],
            "TypeScript": ["typescript", "ts", "typed", "type safety", "tsconfig"],
            "OSS": ["open source", "oss", "foss", "github", "repo", "mit license", "apache"],
            "Security": ["security", "vulnerability", "cve", "exploit", "hack", "bug bounty", "pentest"],
            "DevTools": ["vscode", "cursor", "copilot", "linter", "debugger", "ide", "editor",
                         "tooling", "devops", "ci/cd", "docker", "kubernetes"],
            "AI Engineering": ["ai", "llm", "gpt", "model", "prompt", "fine-tune", "rag", "embedding",
                              "inference", "transformer", "openai", "anthropic"],
            "Testing": ["test", "vitest", "jest", "playwright", "pytest", "assertion"],
        },
        "default_theme": "AI Engineering",
    },
}

# Signal detection patterns (case-insensitive, matched against text.lower())
ANNOUNCE_PATTERNS = [
    r'\b(announce|launch|released?|live now|new feature|new protocol|update)\b',
    r'\b(breaking|just in|alert|exclusive|official)\b',
    r'\b(listed on|now trading|exchange listing)',
    r'\b(partnership|integration|mainnet|testnet|beta)\b',
    r'\b(airdrop|token sale|ido|ieo)\b',
    r'\b(hiring|funding|raised|series)\b',
    r'\b(upgrade|fork|hard fork|soft fork)\b',
]

OPINION_PATTERNS = [
    r'\b(i think|i believe|in my opinion|my take|hot take)\b',
    r'\b(overrated|underrated|overvalued|undervalued)\b',
    r'\b(bullish|bearish|optimistic|skeptical|concerned)\b',
    r'\b(predict|forecast|expect|will (go|reach|hit|crash|pump|dump))\b',
    r'\b(analysis|breakdown|deep dive|thread|🧵)',
    r'\b(the case for|the case against|why .+ (will|is))',
    r'\b(chart shows|data shows|on-chain|metrics|indicator)',
]

QUESTION_PATTERNS = [
    r'\?$', r'\b(question|anyone|does anyone|what do you|thoughts\?)',
    r'\b(help|how (to|do|can)|why (is|does)|when (will|is))\b'
]

REPLY_PATTERNS = [
    r'\b(agree|disagree|wrong|right|nope|yes|exactly|indeed)\b',
]

# === GLOBAL VARS (set after arg parsing) ===
THEME_KEYWORDS = {}
DEFAULT_THEME = ""
LIST_NAME = "Crypto"
PAGE_COUNT = 5
DISCORD_CHAR_BUDGET = 1970
MIN_ENGAGEMENT_FULL = 5
MIN_ENGAGEMENT_DISCORD = 10
TOP_N_FULL = 75
MAX_TEXT_DISCORD = 95
CUTOFF_DAYS = 1            # date filter: today + N days back (1 = today+yesterday)
REPLY_MIN = 10             # min reply slots in output
REPLY_MAX = 30             # max reply slots in output
REPLY_RATIO = 0.25         # target ratio of output slots for replies

# === HELPER FUNCTIONS ===

def extract_media(t):
    """Extract image/video URLs from tweet entities."""
    media = []
    for url in t.get("entities", {}).get("urls", []):
        if url.get("media_key") or "pic.x.com" in url.get("display_url", ""):
            media_type = "video" if "video" in url.get("display_url", "") else "image"
            media.append({"url": url["expanded_url"], "type": media_type})
    return media

def load_pages():
    """Load all page JSON files, merge users, tweets, and build tweet_map."""
    all_tweets, all_users, seen_ids = [], {}, set()
    tweet_map = {}  # tweet_id -> full tweet object (from data[] and includes.tweets[])
    for i in range(1, PAGE_COUNT + 1):
        path = f"/tmp/list-page{i}.json"
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        for u in data.get("includes", {}).get("users", []):
            if u["id"] not in all_users:
                all_users[u["id"]] = u
        for t in data.get("data", []):
            if t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                all_tweets.append(t)
                tweet_map[t["id"]] = t
        # Load includes.tweets (referenced/parent tweets that may be outside main data)
        for t in data.get("includes", {}).get("tweets", []):
            if t["id"] not in tweet_map:
                tweet_map[t["id"]] = t
    return all_tweets, all_users, tweet_map

def is_substantial(text):
    """At least 4 real words after stripping URLs, mentions, hashtags."""
    stripped = re.sub(r'https?://\S+', '', text)
    stripped = re.sub(r'@\w+', '', stripped)
    stripped = re.sub(r'#(\w+)', r'\1', stripped)
    words = [w for w in re.sub(r'[^\w\s]', '', stripped).split() if len(w) > 1]
    return len(words) >= 4

def tag_tweet(text):
    """Return (themes, signal, source)."""
    text_l = text.lower()
    has_url = bool(re.search(r'https?://\S+', text))

    # Themes
    themes = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in text_l for kw in keywords):
            themes.append(theme)
    if not themes:
        themes = [DEFAULT_THEME]

    # Signal
    is_announce = any(re.search(p, text_l) for p in ANNOUNCE_PATTERNS)
    is_opinion = any(re.search(p, text_l) for p in OPINION_PATTERNS)
    is_question = any(re.search(p, text_l) for p in QUESTION_PATTERNS)
    is_reply_sig = any(re.search(p, text_l) for p in REPLY_PATTERNS)

    if is_announce and not is_opinion:
        signal = "🔴 Signal"
    elif is_opinion:
        signal = "🟡 Insight"
    elif is_question or is_reply_sig or len(text.split()) < 10:
        signal = "🟢 Discussion"
    elif has_url and len(re.sub(r'https?://\S+', '', text).strip().split()) < 6:
        signal = "⚪ Link/Ref"
    else:
        signal = "🟡 Insight"

    # Source
    if is_announce:
        source = "Builder"
    elif is_opinion:
        source = "Analyst"
    elif is_question or is_reply_sig:
        source = "Community"
    elif has_url:
        source = "Curator"
    else:
        source = "Analyst"

    return themes, signal, source

def engagement(t):
    return t.get("likes", 0) + t.get("retweets", 0) * 2

def clean_text(text):
    t = html.unescape(text)
    return re.sub(r'\s+', ' ', t).strip()

def build_tweet_card(tweet_data, user, tweet_id):
    """Build a complete tweet card dict from raw API data."""
    metrics = tweet_data.get("public_metrics", {})
    card = {
        "username": user.get("username", "unknown"),
        "name": user.get("name", "unknown"),
        "avatar": user.get("profile_image_url", ""),
        "text": tweet_data["text"],
        "media": extract_media(tweet_data),
        "likes": metrics.get("like_count", 0),
        "retweets": metrics.get("retweet_count", 0),
        "replies": metrics.get("reply_count", 0),
        "quotes": metrics.get("quote_count", 0),
        "tweet_url": f"https://x.com/{user.get('username', 'unknown')}/status/{tweet_id}",
        "id": tweet_id,
        "created_at": tweet_data.get("created_at", ""),
    }
    return card

def fetch_parent_via_xurl(parent_id):
    """Try to fetch parent tweet via xurl read. Returns dict or None."""
    try:
        result = subprocess.run(
            ["xurl", "read", parent_id],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return None
        tweet = json.loads(result.stdout)
        if not tweet or "text" not in tweet:
            return None
        return tweet
    except Exception:
        return None

def build_reply_pairs(tagged_tweets, tweet_map, all_users):
    """
    Detect replies and build reply pairs with parent context.

    Returns list of dicts: all items are in canonical format:
      - Regular tweets:  {is_reply: False, tweet: {...}}
      - Reply pairs:     {is_reply: True, parent: {...}, reply: {...}}

    Parent resolution:
      1. tweet_map (data[] + includes.tweets[]) — >99% case
      2. xurl read fallback — parent outside fetch window
      3. Degraded fallback — [parent tweet unavailable] with in_reply_to user context

    Note: parent sub-objects are intentionally WITHOUT themes/signal/source —
    they are contextual, not classified. Only the reply tweet gets tagged.
    Parent objects include full engagement metrics (likes/retweets/replies/quotes).
    """
    output = []

    for t in tagged_tweets:
        raw_tweet = tweet_map.get(t["id"])
        if not raw_tweet:
            output.append({"is_reply": False, "tweet": t})
            continue

        # Detect if this is a reply via referenced_tweets
        refs = raw_tweet.get("referenced_tweets", [])
        parent_id = None
        for r in refs:
            if r.get("type") == "replied_to":
                parent_id = r.get("id")
                break

        if not parent_id:
            output.append({"is_reply": False, "tweet": t})
            continue

        # This is a reply — build parent context
        parent_raw = tweet_map.get(parent_id)

        if parent_raw:
            # Tier 1: Parent found in tweet_map (data[] or includes.tweets[])
            parent_user = all_users.get(parent_raw.get("author_id", ""), {})
            pmetrics = parent_raw.get("public_metrics", {})
            parent = {
                "username": parent_user.get("username", "unknown"),
                "name": parent_user.get("name", "unknown"),
                "avatar": parent_user.get("profile_image_url", ""),
                "text": parent_raw.get("text", ""),
                "tweet_url": f"https://x.com/{parent_user.get('username', 'unknown')}/status/{parent_id}",
                "media": extract_media(parent_raw),
                "likes": pmetrics.get("like_count", 0),
                "retweets": pmetrics.get("retweet_count", 0),
                "replies": pmetrics.get("reply_count", 0),
                "quotes": pmetrics.get("quote_count", 0),
            }
            output.append({
                "is_reply": True,
                "parent": parent,
                "reply": t,
            })
        else:
            # Tier 2: Parent NOT in tweet_map — try xurl read fallback
            parent_via_xurl = fetch_parent_via_xurl(parent_id)

            if parent_via_xurl:
                parent_user_data = parent_via_xurl.get("author", {}) or {}
                pmetrics = parent_via_xurl.get("public_metrics", {})
                parent = {
                    "username": parent_user_data.get("username",
                                all_users.get(parent_via_xurl.get("author_id", ""), {}).get("username", "unknown")),
                    "name": parent_user_data.get("name",
                            all_users.get(parent_via_xurl.get("author_id", ""), {}).get("name", "unknown")),
                    "avatar": parent_user_data.get("profile_image_url",
                               all_users.get(parent_via_xurl.get("author_id", ""), {}).get("profile_image_url", "")),
                    "text": parent_via_xurl.get("text", ""),
                    "tweet_url": f"https://x.com/{parent_user_data.get('username', 'unknown')}/status/{parent_id}",
                    "media": extract_media(parent_via_xurl),
                    "likes": pmetrics.get("like_count", parent_via_xurl.get("likes", 0)),
                    "retweets": pmetrics.get("retweet_count", parent_via_xurl.get("retweets", 0)),
                    "replies": pmetrics.get("reply_count", parent_via_xurl.get("replies", 0)),
                    "quotes": pmetrics.get("quote_count", parent_via_xurl.get("quotes", 0)),
                }
                output.append({
                    "is_reply": True,
                    "parent": parent,
                    "reply": t,
                })
            else:
                # Tier 3: Degraded fallback — include in_reply_to username from raw data
                reply_to_user_id = raw_tweet.get("in_reply_to_user_id")
                reply_to_user = all_users.get(reply_to_user_id, {}) if reply_to_user_id else {}
                replying_to = reply_to_user.get("username", "unknown")

                parent = {
                    "username": replying_to,
                    "name": reply_to_user.get("name", replying_to),
                    "avatar": reply_to_user.get("profile_image_url", ""),
                    "text": "[parent tweet unavailable]",
                    "tweet_url": f"https://x.com/{replying_to}/status/{parent_id}",
                    "media": [],
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0,
                    "quotes": 0,
                }
                output.append({
                    "is_reply": True,
                    "parent": parent,
                    "reply": t,
                })

    return output

def get_signal_for_grouping(t):
    """Get signal string for grouping (works for canonical format)."""
    if t.get("is_reply"):
        return t.get("reply", {}).get("signal", "🟢 Discussion")
    return t.get("tweet", {}).get("signal", "🟡 Insight")

def build_discord(top_tweets):
    """Build Discord message under 2000 chars."""
    signal_order = ["🔴 Signal", "🟡 Insight", "🟢 Discussion", "⚪ Link/Ref"]
    sig_labels = {"🔴 Signal": "🔴 SIGNAL", "🟡 Insight": "🟡 INSIGHT",
                  "🟢 Discussion": "🟢 DISCUSSION", "⚪ Link/Ref": "⚪ LINKS"}
    grouped = defaultdict(list)
    for t in top_tweets:
        sig = get_signal_for_grouping(t)
        grouped[sig].append(t)

    today = datetime.now(timezone.utc)
    display_date = today.strftime("%B %d, %Y")
    header = f"🗞️ **{LIST_NAME} Digest — {display_date}**\n{'━'*30}"
    lines, char_count = [header], len(header) + 1
    selected = []

    for sig in signal_order:
        grp = grouped.get(sig, [])
        section = f"\n{sig_labels[sig]}"
        lines.append(section); char_count += len(section) + 1
        for t in grp:
            # For reply pairs, show reply's text/signal but parent context on separate line
            if t.get("is_reply"):
                item = t["reply"]
                parent = t["parent"]
                reply_parent_line = f"↳ @{parent['username']}: {clean_text(parent['text'])[:80]}…"
                if char_count + len(reply_parent_line) + 1 <= DISCORD_CHAR_BUDGET:
                    lines.append(reply_parent_line); char_count += len(reply_parent_line) + 1
                reply_line_prefix = "  ↪ "
            else:
                item = t["tweet"]
                reply_line_prefix = ""

            text = clean_text(item["text"])
            if len(text) > MAX_TEXT_DISCORD:
                text = text[:MAX_TEXT_DISCORD].rsplit(" ", 1)[0] + "…"
            theme_str = " | ".join(item["themes"][:2])
            line = f"{reply_line_prefix}**@{item['username']}** {text} — {theme_str} | ❤{item['likes']}|🔄{item['retweets']}"
            if char_count + len(line) + 1 > DISCORD_CHAR_BUDGET:
                break
            lines.append(line); char_count += len(line) + 1
            selected.append(t)

    footer = f"\n{'━'*30}\n📊 {len(selected)} tweets | [Web](https://seven74ai.github.io/twitter-digest/)"
    lines.append(footer)
    return "\n".join(lines), selected

def build_notion(top_tweets):
    """Build Notion markdown body."""
    signal_order = ["🔴 Signal", "🟡 Insight", "🟢 Discussion", "⚪ Link/Ref"]
    sig_labels = {"🔴 Signal": "🔴 SIGNAL", "🟡 Insight": "🟡 INSIGHT",
                  "🟢 Discussion": "🟢 DISCUSSION", "⚪ Link/Ref": "⚪ LINKS"}
    grouped = defaultdict(list)
    for t in top_tweets:
        sig = get_signal_for_grouping(t)
        grouped[sig].append(t)

    display_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines = [f"# {LIST_NAME} Digest — {display_date}", ""]
    for sig in signal_order:
        grp = grouped.get(sig, [])
        if not grp:
            continue
        lines.append(f"## {sig_labels[sig]}"); lines.append("")
        for i, t in enumerate(grp, 1):
            if t.get("is_reply"):
                item = t["reply"]
                parent = t["parent"]
                text = clean_text(item["text"])
                theme_str = " | ".join(item["themes"][:3])
                lines.append(f"### {i}. ↪ Reply to @{parent['username']}")
                lines.append(f"> ↳ @{parent['username']}: {clean_text(parent['text'])[:200]}")
                lines.append(f"> ↪ @{item['username']}: {text}")
                lines.append(f"Themes: {theme_str} | {item['signal']} | {item['source']}")
                lines.append(f"[View]({item['tweet_url']})"); lines.append("")
            else:
                text = clean_text(t["text"])
                eng = f"❤{t['likes']} 🔄{t['retweets']} 💬{t.get('replies', 0)}"
                theme_str = " | ".join(t["themes"][:3])
                lines.append(f"### {i}. @{t['username']} — {eng}")
                lines.append(f"> {text}")
                lines.append(f"Themes: {theme_str} | {t['signal']} | {t['source']}")
                lines.append(f"[View]({t['tweet_url']})"); lines.append("")
    return "\n".join(lines)

# === MAIN ===
def main():
    global THEME_KEYWORDS, DEFAULT_THEME, LIST_NAME, PAGE_COUNT

    parser = argparse.ArgumentParser(description="Twitter Digest Processor")
    parser.add_argument("--list-name", default="Crypto",
                        help="List name: 'Crypto' or 'Dev/AI' (default: Crypto)")
    parser.add_argument("--pages", type=int, default=5,
                        help="Number of pages to load (default: 5)")
    args = parser.parse_args()

    LIST_NAME = args.list_name
    PAGE_COUNT = args.pages

    # Select config
    slug = LIST_NAME.lower().replace(" ", "-").replace("/", "-")
    list_key = slug  # "crypto" or "dev-ai"
    config = LIST_CONFIGS.get(list_key)
    if not config:
        print(f"Unknown list: {LIST_NAME}. Available: {list(LIST_CONFIGS.keys())}")
        sys.exit(1)

    THEME_KEYWORDS = config["themes"]
    DEFAULT_THEME = config["default_theme"]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_tweets, all_users, tweet_map = load_pages()

    # Filter RTs
    non_rt = [t for t in all_tweets if not t.get("text", "").startswith("RT @")]

    # Filter substance
    filtered = [t for t in non_rt if is_substantial(t.get("text", ""))]

    # Deduplicate by normalized text
    seen = set()
    deduped = []
    for t in filtered:
        nt = re.sub(r'https?://\S+', '', t["text"]).strip().lower()
        nt = re.sub(r'\s+', ' ', nt)
        if nt and nt not in seen:
            seen.add(nt)
            deduped.append(t)

    # Step 1: Tag all tweets (build tweet cards with themes/signal/source)
    tagged = []
    for t in deduped:
        uid = t["author_id"]
        user = all_users.get(uid, {})
        themes, signal, source = tag_tweet(t["text"])
        card = build_tweet_card(t, user, t["id"])
        card["themes"] = themes
        card["signal"] = signal
        card["source"] = source
        tagged.append(card)

    # Step 2: Build reply pairs (detect replies, resolve parents, produce unified output)
    final_tweets = build_reply_pairs(tagged, tweet_map, all_users)

    # Sort by engagement (use reply's engagement for reply pairs)
    def sort_key(t):
        item = t.get("reply", t)
        return engagement(item)
    final_tweets.sort(key=sort_key, reverse=True)

    # Filter for full set (web/notion) with engagement floor
    full_set = [t for t in final_tweets if engagement(t.get("reply", t)) >= MIN_ENGAGEMENT_FULL][:TOP_N_FULL]

    # Split regular vs reply for slot management
    regular_in_full = [t for t in full_set if not t.get("is_reply")]
    replies_in_full = [t for t in full_set if t.get("is_reply")]

    # Reserve at least 25% of slots for replies (floor 10, max 30)
    reply_reserved = max(10, min(TOP_N_FULL // 4, 30))
    regular_slots = TOP_N_FULL - reply_reserved

    full_set = regular_in_full[:regular_slots] + replies_in_full[:reply_reserved]
    full_set.sort(key=sort_key, reverse=True)

    # Count stats AFTER reply pairs are built
    replies_total = sum(1 for t in full_set if t.get("is_reply"))
    replies_null_parent = sum(
        1 for t in full_set
        if t.get("is_reply") and t.get("parent", {}).get("text") == "[parent tweet unavailable]"
    )

    # Discord highlight set (higher engagement floor)
    discord_set = [t for t in final_tweets if engagement(t.get("reply", t)) >= MIN_ENGAGEMENT_DISCORD]

    # Build and save
    discord_msg, discord_tweets = build_discord(discord_set)
    notion_md = build_notion(full_set)

    with open(f"/tmp/{today}-{slug}-discord.md", "w") as f:
        f.write(discord_msg)
    with open(f"/tmp/{today}-{slug}-notion.md", "w") as f:
        f.write(notion_md)

    # Count signal distribution
    signal_counts = {"🔴 Signal": 0, "🟡 Insight": 0, "🟢 Discussion": 0, "⚪ Link/Ref": 0}
    for t in full_set:
        sig = get_signal_for_grouping(t)
        if sig in signal_counts:
            signal_counts[sig] += 1

    digest = {
        "date": today,
        "list": LIST_NAME,
        "tweets": full_set,
        "stats": {
            "total_fetched": len(all_tweets),
            "after_filter": len(tagged),
            "final_count": len(full_set),
            "regular_count": len(regular_in_full[:regular_slots]),
            "reply_count": len(replies_in_full[:reply_reserved]),
            "replies_total": replies_total,
            "replies_null_parent": replies_null_parent,
            "discord_count": len(discord_tweets),
            "signals": signal_counts,
        }
    }
    outpath = f"/tmp/{today}-{slug}-final.json"
    with open(outpath, "w") as f:
        json.dump(digest, f, indent=2, ensure_ascii=False)

    print(f"List: {LIST_NAME}")
    print(f"Fetched: {len(all_tweets)}, Tagged: {len(tagged)}")
    print(f"Full: {len(full_set)} ({len(regular_in_full[:regular_slots])} regular + {len(replies_in_full[:reply_reserved])} replies)")
    print(f"Replies total: {replies_total}, Null parents (degraded): {replies_null_parent}")
    print(f"Discord chars: {len(discord_msg)}")
    print(f"Output: {outpath}")

if __name__ == "__main__":
    main()
