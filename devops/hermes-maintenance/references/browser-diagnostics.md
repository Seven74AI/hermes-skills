# Browser Tool Diagnostics

When `browser_navigate` fails, diagnose from the bottom up — do NOT guess at what endpoint should work.

## Quick diagnosis checklist

```bash
# 1. Check what browser provider is configured
grep -A5 "^browser:" ~/.hermes/config.yaml

# 2. Check Firecrawl env (if Firecrawl is the provider)
grep FIRECRAWL ~/.hermes/.env

# 3. What's actually running on the browser proxy port?
curl -s http://127.0.0.1:3002/          # should return Firecrawl API JSON
docker ps --filter name=firecrawl        # find the compose stack
docker compose ps                        # check service health (from compose dir)

# 4. Test the browser session endpoint directly
curl -s -X POST http://127.0.0.1:3002/v2/browser \
  -H "Content-Type: application/json" -d '{}'

# 5. Check Firecrawl API logs for the error
docker logs firecrawl-api-1 --tail 50 | grep -i "browser\|error"
```

## Common failure modes

### "404 Client Error: Not Found for url: .../tabs"

The Hermes browser client calls Firecrawl's browser session endpoint. A 404 means the Firecrawl API at `FIRECRAWL_API_URL` doesn't have browser sessions enabled. Check:

- Is the Firecrawl API actually running? (`curl` the root)
- Does `BROWSER_SERVICE_URL` point to the playwright service? Check `docker-compose.yaml` env for the API container.
- Does the playwright service have the `/browsers` endpoint? The default `firecrawl-playwright-service` in the standard compose is a **scraper** (has `/scrape` only), NOT a browser session manager. It does NOT serve `/browsers`.

### "Browser feature is not configured (BROWSER_SERVICE_URL is missing)"

The Firecrawl API needs `BROWSER_SERVICE_URL=http://playwright-service:3000` in its environment. Add it to `docker-compose.yaml` under the API service's `environment:` block:

```yaml
BROWSER_SERVICE_URL: ${BROWSER_SERVICE_URL:-http://playwright-service:3000}
```

Then recreate the container: `docker compose up -d --no-deps api`

### "Failed to create browser session" / playwright returns 404 on /browsers

The playwright service in the default Firecrawl compose is scraper-only. It has `/scrape` (used by `PLAYWRIGHT_MICROSERVICE_URL`) but NOT `/browsers` (needed for browser sessions). This configuration cannot serve Hermes browser tools — the self-hosted Firecrawl needs a different playwright service build or the cloud API.

### "Database client is not configured"

The Firecrawl browser-sessions module needs a database. `USE_DB_AUTHENTICATION=false` may help, but the core issue is usually the missing `BROWSER_SERVICE_URL` or mismatched playwright service.

## Fallback: agent-browser (local Chrome)

When Firecrawl self-hosted can't do browser sessions, use `agent-browser` with a local Chromium:

```bash
# Install Chrome + system deps
agent-browser install --with-deps

# Test
agent-browser open http://localhost:3000 --timeout 60000
agent-browser snapshot -i
agent-browser click @e3
agent-browser fill @e5 "text"
agent-browser press Enter
agent-browser close
```

**SSR timing:** React/Remix SSR can take 10-60s on first load. Use `--timeout 60000` (60s) or higher. Without it, `agent-browser open` times out.

**Form submission:** React Router `<Form>` components may not respond to `click` on the submit button. Use `press Enter` on the last input field instead — this triggers the native form submit event that React Router intercepts.
