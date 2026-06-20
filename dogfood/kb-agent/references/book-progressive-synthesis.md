# Book Progressive Synthesis — Design vs Drift

## CONTEXT.md Spec (lines 214-222)

```
For large content, the LLM builds the note progressively:
  chunk 1 → write partial note
  chunk 2 + previous note → append
  ...
  final polish call

Context stays clean: current chunk ~50K tokens + growing note ~20K tokens.

Chunk boundaries: A separate, cheap LLM call determines semantic boundaries
(not regex). Returns byte offsets. Fallback: no boundary at 50K → expand to
100K. 10K token overlap between chunks.
```

## Original Implementation (Phase 4C — drift)

The original implementation used:
- Regex chapter splitting (`=== CHAPTER N ===`)
- Group synthesis: 5 chapters → summarize → store
- Single final call receiving ALL summaries → compress everything into one note

Result: 38-chapter book (Hamlet's Mill, 1.2M chars) → 69 non-empty lines. One sentence per chapter.

## Fixed Implementation (2026-06-19)

Three-phase progressive synthesis:

1. **Boundary detection**: Chapter markers preferred (they ARE semantic boundaries).
   Group chapters into ~50K-token chunks with 10K token overlap.
   LLM boundary detection as fallback for books without chapter markers.

2. **Progressive calls**:
   - Call 1 (chunk 1): "Write Summary, Key Claims from these chapters, Chapter Summaries for chapters 1-N. STOP after Chapter Summaries."
   - Call 2-N (chunks 2+): "Here's the EXISTING note. Here are NEW chapters. APPEND to Key Claims and Chapter Summaries. Do NOT rewrite."
   - Final call: "This is the FINAL chunk. Append remaining chapters, then add Who Is the Author, Critical Analysis, Nuances, Reliability, Sources. Polish the Summary."

3. **No final combine pass** — the note grows organically across calls.

Key difference: each call sees the FULL growing note as context, so the note naturally
expands rather than compressing into a single output.
