---
name: db-performance-audit
description: "Full-spectrum database performance audit: grill scope → static code inventory → large seed → live profiling → quantified before/after PR. Use when user wants to audit DB calls, find N+1s, over-fetching, missing indexes, query counts, dead queries, or inefficient Prisma patterns across a codebase."
version: 1.0.0
metadata:
  hermes:
    tags: [db-performance, engineering]
---

# DB Performance Audit

A discipline for auditing database call performance across an entire codebase. Moves from scoping questions through static inventory to live profiling, ending with a quantified before/after comparison.

## When to use

- User says "audit DB performance," "profile DB calls," "find N+1s," "find slow queries"
- User wants to know where the hot paths are in a Prisma/ORM-backed app
- User wants before/after measurements for a set of optimizations

This is NOT a single-query debugging tool — for that, use `diagnose`. This is a codebase-wide survey.

## Phase 1 — Grill the scope

Before touching code, nail down:

1. **Dimensions**: N+1 detection, over-fetching (unused includes/fields), missing indexes, query count per route, dead queries, inefficient patterns (upsert-when-read, COUNT-in-loop)
2. **Tiers**: route loaders, route actions, services, background workers, admin routes
3. **Method**: static code audit only, or static + runtime profiling
4. **Output**: report only, immediate fixes, GitHub issues, or a PR with before/after

The user may answer "all" to multiple questions — that's an explicit choice, not ambiguity.

## Phase 2 — Static code audit

Inventory every Prisma call in the codebase. Use `search_files` with pattern `prisma\.` across all `.ts`/`.tsx` files under `app/`.

For each call site, note:
- What model is queried
- What `include` / `select` is used (or absent = default all fields)
- Whether it's in a loader (per-request), action (per-mutation), or worker (per-tick)
- Whether it's in a loop (N+1 candidate)
- Whether it queries fields that are never read downstream

Output: a flat inventory. Do NOT present findings until every file is read — the "verify before asserting" rule from `diagnose` applies here too.

### N+1 detection

Search for Prisma calls inside `.map()`, `for...of`, or `Promise.all()` blocks. An N+1 is when a query fires per-item in a collection instead of batching with `where: { id: { in: ids } }`.

### Over-fetching detection

For each `include` or default (no select), trace the returned data to the UI. Fields in the Prisma response that never appear in JSX are candidates for `select` scoping.

## Phase 3 — Large seed data

Runtime profiling needs realistic data volume. Create a seed script (`prisma/seed-large.ts`) with:

- 10k+ rows in the main table
- Matching volume in join tables
- Realistic distribution (some playlists with 5000 tracks, some with 5)

Use `faker` or simple loops. The seed must be re-runnable (`deleteMany` first).

## Phase 4 — Live profiling

Do NOT try to micro-benchmark inside vitest — SQLite copy semantics and test isolation make results unreliable.

Instead:

1. Lower the Prisma query log threshold to 0ms temporarily so every query is logged
2. Write a standalone profiling script (`scripts/profile-queries.ts`) that imports the app's route handlers and exercises them with known inputs
3. Or: hit the dev server with curl while watching query logs
4. Capture: query text, duration, call site (file + line)

Measure each hotspot 5-10 times and take the median. One-shot measurements are noise.

### Micro-benchmarking specific operations

When comparing upsert vs findUnique or other individual operations, use `$executeRawUnsafe` in a loop:

```ts
const N = 5000;
const t1 = performance.now();
for (let i = 0; i < N; i++) {
  await prisma.$executeRawUnsafe('INSERT INTO t(id,val) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET val=val', ...);
}
const beforeMs = performance.now() - t1;

const t2 = performance.now();
for (let i = 0; i < N; i++) {
  await prisma.$executeRawUnsafe('SELECT 1 FROM t WHERE id=?', ...);
}
const afterMs = performance.now() - t2;

console.log(`Improvement: ${((1 - afterMs / beforeMs) * 100).toFixed(0)}%`);
```

This avoids Prisma query-building overhead and measures raw SQLite.

## Phase 5 — Before/After PR

Present results as a PR with a markdown table. **Every row MUST have a quantitative improvement measure.** No "—" placeholders, no empty cells. The user will call out missing percentages.

### Table format

```
| Operation | Before | After | Improvement | What changed |
|---|---|---|---|---|
| **Queue spine library** | 297ms | 39ms | **87%** | `take: 2000` prevents full 10k fetch |
```

### Handling edge cases

- **Same latency, different data volume** (e.g., field scoping at small scale): note as "N/A (same query time, ~79% less data on the wire)" — the win is bandwidth, not latency. Still quantified.
- **Conditional improvements** (e.g., mode-gated queries): "100% in non-listening modes (3 queries saved)" — state the condition and the saving.
- **Eliminated operations** (e.g., DB writes removed entirely): "2 upserts/job → 0: 100%" — quantify what was eliminated.
- **Write-vs-read improvements** (e.g., upsert → findUnique): benchmark with the raw SQL method from Phase 4 and include the measured percentage.

### Commit strategy

Batch fixes into atomic commits by category:
- Commit 1: field scoping + N+1 fixes (read-side)
- Commit 2: worker write elimination + query consolidation (write-side)

Run typecheck after each commit. Push only when clean.

## Pitfalls

### Missing percentages in before/after tables

**CRITICAL**: Every row in the before/after table must have a number in the Improvement column. If a measurement seems marginal or N/A, dig deeper — measure the actual benefit (bandwidth saved, writes eliminated, queries skipped). The user will reject "—" placeholders. If you genuinely cannot produce a percentage, the row doesn't belong in the table.

### Vitest for DB profiling

Vitest copies the SQLite DB per-test-file and uses MSW for HTTP mocking. DB query timings from within vitest runs are NOT representative of production — different SQLite instance, different cache state, different connection pool. Use vitest only for correctness tests. Use live profiling against a seeded dev DB for timing measurements.

### Standalone scripting with Prisma imports

When writing profiling scripts, import PrismaClient the same way the app does (check `app/utils/db.server.ts` for the adapter and import path). For Prisma 7+ with `PrismaBetterSqlite3`, the adapter constructor takes `{ url: 'file:data.db' }`, not a raw `better-sqlite3` Database instance.

### Worker operations are per-job, not per-request

When auditing worker code, the unit of measurement shifts: a 2ms saving per job × 100 jobs/minute is significant even though it doesn't show up in any route's latency. Express worker improvements as per-job savings, not per-request.

### Large seed data persistence

Large seed scripts run `deleteMany` first so they're re-runnable, but the data persists after the script exits. Don't leave 10k+ rows in the dev DB without telling the user — it inflates the repo size. Offer to reset with `prisma/seed.ts` when done.

### `take` limits on lightweight queries break correctness

**Don't apply `take`/row limits without checking whether the query is actually heavy.** Before adding a limit, check the `select` — if it only fetches 3-4 columns (id, title, foreign-key name), even 5000 rows is <1MB and SQLite handles it trivially with an index.

Capping a lightweight query with `take: 2000` is a performance theater fix that introduces correctness regressions (e.g., shuffle only operates on the capped subset, invisible to the user). The real heavy queries — the ones loading full relations, blobs, or unindexed fields — are the ones that need limits.

**Diagnosis**: after profiling, check whether the query's select is already minimal. If yes, the fix is elsewhere (indexing, relation scoping, caching). If no, scope the select first, THEN evaluate whether a limit is still needed.

**Real case (music-library, 2026-07-14)**: Queue spine query loaded only `id, title, artist.name` (~150 bytes/row). Added `take: 2000` — broke shuffle for libraries with >2000 tracks, zero performance gain. Reverted. The real heavy queries were the playlist detail page (full relations) and `/api/tracks/playback` (cover images, audio URLs) — those were fixed via select scoping, batch size, and debounce.

### Stale test mocks after Prisma method changes

When the audit changes Prisma method calls, the corresponding vitest mocks **will** break — they still stub the old method name. Run `npx vitest run <affected-files>` after EVERY commit. The user will catch failures you missed.

Common breakage patterns:
- `findMany` → `findFirst` — mock needs `findFirst: vi.fn()`
- `upsert` → `findUnique` — mock needs `findUnique` + `create`
- 4× `count` → `groupBy` — mock needs `groupBy` returning `[{ status, _count: { _all: N } }]`

Also: dead interface fields survive. When you eliminate a DB write (e.g., `currentlyProcessing` moved to in-memory Set), the corresponding type field and `reshape()` still carry it — remove them too.
