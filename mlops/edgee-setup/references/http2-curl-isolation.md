# HTTP/2 vs HTTP/1.1 Protocol Isolation Diagnostic

A technique for isolating whether a provider streaming issue is HTTP-version-specific.
This was developed while debugging Edgee's `StreamReset error_code:1` bug (2026-05-20).

## The technique

When a provider returns protocol-level errors on streaming requests, isolate the HTTP
version with two simple `curl` commands:

```bash
# Test 1: HTTP/1.1 forced
curl -s -N --http1.1 \
  https://api.example.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model":"model-name","messages":[{"role":"user","content":"hi"}],"stream":true,"max_tokens":50}'

# Test 2: HTTP/2 forced
curl -s -N --http2 \
  https://api.example.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model":"model-name","messages":[{"role":"user","content":"hi"}],"stream":true,"max_tokens":50}'
```

If HTTP/1.1 works and HTTP/2 doesn't, the bug is HTTP-version-specific on the server side.

## Check which protocol a provider negotiates by default

```bash
curl -s -o /dev/null -w "http_version: %{http_version}\n" \
  https://api.example.com/v1/models \
  -H "Authorization: Bearer $API_KEY"
```

## Edgee results (2026-05-20)

| Protocol | Streaming | Non-streaming |
|----------|-----------|---------------|
| HTTP/1.1 (`--http1.1`) | ✅ Works, clean SSE chunks | ✅ Works |
| HTTP/2 (`--http2`) | ❌ Timeout, 0 bytes received | ✅ Works |
| Default (ALPN) | HTTP/2 → broken | ✅ Works |

**Conclusion:** Edgee's HTTP/2 server implementation is broken for streaming chat completions.
This is a server-side defect — not a client or payload issue. The `StreamReset error_code:1`
seen in Hermes is the httpx/httpcore representation of Edgee's HTTP/2 server dropping the stream.

## Why this matters

- Prevents hours of client-side code archaeology when the bug is server-side
- Provides clear evidence when reporting to the provider
- Works for any OpenAI-compatible endpoint
- No need to instrument the agent — a single curl command is definitive
