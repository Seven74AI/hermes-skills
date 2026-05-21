---
name: edgee-lab
description: "Edgee Lab project configuration — profiles, pipeline, cron jobs, strategy research."
version: 2.1.0
metadata:
  hermes:
    tags: [edgee, project, kanban, cron, reference, strategy]
---

# Edgee Lab — Project Configuration

Competitive strategy & integration research for Edgee (edgee.ai), an AI Agent Gateway with active token compression.

## GitHub

- Repo: `Seven74AI/edgee-lab`
- No active PRs — research-only project
- Local checkout: `/root/edgee-lab`

## Docker Setup (Ready)

Edgee CLI Docker image built and functional (v0.2.6). No official Docker image exists — custom Dockerfile at `/root/edgee-lab/docker/Dockerfile`.

**Structure:**
| File | Purpose |
|------|---------|
| `docker/Dockerfile` | Edgee CLI container (debian:bookworm-slim + binary from GitHub) |
| `docker-compose.yml` | Orchestration, mounts edgee-config volume |
| `.env.example` | Template — copy to `.env`, no secrets |
| `hermes-edgee-provider.yaml` | Hermes provider config for Edgee Cloud |

**Commands:**
```bash
cd /root/edgee-lab
cp .env.example .env                    # first time
docker compose build edgee              # build image
docker compose run --rm edgee --version # verify (v0.2.6)
docker compose run --rm edgee auth login  # OAuth (needs browser)
```

**Important:** Edgee v0.2.6 does NOT have a `serve` command. It is purely a CLI wrapper for coding agents. The gateway functionality is via Edgee Cloud (`api.edgee.ai`). For Hermes headless integration, configure a provider pointing to `https://api.edgee.ai/v1` with `x-edgee-api-key` header.

## Kanban Board

- Board: `edgee-lab`
- Profiles: researcher (primary), planner, reviewer

## What We Know

Edgee is the ONLY AI gateway doing active token compression. 8 competitors analyzed (Helicone, Portkey, LiteLLM, Cloudflare AI Gateway, Kong AI Gateway, Bifrost, Langfuse, OpenRouter) — all only cache or route, none compress tokens.

**Key metrics** from T8 integration test:
- Edgee TTFB: 0.038s vs DeepSeek direct: 0.308s (8× faster via Fastly CDN)
- Token compression: up to 50% savings, sessions 26.5% longer
- Integration: zero code changes, transparent proxy

## Authentication — Two Modes

Edgee has two separate auth modes — do NOT confuse them:

| Mode | Auth | Use case |
|------|------|----------|
| **CLI tool** (`edgee`) | Browser OAuth (`edgee auth login`) | Interactive wrapping of Claude Code, Codex, OpenCode |
| **API Gateway** (`api.edgee.ai/v1`) | API key (`sk-edgee-...` header) | Hermes headless integration, transparent LLM proxy |

**For Hermes integration:** use the API Gateway with API key. No OAuth, no Docker, no CLI needed. The API key was obtained from https://console.edgee.ai → API Keys.

```bash
hermes config set provider edgee
hermes config set base_url https://api.edgee.ai/v1
hermes config set api_key $EDGEE_API_KEY
```

The Docker setup in this repo is for the CLI tool only (optional, not needed for Hermes).

## Cron Jobs

| Job | ID | Schedule | Purpose |
|-----|-----|----------|---------|
| Daily Report | `b4e9989d4d72` | 0 9 * * * | Competitor & product digest → Discord #seven-ai |
| Strategy Research | `cffd88539f6a` | every 3h | Rotates through strategy tickets, continues research, creates new tickets when done → Discord #seven-ai |

## Monitoring Sources & Feeds

The daily monitor cron (`b4e9989d4d72`) scans these sources via blogwatcher-cli. Feeds were discovered manually — standard auto-discovery fails for several sites.

| Blog | URL | Feed/Scraper | Status |
|------|-----|-------------|--------|
| Edgee Blog | `https://www.edgee.ai/blog` | `--scrape-selector "article h3 a, article h2 a"` | No RSS (Next.js). HTML scrape. |
| Cloudflare Blog | `https://blog.cloudflare.com` | RSS auto-detected ✓ | Working |
| Fastly Blog | `https://www.fastly.com/blog` | RSS auto-detected ✓ | Working |
| BunnyCDN Blog | `https://bunny.net/blog` | `--feed-url https://bunny.net/blog/rss/` | RSS at non-standard path |
| Bytecode Alliance | `https://bytecodealliance.org/articles` | `--feed-url https://bytecodealliance.org/feed.xml` | Feed at non-standard path |

To re-add after DB reset:
```bash
blogwatcher-cli add "Cloudflare Blog" https://blog.cloudflare.com
blogwatcher-cli add "Fastly Blog" https://www.fastly.com/blog
blogwatcher-cli add "BunnyCDN Blog" https://bunny.net/blog --feed-url https://bunny.net/blog/rss/
blogwatcher-cli add "Bytecode Alliance (WASM)" https://bytecodealliance.org/articles --feed-url https://bytecodealliance.org/feed.xml
blogwatcher-cli add "Edgee Blog" https://www.edgee.ai/blog --scrape-selector "article h3 a, article h2 a"
```

### Daily Monitor — Known Pitfalls

- **Xurl OAuth2 silent expiry**: The xurl token can expire silently in headless/cron environments. `xurl auth status` may show a valid user but `xurl whoami` returns 401 — the refresh token on disk went stale. Schedule `xurl whoami` 30 minutes before the cron job to force a live refresh and keep on-disk tokens fresh. Re-auth requires browser OAuth: `ssh -L 8080:localhost:8080 user@server` then `xurl auth oauth2 --app my-app seven_dai74`.
- **Web search/extract credits**: If Firecrawl returns "Payment Required" / "Insufficient credits", fall back to blog RSS + GitHub APIs. The monitoring pipeline is designed to function without web_search.
- **Edgee.ai RSS**: Edgee's blog is Next.js with no RSS endpoint. The HTML scraper (`article h3 a`) works but is fragile — if Edgee changes their blog markup, posts will stop being detected. Check the HTML manually with `curl` if the scraper returns 0 posts for more than a week.
- **Blogwatcher initial scan**: First scan after adding blogs will flag ALL historical posts as "new" (45+ articles). The `articles` listing is chronological; the daily monitor should focus on posts from the last 24h, not the full "new" list.

## Pipeline (Complete)

### Phase 1 — Research (done ✓)
T1: Research plan → T2: Edgee deep-dive → T3: Competitor landscape → T4: Hermes compatibility → T5-T6: Monitoring setup → T7: Local benchmark → T8: Hermes integration test

### Phase 2 — Strategy (in progress)
8 strategy tickets: self-serve onboarding, open-source gateway, content marketing, integrations marketplace, developer advocacy, pricing, token compression competitors, growth playbook.

### Phase 3 — Integration (ready)
API key obtained ✅. Ready to configure Hermes provider pointing to `https://api.edgee.ai/v1`. Next: deploy as Hermes proxy, measure real-world compression savings, validate in production.

## Competitive Analysis Methodology (CRITICAL)

When analyzing Edgee's competitors, do NOT search for "AI gateway competitors." Edgee's core differentiator is **token compression**, not gateway routing. Search for: "token compression API", "LLM context compression proxy", "prompt compression service", "context window optimization". The gateway category (Helicone, Portkey, etc.) is the wrong comparison set — they compete on routing/observability, not compression.
