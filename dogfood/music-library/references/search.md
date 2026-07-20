# Search — Architecture & Current State

## FTS5 Engine

`app/utils/search.server.ts` — FTS5 with unicode61 tokenizer. Keyset cursor pagination on all 4 entities.

**Indexed entities (4):**

| Entity    | FTS Table        | Indexed Columns                                  | Extra                          |
|-----------|------------------|--------------------------------------------------|--------------------------------|
| Track     | `tracks_fts`     | title, artist_name, album_name                   | Triggers on INSERT/UPDATE/DELETE |
| Album     | `albums_fts`     | name, artist_name                                | Triggers on INSERT/UPDATE/DELETE |
| Artist    | `artists_fts`    | name, genre                                      | Triggers on INSERT/UPDATE/DELETE |
| Playlist  | none (LIKE)      | name                                             | Plain SQL LIKE, scoped to user  |

**Artist rename cascade:** Migration trigger on Artist UPDATE cascades to `tracks_fts` and `albums_fts`.

**Library scoping:** Search functions accept `userId` and JOIN `UserTrack`.

**Prefix matching:** `met` matches `metal`, `metallic`.

**Ranking:** Exact match → prefix match → FTS rank.

**Validation:** Zod schemas, max 200 chars, 20 words, alphanumeric required.

## Cursor Pagination

Keyset pagination across all 4 entities. Composite cursor format (base64 JSON):

```json
{"t":{"rk":1,"fr":5,"n":"Song X","id":"abc"},"a":null,"ar":null,"p":null}
```

Each key (`t`/`a`/`ar`/`p`) holds a sort-tuple `{rk, fr, n, id}` encoding the last-seen position for that type. `searchAll` combines per-function cursors into the composite. Individual functions build a WHERE clause:

```sql
AND (
  relevance_rank > rk OR
  (relevance_rank = rk AND fts_rank > fr) OR
  (relevance_rank = rk AND fts_rank = fr AND name > n) OR
  (relevance_rank = rk AND fts_rank = fr AND name = n AND id > id)
)
```

**Playlist exception:** Playlists use LIKE not FTS5. The cursor passes `fts_rank = 0` with `ftsCol = '0'` in the clause — `0 = 0` is true, `0 > 0` is false, so the second branch collapses and the third/fourth branches handle name/id comparison after matching relevance_rank.

**BigInt trap:** SQLite FTS5 returns `fts_rank` as BigInt. `JSON.stringify` can't serialize BigInt, causing `encodeCursor` to throw. Fix: `Number()` cast in `lastCursorTuple` before constructing the cursor.

**Pitfall:** The `cursor` parameter must flow through the composite chain: `searchAll` → decode → per-function cursor → individual function's WHERE clause. Calling a function directly (not via `searchAll`) requires the caller to pass the right per-type cursor field — passing a raw composite cursor to a single function will decode `cur.t` (or `cur.a` etc.) correctly since each function extracts its own field.

## API Route

`app/routes/api+/search.tsx` — validates via Zod, gets `userId`, calls `searchWithCache`.

## Caching

`app/utils/search-cache.server.ts` — wraps `searchAll` with 5-min TTL via cachified. Cache key:

```
search:${type}:${userId || "public"}:${query}:${limit}:${cursor}:${usePrefix}
```

**Pitfall:** API route must call `searchWithCache`, not `searchAll` directly. Calling `searchAll` directly bypasses the cache entirely.

## Search Page

`app/routes/search.tsx` — full-screen overlay with cancel button, type filter pills, debounced results (400ms), recent searches in localStorage (max 8).

**Load More accumulation:** Results accumulate across pages. Implementation: `useRef` flag (`isLoadMore`) set to `true` before Load More fetch; `useEffect` watching `fetcher.data` appends or replaces based on the flag. Accumulation resets on new search or type change.

## Result Display

`app/components/search-results.tsx` — grouped sections by type with distinct icons:
Tracks: `play` | Albums: `camera` | Artists: `avatar` | Playlists: `list-bullet`

## Bottom Nav

Persistent bottom nav bar on mobile (`md:hidden`) — Home, Search, Library, Profile.

## Deleted Dead Code

`validateSearchQuery`, `validateSearchLimit`, `validateSearchType`, `validateCursor` — thin Zod `.parse()` wrappers, never called in production. Schemas used directly via `.safeParse()`.

## Unified feed

The remote has a unified mixed-feed `search-results.tsx` (from PRD #212) with `getTypeLabel`/`getResultLink`/`formatDuration`. The local version uses grouped-sections layout. The unified feed hasn't been merged locally yet — resolve conflicts before adopting.
