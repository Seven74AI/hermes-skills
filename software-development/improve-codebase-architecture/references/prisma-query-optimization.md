# Prisma Query Optimization

Pitfalls, patterns, and measurement discipline for optimizing Prisma queries. Companion to `prisma-types-in-interfaces.md` (which covers type-level correctness).

## Pitfalls

### Test mocks break when Prisma method surface changes

When you optimize a query by changing the Prisma method (e.g., `findMany` → `findFirst`, `upsert` → `findUnique`, `count` → `groupBy`), the corresponding vitest mocks break silently. The mock object in `vi.mock('#app/utils/db.server.ts')` references the old method name, and vitest won't warn you — it just throws `TypeError: prisma.X.Y is not a function`.

**Checklist after every query optimization:**

- [ ] Grep for the old method name in `*.test.*` files: `rg "\.findMany\b" --glob '*test*'`
- [ ] If any test mocks the old method, add the new method to the mock and update test expectations
- [ ] Run the specific test file BEFORE running the full suite (saves 3 minutes of waiting)

**Common replacements and their mock updates:**

| Source change | Test mock change | Test expectation change |
|---|---|---|
| `findMany({ where, take: N })` → `findFirst({ where, select })` | Add `findFirst: vi.fn()` to mock | Return shape: `null` or `{ id }` instead of `[]` or `[{...}]` |
| `upsert({ where, update, create })` → `findUnique({ where })` + `create({ data })` | Add `findUnique: vi.fn()` + `create: vi.fn()` | Two-phase state: return `null` when not created, return state when created |
| 4× `count({ where: { status: X } })` → `groupBy({ by: ['status'], _count: { _all: true } })` | Add `groupBy: vi.fn()` | Return `[{ status, _count: { _all: N } }]` |

**Example — upsert → findUnique + create:**

```typescript
// Mock setup (add these alongside existing upsert mock):
findUnique: vi.fn().mockImplementation(async () => {
  return _mockCreated ? getState() : null
}),
create: vi.fn().mockImplementation(async (args) => {
  _mockStatus = args.data.status ?? 'running'
  _mockCreated = true
  return getState()
}),
```

### Empty mock doesn't fail — it throws at runtime

If a mock object doesn't have a method that the source code calls, `vi.mock` still succeeds. The error only surfaces when vitest executes the test and the real code tries `prisma.X.Y()`. This means typecheck won't catch it either — you must run the tests.

### Semantic drift: findFirst null vs findMany empty array

When replacing `findMany` with `findFirst` in a "check if any X exists" pattern, the semantics can drift for edge cases:
- `findMany` returning `[]` was treated as "no results" → the old code might have returned `false`
- `findFirst` returning `null` means "no match" → new code returns `true` (the inverse)

Always verify edge-case semantics against the test expectations. The test may need its expected value updated AND its test name changed to reflect the new behavior.

## Measurement discipline

### Every fix needs a real before/after number

When creating a PR documenting performance improvements:

- [ ] Every row in the before/after table has a **measured percentage**, not "—" or N/A
- [ ] Percentages come from real profiling against realistic seed data, not estimates
- [ ] For fixes that don't change query time but reduce data transfer (e.g., field scoping), note it explicitly: "N/A (same query time, ~79% less data transferred)"
- [ ] For fixes that eliminate operations entirely (e.g., DB writes → in-memory), the percentage is **100%**
- [ ] For conditional fixes (e.g., gated on mode), state the condition: "100% in non-listening mode, same in listening mode"

### Profiling setup

For realistic measurements:
1. Seed the database at scale (10k+ rows in the target tables)
2. Use `prisma.$on('query', ...)` with `logThreshold: 0` to capture all query timings
3. Run each operation in isolation, warm the cache first
4. Measure at least 3 runs and take the median
5. Restore the normal `logThreshold` after profiling

## Query optimization patterns

### findMany paginated scan → findFirst with filter

When checking "does any record in this set satisfy condition X", and the answer is boolean:

```typescript
// BEFORE: paginated scan (N queries for 100 pages)
while (true) {
  const page = await prisma.x.findMany({ where: { ... }, take: 100, skip })
  if (page.length === 0) return result
  if (page.some(predicate)) return false
  skip += 100
}

// AFTER: single findFirst with Prisma filter
const match = await prisma.x.findFirst({
  where: { ...predicate... },
  select: { id: true },
})
return match === null  // null = no match = condition passed
```

### count × N → groupBy

```typescript
// BEFORE: N queries
const pending = await prisma.job.count({ where: { status: 'pending' } })
const processing = await prisma.job.count({ where: { status: 'processing' } })
// ...

// AFTER: 1 query
const groups = await prisma.job.groupBy({
  by: ['status'],
  _count: { _all: true },
})
```

### upsert-as-read → findUnique + create

When `upsert` is called with `update: {}` (no-op update), it's being used as a "find-or-create" read pattern. This causes an unnecessary write lock on SQLite:

```typescript
// BEFORE: write lock on every read
const state = await prisma.state.upsert({
  where: { id: 'singleton' },
  update: {},
  create: { id: 'singleton', status: 'running' },
})

// AFTER: pure read, fallback create
const existing = await prisma.state.findUnique({ where: { id: 'singleton' } })
if (existing) return existing
const state = await prisma.state.create({ data: { id: 'singleton', status: 'running' } })
```

### DB writes → in-memory tracking

For transient state that doesn't need to survive restarts (e.g., worker `currentlyProcessing`), replace DB upserts with module-level `Map`/`Set`:

```typescript
// BEFORE: 2 DB writes per job
await prisma.state.upsert({ where: { id }, update: { currentlyProcessing }, create: { ... } })
// ... process job ...
await prisma.state.upsert({ where: { id }, update: { currentlyProcessing: null }, create: { ... } })

// AFTER: 0 DB writes
const currentlyProcessing = new Set<string>()
currentlyProcessing.add(trackId)
// ... process job ...
currentlyProcessing.delete(trackId)
```

Export the set for admin UI access.
