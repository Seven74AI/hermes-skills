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

Both providers use identical OpenAI-compatible format. Toggle is a one-line `base_url` change:

```python
# DeepSeek direct
base_url = "https://api.deepseek.com/v1"

# Edgee (add compression_model for compression)
base_url = "https://api.edgee.ai/v1"
extra_fields = {"compression_model": "claude"}
```

No code changes needed beyond `base_url` + optional `compression_model` injection.

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
