# DB Performance Audit — Findings & Patterns

Captured from the 2026-07-14 full-spectrum audit at 10k-track scale.

## Prisma Batch Explosion (SQLite)

When a query returns many rows with nested relations (`include`/`select` with related models), Prisma batches relation resolution into separate queries with an **~700-row batch size** limit.

**Example:** `findMany` on 5000 `UserPlaylistTrack` rows with `select: { track: { select: { artist, coverImage, service, audioFiles } } }` produces:
- 8 batches for `Track` (5000/700)
- 8 batches for `Artist`
- 8 batches for `CoverImage`  
- 8 batches for `Service`
- 8 batches for `TrackAudioFile`
- **Total: ~40 queries** for one logical operation

**Symptoms at scale:**
| Scenario | Rows | Queries | Duration |
|---|---|---|---|
| Queue spine (library, all tracks) | 10,000 | 23 | 1,030ms |
| Playlist detail | 5,000 × 4 relations | 32 | 405ms |
| ServicePlaylist tracks | 5,000 × 2 relations | 19 | 467ms |

**Mitigations:**
- Add `take` limits on high-cardinality queries (spine: 2k, library: 50/page)
- Narrow `select` to only the fields actually used (eliminate `service: true` → 8→3 fields)
- For large relations that must load fully, consider raw SQL or lazy loading
- `IN (NULL)` wasted queries: when the main query returns 0 rows, Prisma still issues `WHERE IN (NULL)` for each relation — harmless but wasteful

## Over-Fetching Patterns

### `include: { relation: true }` → `include: { relation: { select: { ... } } }`

Always check what fields the UI/component types actually use. Common offenders:
- `service: true` fetches 8 fields; UI uses 3 (name, displayName, logoUrl)
- `audioFiles: true` fetches 14 fields; UI uses 3 (id, format, objectKey)

**Audit command:**
```bash
grep -rn 'prisma\.' app/ --include='*.ts' --include='*.tsx' | grep -v '\.test\.'
```

### N+1 Detection

Look for `findMany` with no `where` filter that returns all rows, then used as a lookup Set. Example:
```typescript
// BAD: fetches ALL userTracks (10k rows) per playlist page load
const allTracks = await prisma.userTrack.findMany({ where: { userId, isActive: true } })
const set = new Set(allTracks.map(t => t.trackId))

// GOOD: scoped to playlist's trackIds
const ids = playlist.tracks.map(t => t.track.id)
const matches = await prisma.userTrack.findMany({ where: { userId, isActive: true, trackId: { in: ids } } })
```

## Profiling Workflow

1. **Static audit first** — grep all `prisma.` calls, catalog `include`/`select`, check for N+1 patterns
2. **Seed large dataset** — write a dedicated seed script (not the test seed) with realistic volumes
3. **Profile against real data** — use standalone `PrismaClient` with `log: [{ level: 'query', emit: 'event' }]`
4. **Verify data exists before profiling** — check `count()` for each table before measuring
5. **Compare before/after** — include in PR description

## Micro-Benchmarking Write vs Read (SQLite)

When verifying that replacing an `upsert` with a `findUnique`/`create` pattern actually saves time, create a temp table and measure raw `$executeRawUnsafe` loops:

```bash
cd /tmp/music-library
sqlite3 data.db "CREATE TABLE IF NOT EXISTS test_state (id TEXT PRIMARY KEY, val TEXT)"
sqlite3 data.db "INSERT OR IGNORE INTO test_state(id,val) VALUES('s','x')"

npx tsx -e "
import { PrismaClient } from '#prisma/client.js'
import { PrismaBetterSqlite3 } from '@prisma/adapter-better-sqlite3'

const p = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: 'file:data.db' }) })
await p.\$connect()

const N = 5000
const t1 = performance.now()
for (let i = 0; i < N; i++) {
  await p.\$executeRawUnsafe('INSERT INTO test_state(id,val) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET val=val', 'su'+(i%10), 'x')
}
const up = performance.now() - t1

const t2 = performance.now()
for (let i = 0; i < N; i++) {
  await p.\$executeRawUnsafe('SELECT 1 FROM test_state WHERE id=?', 'su'+(i%10))
}
const fi = performance.now() - t2

// cleanup
await p.\$executeRawUnsafe('DROP TABLE test_state')
console.log('upsert avg:', (up/N).toFixed(4), 'ms  select avg:', (fi/N).toFixed(4), 'ms  =>', ((1-fi/up)*100).toFixed(0), '%')
await p.\$disconnect()
"
```

**Result (2026-07-14):** upsert ~1.4ms, select ~0.3ms → **80% improvement** on SQLite. The write lock on `upsert` (even with empty `update: {}`) costs ~5× more than a pure read. This validated the `getWorkerState()` change from `upsert` → `findUnique` + `create` fallback.

## Verified Index Coverage

All hot query paths on the existing schema have appropriate indexes. No missing indexes found at audit time.
