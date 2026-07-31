# Firecrawl Stack Health Check

Self-hosted Firecrawl Docker stack diagnosis. The browser tool (`browser_navigate`, etc.) uses Firecrawl for cloud browser sessions via the `/tabs` and `/v2/browser` endpoints.

## Health check commands

```bash
# 1. Is the stack running?
docker ps --format '{{.Names}} {{.Status}}' | grep firecrawl

# Expected: firecrawl-api-1, firecrawl-playwright-service-1, firecrawl-redis-1, firecrawl-rabbitmq-1, firecrawl-nuq-postgres-1

# 2. API root responds?
curl -s http://127.0.0.1:3002/
# Expected: {"message":"Firecrawl API","documentation_url":"https://docs.firecrawl.dev"}

# 3. Browser endpoint functional?
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3002/v2/browser
# Expected: anything other than 500 or 404

# 4. RabbitMQ healthy? (most common failure mode)
docker logs firecrawl-api-1 --tail 50 2>&1 | grep -i "rabbitmq\|noproc\|connection error"
# Healthy: no output. Unhealthy: "INTERNAL_ERROR - noproc", "Channel ended, no reply"

# 5. Playwright service reachable?
docker logs firecrawl-playwright-service-1 --tail 10 2>&1
```

## Common failure: RabbitMQ queue corruption

**Symptom:** `/v2/browser` returns 500, scrape endpoints return errors, logs show `INTERNAL_ERROR - Cannot get a message from queue 'queue 'nuq.queue_*' in vhost '/': noproc`

**Fix:** Restart the stack
```bash
cd /path/to/firecrawl  # or wherever docker-compose.yml lives
docker compose restart
```

## Common failure: browser tool 404 on /tabs

**Symptom:** `browser_navigate` fails with "404 Client Error: Not Found for url: http://127.0.0.1:3002/tabs"

**This is NOT a wrong endpoint.** `/tabs` is the Firecrawl browser session management endpoint. The 404 means the Firecrawl API doesn't have browser support enabled or the stack is unhealthy.

**Diagnosis:**
1. Check RabbitMQ health (see above)
2. Check if `FIRECRAWL_API_URL` is set correctly in `~/.hermes/.env`
3. Check if the Firecrawl API key is valid
4. Try the cloud API instead: set `FIRECRAWL_API_URL=https://api.firecrawl.dev`
