---
name: edgee-setup
description: "Install, configure, and use Edgee as an LLM gateway for custom agents (non-Hermes)."
version: 3.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [edgee, provider, setup, configuration]
---

# Edgee — AI Gateway

Edgee is an AI gateway that routes requests to various LLM providers (DeepSeek, OpenAI, Anthropic, etc.) through a single API endpoint. It applies compression, routing, and observability to every request.

**Use for:** custom agents (KB Agent, standalone Python scripts) that call Edgee directly via httpx/requests.
**Do NOT use for:** Hermes Agent interactive chat — use DeepSeek direct for Hermes.

## Endpoint

```
POST https://api.edgee.ai/v1/chat/completions
Authorization: Bearer $EDGEE_API_KEY
Content-Type: application/json
```

OpenAI-compatible format. Standard `messages`, `tools`, `tool_choice`, `stream` fields all supported. Both streaming and non-streaming work.

## Model Naming Convention (Critical)

Edgee routes by provider prefix. Model names MUST use the format **`provider/model`**:

```
✓ deepseek/deepseek-v4-pro
✓ openai/gpt-4o
✓ anthropic/claude-sonnet-4

✗ deepseek-v4-pro          → shows as <unknown> in Edgee dashboard
✗ gpt-4o                   → rejected or misrouted
```

If you're building an agent that toggles between Edgee and a direct provider, normalize the model name when switching: prepend `deepseek/` (or the appropriate provider) when routing through Edgee, strip it for direct calls.

## Provider API Keys (Edgee Dashboard)

`EDGEE_API_KEY` authenticates your agent **to the Edgee gateway** — it does NOT grant access to upstream providers. Edgee uses **its own API keys** for each provider, configured in the Edgee dashboard:

1. Go to your Edgee dashboard → Provider Settings
2. Add/update API keys for each upstream provider (DeepSeek, OpenAI, etc.)
3. The key must be valid and have credits — Edgee passes it through to the provider

**Symptom if misconfigured:** Edgee returns `400` with an embedded `401` from the upstream provider:
```json
{"error":{"message":"DeepSeek API error (401 Unauthorized): ...",
 "code":"unauthorized"}}
```
→ Fix the provider API key in the Edgee dashboard, not the `EDGEE_API_KEY`.

## Edgee-Specific Request Fields

| Field | Type | Effect |
|-------|------|--------|
| `compression_model` | `"claude"` \| `"opencode"` \| `"cursor"` \| `"customer"` | Enables transparent token compression. Use `"claude"` for general-purpose. |
| `tags` | `list[str]` | Labels requests for observability (e.g., `["kb-agent", "synthesis"]`) |

## Response Extras

```json
{
  "choices": [...],
  "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N},
  "compression": {
    "saved_tokens": 12450,
    "cost_savings": 27000,
    "reduction": 48,
    "time_ms": 342
  }
}
```

- `saved_tokens` — tokens removed from context by compression
- `cost_savings` — micro-units (divide by 1,000,000 for $)
- `reduction` — percentage of input tokens compressed
- `time_ms` — compression processing time

## Toggle Pattern (Edgee ↔ DeepSeek)

Both providers use identical OpenAI-compatible format. Toggle requires a `base_url` change AND model name normalization:

```python
# DeepSeek direct — bare model name
base_url = "https://api.deepseek.com/v1"
model = "deepseek-v4-pro"

# Edgee — provider/model format
base_url = "https://api.edgee.ai/v1"
model = "deepseek/deepseek-v4-pro"
extra_fields = {"compression_model": "claude"}
```

Normalize at toggle time:

```python
if provider == "edgee" and "/" not in model:
    model = f"deepseek/{model}"
```

## Python SDK

```bash
pip install edgee
```

```python
from edgee import Edgee, InputObject

edgee = Edgee("api-key")

# Simple
response = edgee.send("deepseek/deepseek-v4-pro", "Hello")

# With tools + compression + streaming
response = edgee.send("deepseek/deepseek-v4-pro", InputObject(
    messages=[{"role": "user", "content": "..."}],
    tools=[{"type": "function", "function": {...}}],
    compression_model="claude",
    tags=["synthesis"]
))

# Streaming
for chunk in edgee.stream("deepseek/deepseek-v4-pro", "Tell me a story"):
    print(chunk.text, end="")

# Compression metrics
if response.compression:
    print(f"Saved: {response.compression.saved_tokens} tokens")
    print(f"Reduction: {response.compression.reduction}%")
```

Full API reference: `references/edgee-api-reference.md`

## Docker (Edgee Lab)

If running Edgee locally:

```bash
cd /root/edgee-lab
docker compose up -d
```

Local endpoint: `http://localhost:3000`.
