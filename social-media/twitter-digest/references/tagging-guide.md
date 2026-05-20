# Tagging Guide — Keyword Matching + Manual Correction

The triple-tag system (Theme / Signal / Source) uses a two-pass approach:
1. **Automated pass**: keyword matching with weighted scoring
2. **Manual pass**: human review and correction (agent reads full texts, corrects ~50% of tags)

## Automated Keyword Matching

### Theme Keywords (Crypto list example)

| Theme | Keywords |
|-------|----------|
| Bitcoin | bitcoin, btc, #bitcoin, satoshi, lightning, halving, sbr, strategic bitcoin reserve, bitcoin etf, btc etf |
| Trading | chart, price, bull, bear, pump, dump, resistance, support, ema, trend, long, short, pullback, breakout, volatility, trade, altcoin, altcoins, alts, liquidat, position, entry, exit, target |
| DeFi | defi, hyperliquid, uniswap, aave, lending, yield, amm, dex, perp, perps, solana, eth, ethereum, l2, arbitrum, optimism, staking, bridge, token, airdrop, meme coin, memecoin, $ |
| Regulation | regulation, sec, cftc, compliance, law, legal, tax, ban, government, policy, congress, senate, bill, legislation, enforcement |
| Macro | macro, fed, inflation, economy, recession, gdp, interest rate, stock market, sp500, nasdaq, gold, dollar, dxy, treasury, geopolitic, tariff, trade war, central bank, fomc |
| Privacy | privacy, zcash, monero, xmr, coinjoin, mixer, encrypt, pgp, anonymous, surveillance, kyc, zerocoin |
| Security | hack, scam, exploit, vulnerability, ledger, wallet, key, seed, phish, rug, security, audit, bug |
| Mining | mining, miner, hash, hashrate, asic, pow, difficulty, energy, electricity |

### Theme Keywords (Dev/AI list example)

| Theme | Keywords |
|-------|----------|
| Agent UX | agent, agents, agentic, autonomous, orchestrate, delegate, multi-agent, subagent, agent sdk, agent protocol, mcp, tool use, function call, reasoning, planning, workflow |
| Codex | codex, openai codex, @openai/codex, openai sdk |
| Claude Code | claude code, claude-code, claude.ai, anthropic, sonnet, opus, haiku |
| TypeScript | typescript, ts, type system, types, typed, tsconfig, deno, bun |
| OSS | open source, oss, github, apache, mit license, gpl, open-source, foss, community |
| Security | security, vuln, cve, exploit, auth, oauth, jwt, xss, csrf, encrypt, zero trust, supply chain |
| DevTools | devtools, dev tool, cli, debug, ide, editor, vscode, terminal, tooling, workflow, lint, format, build, bundle, compile, ci/cd, git |
| AI Engineering | ai, llm, gpt, model, ml, machine learning, deep learning, transformer, embedding, inference, training, fine-tune, prompt, rag, vector, neural |

Pick top 1-3 themes by keyword match score. Default to the list's primary domain if no keywords match.

### Signal Detection

- **Check referenced_tweets first**: if `referenced_tweets[].type == "replied_to"` → 🟢 Discussion
- **Short text + link**: if URL-stripped text < 50 chars → ⚪ Link/Ref
- **Signal keywords**: announce, launch, release, shipping, just shipped, new, introducing, now available, alpha, beta, product, live, deploy, publish → 🔴 Signal
- **Insight keywords**: think, believe, opinion, prediction, hot take, trend, observation, interesting, fascinating, underrated, overrated, should, would be, seems, might be → 🟡 Insight
- **Fallback**: ⚪ Link/Ref

### Source Detection

- **Replies** (text starts with `@`) → Community
- **Builder keywords**: i built, i made, i created, i shipped, i launched, my, our, we built, we made, we shipped, just shipped, check out my, i wrote, i published, my new → Builder
- **Analyst keywords**: i think, i believe, opinion, analysis, prediction, hot take, observation, trend, should, would, might, could, seems, interesting how, fascinating, underrated → Analyst
- **Curator keywords**: check out, via, by @, from @, great post, great thread, must read, worth reading, good read, recommend → Curator
- **Tiebreaker**: Builder > Curator > Analyst > Community fallback

## When Automated Tagging Fails

The keyword approach fails on:
- **Context-dependent tweets**: "Pump the classics into my veins" (meme) tagged as AI Engineering — actually TypeScript (Matt Pocock's domain)
- **Joke/meme tweets**: "junior engineers after submitting their first slop PR" (4868 likes) — keyword match picks up "AI" but it's a meme, not engineering content
- **Short commentary with link**: "imagine the phishing attacks [link]" — only detectable as Security if you read the link or know the author's domain
- **General tech observations**: "Apple gaslighting me about spelling" — keyword match gives AI Engineering, but it's a DevTools/UX observation

## Manual Correction Rules

1. **Author domain matters**: @mattpocockuk = TypeScript, @colinhacks = APIs/Security/TypeScript, @kentcdodds = web dev/agent tools, @RhysSullivan = agent tools/infra
2. **Link context**: When a tweet is mostly a link, infer the theme from the author's domain and the surrounding conversation
3. **Meme/joke tweets**: These are almost always ⚪ Link/Ref + Curator, regardless of automated signal score
4. **Thread context**: Replies in a thread inherit context from the parent — a joke reply about Scottish accents in a thread about AI tools is Discussion/Community, not AI Engineering
5. **Engagement ≠ Signal**: A viral meme (4868 likes) is still Link/Ref, not Signal. Signal requires substantive announcements/launches.

## Off-Topic Filtering Patterns

Build domain-specific off-topic regex patterns to exclude non-relevant content from crypto/finance lists. **ALL patterns MUST be lowercase** — see case-sensitivity pitfall below.

Common off-topic categories to filter:
- **War/travel content** from crypto personalities in conflict zones (Kramatorsk, Ukraine, drone footage) — unless they explicitly mention crypto fundraising (BTC/SOL/ETH)
- **Sports/gaming**: NBA, football, race commentary, e-sports
- **Personal life**: vacation snaps, Spotify complaints, gym advice, home projects
- **Podcast episode announcements** (`r'new episode of @'`) — link-forward with zero original content
- **Political rants** without crypto angle
- **Generic meme templates**: "How it started / How it's going" with just image links

### Override mechanism

Build a `strong_crypto` keyword list (BTC, Bitcoin, $ETH, Hyperliquid, Clarity Act, Lightning Network, SBR, etc.). If any strong signal is present, skip off-topic filtering. Without this override, crypto content with incidental personal words gets filtered; with it too lax, you get travelogues.

## Critical Regex Pitfall: Case Sensitivity

**If your regex patterns contain uppercase (`r'ADD'`, `r'What ADD'`) but you match against `text.lower()`, they silently fail.** The pattern `r'What (having )?ADD (is|looks) like'` will NEVER match `text.lower()` output `"what having add is like"`. Write ALL patterns lowercase: `r'what (having )?add (is|looks) like'`.

This caused an ADHD tweet with 63K likes to pass through the off-topic filter and appear as "Bitcoin" in a crypto digest — the pattern had uppercase `ADD` but the match target was lowercased.
