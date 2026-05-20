# Edgee Diagnostic Tests — Systematic Isolation (2026-05-19)

Methodology for isolating server-side provider bugs by testing payload
components independently.

## Test Matrix

All tests use `httpx.Client(transport=HTTPTransport(http2=False))` with
the OpenAI SDK, keepalive socket options, AGENTS.md (51KB system prompt),
and 76 tools.

| # | System Prompt | Tools | Payload | Result |
|---|--------------|-------|---------|--------|
| 1 | None | 0 | ~1KB | ✓ HTTP/1.1 200, 7 chunks, 3s |
| 2 | None | 76 simple | 12KB | ✓ HTTP/1.1 200, 13 chunks, 3.3s |
| 3 | AGENTS.md 51KB | 0 | 53KB | ✓ HTTP/1.1 200, 10 chunks, 4.2s |
| 4 | AGENTS.md 51KB | 76 simple | 64KB | ✓ HTTP/1.1 200, 13 chunks, 3.3s |
| 5 | AGENTS.md 51KB | 76 heavy (~1KB/ea) | 162KB | ✓ HTTP/1.1 200, 11 chunks, 5.4s |
| 6 | + OpenAI SDK | 76 simple | 64KB | ✓ OK, 11 chunks, 3.8s |
| 7 | + Custom transport (keepalive) | 76 simple | 64KB | ✓ OK, 12 chunks, 4.1s |
| 8 | + stream_options include_usage | 76 simple | 64KB | ✓ OK, 13 chunks, 3.0s |
| 9 | + Multiple system messages | 76 simple | 64KB | ✓ OK, 212 chunks, 19s |

**Conclusion:** No synthetic payload reproduces the bug. The real Hermes
session (76 real tools with complex nested schemas + AGENTS.md + memory
+ user profile) is the only trigger. The exact trigger element within the
full Hermes context is still unidentified.

## Two Distinct Bugs

**Bug #1** — `RemoteProtocolError: illegal chunk header: bytearray(b'\r\n')`
- Edgee responds HTTP 200, then sends bare `\r\n` before first chunk header
- bytes=0, chunks=0, elapsed <1s
- Fix: HTTP/1.1 + h11 CRLF monkey-patch (edgee_crlf_fix.py + http2=False)

**Bug #2** — `StreamReset stream_id:1, error_code:1, remote_reset:True`
- Edgee sends HTTP/2 RST_STREAM with PROTOCOL_ERROR
- Surfaces only AFTER bug #1 is fixed
- Elapsed ~1.2s
- Unfixable client-side

## Key Insight

The h11 CRLF fix was originally applied without forcing HTTP/1.1. Hermes
uses `http2=True` by default, so h2 handles framing and h11's ChunkedReader
is never invoked. The fix was a no-op until we conditionally set `http2=False`
for Edgee in `_build_keepalive_http_client` (run_agent.py:2413).

## Provider Display

Hermes shows `Provider: custom` for Edgee — this is normal. Edgee is
resolved as a `custom_providers` entry. The label is cosmetic and doesn't
affect API calls.

## Next Steps (if debugging continues)

To find the exact trigger for bug #2:
1. Capture the real Hermes request body with `HTTPX_LOG_LEVEL=TRACE`
2. Compare against synthetic tests
3. Identify the specific payload element (tool schema complexity,
   message count, header, parameter) that triggers the StreamReset
