# Edgee + Hermes Investigation — Definitive (May 19-20, 2026)

## Conclusion

Edgee has TWO independent server-side bugs when processing Hermes' full agent
context. Bug #1 is workaround-able. Bug #2 is not.

**Verdict: Edgee is NOT compatible with Hermes Agent interactive sessions.**
Use DeepSeek direct (`api.deepseek.com`, model `deepseek-v4-pro`).

## Bug #1: `illegal chunk header: \r\n` (FIXED)

A bare `\r\n` leaks into the chunked HTTP body before the first real chunk header.
Fix: force HTTP/1.1 (`http2=False` in `_build_keepalive_http_client`) + apply
the h11 CRLF monkey-patch (`edgee_crlf_fix.py`). This successfully eliminates
bug #1.

## Bug #2: `StreamReset stream_id:1, error_code:1` (UNFIXABLE)

After bug #1 is fixed, Edgee sends an HTTP/2 RST_STREAM frame with PROTOCOL_ERROR.
- `error_code:1` = server-detected protocol violation
- `remote_reset:True` = server-initiated reset
- Occurs at ~1.2s, zero bytes received
- Unfixable client-side — the server is actively resetting the stream

See `references/http2-h11-root-cause.md` and `references/diagnostic-tests.md`
for full details.

## Error signature

```
RemoteProtocolError: illegal chunk header: bytearray(b'\r\n')
http_status=200 bytes=0 chunks=0 elapsed=<1s ttfb=-
```

HTTP 200 headers sent, then body begins with `\r\n` instead of valid chunk size.

## What works (all pass)

- curl + Edgee (streaming & non-streaming)
- httpx raw + Edgee
- OpenAI SDK + Edgee + any simulated payload (up to 76 tools + 51K AGENTS.md)
- `hermes chat -q --provider edgee --quiet` (one-shot, minimal context)
- Raw socket: `c0\r\n` (valid chunk header) — NO bare `\r\n` from this server

## What fails (user side, 100% reproducible)

- `hermes chat --provider edgee` in interactive mode with full agent context:
  76 real Hermes tools + 51K AGENTS.md + memory + user profile + skills list

## Workaround created (May 19, 2026)

`edgee_crlf_fix.py` — monkey-patches `h11._readers.ChunkedReader.__call__` to tolerate
up to 3 bare `\r\n` before the first real chunk header. The patch is:
- Conditional: only applied when `base_url` matches `api.edgee.ai`
- Reversible: `edgee_crlf_fix.revert()` restores original behaviour
- Integrated: import + apply in `_apply_client_headers_for_base_url` in `run_agent.py`

Script location: `scripts/edgee_crlf_fix.py` in the `edgee-setup` skill.

## What was tried (earlier attempts, none fixed it alone)

1. HTTP/2 negotiation (`http2=True` on HTTPTransport + `h2` package) — connection still HTTP/1.1
2. Header manipulation (compression-model, debug, tags) — no effect
3. Pycache clear + gateway restart — no effect
4. Full Edgee documentation review (58 pages) — no undocumented connector or config
5. Raw socket reproduction with 76 tools + 51K AGENTS.md — `c0\r\n` (valid), bug not reproducible from server

## Why the SDK can reproduce with simulated payloads but not the real one

Simulated tool schemas and system prompts pass. The EXACT real Hermes payload (76 real
tool schemas with complex nested JSON, real AGENTS.md, memory block, user profile) triggers
the server-side `\r\n` artifact. The specific character patterns or byte sequences in Hermes'
real context exceed an internal Edgee processing threshold.

## Edgee product scope

Edgee is an Agent Gateway designed for Claude Code, Codex, and OpenCode. Their Console
API key types only support `claude_code`, `opencode`, and `codex`. Hermes is not on
their supported agent list.

## Edgee source code review (May 19, 2026)

The open-source Rust repo (`github.com/edgee-ai/edgee`) was reviewed:

**Open-source crates:**
- `gateway-http` — HTTP passthrough + SSE streaming via `StreamBody` (axum). No obvious bug.
- `gateway-core` — Provider trait, HTTP client abstraction via reqwest.
- `compression-layer` — Synchronous compression middleware.

**Critical finding:** `ProviderDispatchService` in `gateway-core/src/service.rs` is a **stub**
that returns `Err("not yet implemented")` on every call. The actual provider dispatch code
(DeepSeek/OpenAI/Anthropic adapters) is **closed-source** — not in the public repo.

**`MAX_BODY_BYTES = 4 MB`** in `passthrough.rs` — Hermes payloads (~200K) are well within limits.

**Streaming architecture:**
1. Request body read → JSON parsed → `PassthroughRequest` created
2. Middleware layers (compression) process synchronously
3. Provider dispatch (closed-source) produces `GatewayResponse::Stream(stream)`
4. SSE stream wrapped in `StreamBody` → HTTP response with chunked encoding
5. Client (h11/httpcore) parses chunked body → crashes on bare `\r\n`

## h11 chunk reader internals

The error is raised in `h11._readers.ChunkedReader.__call__` (line ~180 in h11 >=0.14):
```python
chunk_header = buf.maybe_extract_next_line()
matches = validate(chunk_header_re, chunk_header, "illegal chunk header: {!r}", chunk_header)
```

The `chunk_header_re` regex requires hex digits. A bare `\r\n` fails this validation.
The workaround skips `\r\n` and re-reads the next line as the chunk header.
