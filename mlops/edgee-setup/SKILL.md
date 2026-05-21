---
name: edgee-setup
description: "Install, configure, and troubleshoot Edgee as an LLM provider for Hermes Agent."
version: 2.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [edgee, provider, setup, configuration]
---

# Edgee Provider Setup

Edgee is an AI gateway that routes requests to various LLM providers (DeepSeek, OpenAI, Anthropic, etc.) through a single API endpoint.

**⚠️ VERDICT (2026-05-20): Edgee is INCOMPATIBLE with Hermes Agent for interactive use.** Both endpoints fail for different reasons. Use DeepSeek direct instead.

## Why Edgee doesn't work with Hermes

| Endpoint | Issue | Status |
|----------|-------|--------|
| OpenAI `/chat/completions` | 3 server-side streaming bugs (illegal chunk header, HTTP/2 StreamReset, incomplete chunked read on large contexts ~80K tok) | ❌ Server-side, unfixable from client |
| Anthropic `/v1/messages` | `api_mode: anthropic_messages` breaks Hermes entirely — even without Edgee as provider | ❌ Hermes Anthropic adapter incompatibility |

**Workaround attempted and reverted (2026-05-20):** h11 CRLF monkey-patch + HTTP/2 killswitch + agent_init.py injection. 4 patches across `run_agent.py` and `agent/agent_init.py`. These fixed bugs #1 and #2 but bug #3 (server-side timeout on large contexts) remained. All patches have been reverted — Hermes source is clean.

**Recommendation:** Configure DeepSeek as a direct provider instead.

## DeepSeek Direct (Working Alternative)

```bash
# In config.yaml, use DeepSeek as a standard provider:
hermes config set model.provider deepseek
hermes config set model.default deepseek-v4-pro
hermes config set model.base_url https://api.deepseek.com/v1
```

Store the key in `~/.hermes/.env`:
```bash
DEEPSEEK_API_KEY=sk-...
```

## Complete Edgee Removal (when migrating away)

If Edgee was previously configured, three files need cleanup — not just config.yaml:

### 1. config.yaml — model section
```yaml
model:
  provider: deepseek           # was: edgee
  base_url: https://api.deepseek.com/v1  # was: https://api.edgee.ai/v1
  default: deepseek-v4-pro     # was: deepseek/deepseek-v4-pro
```

### 2. config.yaml — custom_providers
```yaml
custom_providers: {}           # remove the Edgee entry entirely
```

### 3. auth.json — credential_pool
```json
// Remove the entire "custom:edgee---deepseek" key from credential_pool.
// This contains 2 entries (api_key + model_config) with Edgee tokens.
// Watch for trailing commas — the JSON must remain valid after removal.
```

### 4. .env (optional)
The `EDGEE_API_KEY` can be kept or removed — it's harmless if no provider references it.

### 5. Verify
```bash
grep -in edgee ~/.hermes/config.yaml ~/.hermes/auth.json  # should return nothing
python3 -c "import json; json.load(open('~/.hermes/auth.json'))"  # valid JSON
hermes mcp list  # ensure no Edgee-related MCP servers remain
```

### Pitfall: auth.json JSON breakage
Removing the last key from `credential_pool` leaves a trailing comma on the previous key. The resulting JSON is invalid. Fix: remove the trailing comma from the preceding `],` line so it becomes `]`.

## Bug Details (for reference)

### OpenAI `/chat/completions` (3 bugs)

| # | Error | Protocol | Detail |
|---|-------|----------|--------|
| 1 | `illegal chunk header: \\r\\n` | HTTP/2 | Bare CRLF before first SSE chunk — h11 ChunkedReader fails |
| 2 | `StreamReset stream_id:1 error_code:1` | HTTP/2 | RST_STREAM PROTOCOL_ERROR — Edgee HTTP/2 streaming fundamentally broken |
| 3 | `incomplete chunked read` | HTTP/1.1 | Server drops connection ~1s after 200 OK, before DeepSeek streams. Only triggers with large Hermes contexts (~80K tokens) |

Bugs #1 and #2 were fixable with client-side workarounds (h11 monkey-patch + HTTP/2 killswitch), but bug #3 is a server-side timeout — Edgee gives up waiting for DeepSeek to start streaming on large prompts. Unfixable from the client.

### Anthropic `/v1/messages`

Setting `api_mode: anthropic_messages` in config.yaml breaks Hermes entirely, even when the provider is NOT Edgee. The Anthropic adapter path in Hermes appears incompatible with how it's activated via `api_mode`. Root cause not fully diagnosed — but the endpoint is not a viable workaround.

## Diagnostic References

See `references/` for full diagnostic logs:
- `references/http2-curl-isolation.md` — Protocol isolation technique
- `references/http2-h11-root-cause.md` — HTTP/2 vs h11 analysis
- `references/diagnostic-tests.md` — Systematic testing methodology
- `references/large-context-streaming-timeout.md` — Bug #3 deep dive
- `references/edgee-http2-debug.md` — HTTP/2 debugging

## Docker (Edgee Lab)

If running Edgee locally for non-Hermes use:

```bash
cd /root/edgee-lab
docker compose up -d
```

Local endpoint: `http://localhost:3000`.
