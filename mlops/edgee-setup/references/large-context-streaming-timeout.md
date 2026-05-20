# Bug #3 — Large-Context HTTP/1.1 Streaming Timeout

Discovered 2026-05-20 after fixing bugs #1 (bare CRLF) and #2 (HTTP/2 StreamReset).

## Symptom

```
⚠️  API call failed: RemoteProtocolError
   📝 Error: peer closed connection without sending complete message body (incomplete chunked read)

Log: http_status=200 bytes=0 chunks=0 elapsed=0.73-1.17s ttfb=-
```

Edgee sends HTTP 200 OK headers, then drops the TCP connection within ~1 second
without sending ANY chunked body data.

## Trigger

Only occurs with large Hermes contexts (~80K tokens: 76 tools + AGENTS.md + memory + user profile + conversation history). Does NOT occur with:

- Small one-shot queries (`hermes chat -q "hi"`)
- Direct curl/httpx streaming with <10K token prompts
- Non-streaming requests of any size

## Root Cause

Edgee is a reverse proxy to DeepSeek. The sequence observed:

1. Hermes sends ~80K token request over HTTP/1.1
2. Edgee receives it, opens connection to DeepSeek
3. Edgee sends HTTP 200 OK to Hermes (prematurely, before DeepSeek responds)
4. DeepSeek takes >1 second to start streaming on an 80K token prompt
5. Edgee times out waiting for DeepSeek — drops Hermes connection
6. Hermes gets "incomplete chunked read"

Small prompts (~10-10K tokens) succeed because DeepSeek starts streaming immediately
(within Edgee's ~1 second window).

## Diagnostic Evidence

```bash
# Works: small prompt + streaming via curl
curl -s -N -H "Authorization: Bearer $KEY" \
  -d '{"model":"deepseek/deepseek-v4-pro","messages":[{"role":"user","content":"say hi"}],"max_tokens":10,"stream":true}' \
  https://api.edgee.ai/v1/chat/completions
# → 200 OK, chunks received, 5-7 seconds

# Works: large prompt (10K chars padding) + streaming via curl
# → 200 OK, chunks received, 10.7 seconds

# Fails: Hermes interactive session with accumulated context
# → 200 OK, 0 bytes, connection dropped after ~1s

# Works: non-streaming any size
# → 200 OK, complete response, 6-10 seconds
```

## Verdict

**Server-side Edgee defect — no client-side fix possible.** The timeout window
(~1 second) between Edgee sending 200 OK and receiving DeepSeek's first token
is too narrow for large-context processing. DeepSeek direct is the recommended
alternative.
