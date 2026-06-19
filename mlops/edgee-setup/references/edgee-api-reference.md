# Edgee Gateway API — Full Reference

Sourced from `github.com/edgee-ai/python-sdk` source code (2026-06-19).

## Endpoint

```
POST https://api.edgee.ai/v1/chat/completions
Authorization: Bearer $EDGEE_API_KEY
Content-Type: application/json
```

## Request Format (OpenAI-compatible + Edgee extensions)

```json
{
  "model": "deepseek/deepseek-v4-pro",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "read_file",
        "description": "Read a file",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}
      }
    }
  ],
  "tool_choice": "auto",
  "stream": false,
  "tags": ["kb-agent", "synthesis"],
  "compression_model": "claude"
}
```

### Edgee-Specific Fields

| Field | Type | Required | Effect |
|-------|------|----------|--------|
| `compression_model` | `"claude"` \| `"opencode"` \| `"cursor"` \| `"customer"` | No | Enables transparent token compression at gateway level. `"claude"` is the recommended general-purpose model. |
| `tags` | `list[str]` | No | Labels requests for observability in Edgee console. |

### Standard OpenAI Fields (all supported)

| Field | Notes |
|-------|-------|
| `model` | Format: `"provider/model"` (e.g., `"deepseek/deepseek-v4-pro"`, `"anthropic/claude-sonnet-4"`) or bare model name |
| `messages` | Standard `role`/`content` array |
| `tools` | Full function calling support |
| `tool_choice` | `"auto"`, `"none"`, or specific function |
| `stream` | `true` for SSE streaming, `false` for non-streaming |

## Response Format

### Non-Streaming (`stream: false`)

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1718400000,
  "model": "deepseek/deepseek-v4-pro",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris.",
        "tool_calls": null
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 8,
    "total_tokens": 33
  },
  "compression": {
    "saved_tokens": 0,
    "cost_savings": 0,
    "reduction": 0,
    "time_ms": 12
  }
}
```

### Streaming (`stream: true`)

Standard SSE (`text/event-stream`) with `data: ` prefixed JSON chunks. Each chunk is an OpenAI-compatible delta.

### Compression Response Fields

| Field | Type | Meaning |
|-------|------|---------|
| `saved_tokens` | `int` | Tokens removed from context by compression |
| `cost_savings` | `int` | Micro-units saved (divide by 1,000,000 for USD) |
| `reduction` | `int` | Percentage of input tokens compressed (0-100) |
| `time_ms` | `int` | Milliseconds spent on compression |

Compression fields are always present in the response, even when compression is disabled (values will be zero).

## Model Format

Models are specified as `"provider/model"`:
- `"deepseek/deepseek-v4-pro"`
- `"anthropic/claude-sonnet-4"`
- `"anthropic/claude-haiku-4-5"`
- `"openai/gpt-5.2"`
- Or bare model names for Edgee's default routing

Edgee routes to the appropriate provider based on the model prefix.

## Python SDK

```bash
pip install edgee
```

### Simple Usage
```python
from edgee import Edgee
edgee = Edgee("api-key")
response = edgee.send("deepseek/deepseek-v4-pro", "Hello")
print(response.text)
```

### With Tools + Compression
```python
from edgee import Edgee, InputObject

edgee = Edgee("api-key")
response = edgee.send("deepseek/deepseek-v4-pro", InputObject(
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Read /tmp/file.txt"}
    ],
    tools=[{
        "type": "function",
        "function": {
            "name": "read_file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}
        }
    }],
    compression_model="claude",
    tags=["synthesis"]
))

# Access response
print(response.text)
print(response.tool_calls)
if response.compression:
    print(f"Saved {response.compression.saved_tokens} tokens ({response.compression.reduction}%)")
```

### Streaming
```python
for chunk in edgee.stream("deepseek/deepseek-v4-pro", "Tell me a story"):
    if chunk.text:
        print(chunk.text, end="", flush=True)
```

### Configuration
```python
# API key via constructor
edgee = Edgee("api-key")

# Via config dict
edgee = Edgee({"api_key": "...", "base_url": "https://custom.edgee.ai"})

# Via environment variables
# EDGEE_API_KEY=... EDGEE_BASE_URL=...
edgee = Edgee()
```

## Known Issues

### Streaming (Hermes Agent)
Edgee's streaming has 3 server-side bugs that prevent use with Hermes Agent:
1. Illegal chunk header in SSE stream
2. HTTP/2 StreamReset on large contexts
3. Server-side timeout on large prompts (~80K tokens)

These do NOT affect non-streaming calls. Custom agents using `stream=False` are unaffected.

### Anthropic Messages API
Setting `api_mode: anthropic_messages` breaks Hermes regardless of provider. Not an Edgee-specific issue.

## Docker (Edgee Lab)

If running Edgee locally for testing:
```bash
cd /root/edgee-lab
docker compose up -d
```
Local endpoint: `http://localhost:3000`

## References

- Main docs: https://docs.edgee.ai
- Python SDK: https://github.com/edgee-ai/python-sdk
- PyPI: https://pypi.org/project/edgee/
