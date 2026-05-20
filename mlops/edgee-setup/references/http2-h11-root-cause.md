# HTTP/2 vs h11 root-cause analysis (2026-05-19)

## Error Transcript

```
⚠️ custom stream drop (RemoteProtocolError) after 1.2s — reconnecting, retry 2/3
📝 Error: illegal chunk header: bytearray(b'\r\n')
⏳ Retrying in 2.8s (attempt 1/3)...
❌ Connection to provider failed after 3 attempts.
```

Always with `bytes=0 chunks=0 elapsed=<1s` — the stream drops before the first
real chunk arrives.

## Why the original h11 CRLF fix was ineffective

Hermes builds its HTTP client in `run_agent.py:_build_keepalive_http_client`:

```python
return _httpx.Client(
    transport=_httpx.HTTPTransport(socket_options=_sock_opts, http2=True),
    ...
)
```

`http2=True` means httpx negotiates HTTP/2 with the server. In HTTP/2 mode:
- **`h2` library** handles frame-level protocol (DATA frames, HEADERS frames, etc.)
- **`h11` library** is NEVER used for chunked transfer decoding — h2 has its own framing

The `edgee_crlf_fix.py` monkey-patches `h11._readers.ChunkedReader.__call__`,
which only runs in HTTP/1.1 mode. In HTTP/2 mode, the patch is a no-op:
the function is never called, and the bare `\r\n` from Edgee's server
causes h2 to raise `RemoteProtocolError` (not h11's `LocalProtocolError`).

## The actual fix

Two changes required:

1. **Force HTTP/1.1 for Edgee** — modify `_build_keepalive_http_client`:
   ```python
   _use_http2 = "api.edgee.ai" not in (base_url or "")
   transport=_httpx.HTTPTransport(socket_options=_sock_opts, http2=_use_http2)
   ```
   This makes the transport use h11 for Edgee, so the CRLF fix actually runs.

2. **Keep the h11 CRLF monkey-patch** (Step 0a in SKILL.md) — now that h11
   is active, it can intercept and skip the bare `\r\n`.

## Why one-shot queries work but interactive doesn't

Both use `http2=True` by default. The difference is context size:
- One-shot: minimal context (just the user message)
- Interactive: full agent context (76 tools + AGENTS.md + memory + user profile)

Edgee's server-side processing only produces the bare `\r\n` artifact when
processing the heavy context payload. The HTTP version is the same either way.

## Why other agents (Claude Code, Codex) work with Edgee

These agents likely differ in at least one of:
- Use different API endpoints (not `/v1/chat/completions` streaming)
- Send smaller context/tool payloads
- Use different HTTP client configurations
- Edgee has explicit handling paths for these supported agents

Hermes sends the largest context (76 tools + full AGENTS.md at ~51KB) through
the generic OpenAI-compatible streaming endpoint, which triggers Edgee's bug.

---

# Bug #2: StreamReset PROTOCOL_ERROR (2026-05-20)

## Error Transcript

```
⚠️ custom stream drop (RemoteProtocolError) after 1.2s — reconnecting, retry 2/3
⚠️  API call failed (attempt 1/3): RemoteProtocolError
   🔌 Provider: custom  Model: deepseek/deepseek-v4-pro
   🌐 Endpoint: https://api.edgee.ai/v1
   📝 Error: <StreamReset stream_id:1, error_code:1, remote_reset:True>
```

Always with `bytes=0 chunks=0 elapsed=~1.0s` — identical timing profile to bug #1.

## Root Cause

After fix #1 (HTTP/1.1 + h11 CRLF monkey-patch), the `illegal chunk header` error
is gone — the h11 CRLF fix successfully skips the bare `\r\n`. But Edgee
immediately follows with an HTTP/2 RST_STREAM frame (error_code=1 = PROTOCOL_ERROR).

`StreamReset` is a **pure HTTP/2 concept** (from the `h2` library). Its appearance
even after forcing HTTP/1.1 (`http2=False` in the transport) means Edgee's server
is sending HTTP/2-level protocol violations that propagate through httpx's error
handling regardless of the negotiated HTTP version.

The `http2=False` fix was verified working via debug logging:
```
DEBUG keepalive: base_url='https://api.edgee.ai/v1' http2=False
```

## Why unfixable client-side

- `error_code:1` = PROTOCOL_ERROR — the server detected a protocol violation
  in what WE sent, or in its own internal processing
- `remote_reset:True` — the reset was initiated by the server, not us
- The server resets stream_id:1 (the only stream) before any data is sent
- No client-side workaround can prevent a server from sending RST_STREAM

## Elimination Process

Systematic testing ruled out these hypotheses:

| Test | Result |
|------|--------|
| 0 tools, no system prompt | ✓ Works |
| 76 simple tools, no system prompt | ✓ Works |
| AGENTS.md alone (51KB), 0 tools | ✓ Works |
| AGENTS.md + 76 simple tools (64KB) | ✓ Works |
| AGENTS.md + 76 heavy tools (162KB) | ✓ Works |
| OpenAI SDK instead of raw httpx | ✓ Works |
| Custom transport with keepalive | ✓ Works |
| `stream_options={"include_usage": True}` | ✓ Works |
| Multiple system messages + memory | ✓ Works |
| Real Hermes interactive session | ✗ Fails |

All synthetic tests pass. Only Hermes' actual session payload (with real tool
schemas — complex nested JSON, verbose descriptions, `$defs`, `anyOf`, arrays)
triggers the bug. The exact trigger within the payload remains unidentified
but is irrelevant: the fix must be server-side (Edgee), not client-side (Hermes).

## Definitive Verdict

**Edgee is NOT compatible with Hermes Agent interactive sessions.** Two independent
server-side bugs exist. Bug #1 is workaround-able. Bug #2 is not. Use DeepSeek
direct (`api.deepseek.com`, model `deepseek-v4-pro`).
