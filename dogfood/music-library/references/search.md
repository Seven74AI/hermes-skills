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

**Auto-focus:** The search input auto-focuses on every navigation to `/search`. The `useEffect` depends on `location.pathname` (not `[]`) so it refires when navigating back from another page. The bottom nav Search button uses `navigate("/search")` + `setTimeout(() => focus(), 0)` as a fallback for when already on `/search` (pathname unchanged, effect doesn't fire).

## Result Display

`app/components/search-results.tsx` — mixed feed of all entity types sorted by relevance (server-side sort in `searchAll`). No grouped-by-type sections; a single unified list.

**Horizontal card layout:**

```
┌──────────┬──────────────────┐
│  icon    │ Entity Title     │
│  (12×12) │ Type — subtitle  │
└──────────┴──────────────────┘
```

| Entity | Title field | Subtitle format | Icon |
|---|---|---|---|
| Track | `result.title` | `Track — Artist Name` | `play` |
| Album | `result.name` | `Album — Artist · Year` | `camera` |
| Artist | `result.name` | `Artist · Genre` (or just `Artist`) | `avatar` |
| Playlist | `result.name` | `Playlist — N tracks` | `list-bullet` |

Image placeholder: 12×12 rounded `bg-muted` div with type-specific icon. Playlists use `thumbnailUrl` if available. Cover images use `coverImageId` (objectKey not available in search results — the search SQL would need to JOIN `CoverImage` to return it).

**Helper functions:** `getResultLink`, `getTypeLabel`, `getResultSubtitle`, `ResultImage` — extracted to keep the JSX clean.

**Load More:** identical to before — `hasNext` + `onLoadMore` button at the bottom.

## Bottom Nav

`app/components/bottom-nav.tsx` — fixed bottom nav on mobile (`md:hidden`). Tabs: Home, Search, My Library, My Playlists. Uses `z-[51]`.

### Mobile z-index hierarchy

| Component | z-index | Position |
|---|---|---|
| Toast viewport | z-[100] | Top (mobile) / bottom-right (desktop) |
| Search overlay | z-[80] | Full-screen inset-0 (100dvh) |
| EpicProgress (loading bar) | z-50 | Top |
| Bottom nav | z-[51] | Bottom (mobile only) |
| Audio player | z-50 | Bottom (bottom-16 on mobile, bottom-0 on desktop) |
| Install app banner | z-30 | Bottom (above playerVisible ? 4.5rem : 0) |

Search overlay at z-[80] sits above both bottom nav and audio player — users use the back arrow to exit search.
Bottom nav at z-[51] sits 1 above the audio player (z-50).
Install banner at z-30 sits below both bottom nav and audio player; tests dismiss it with `{ force: true }` clicks when covered.

### Content height

Bottom nav is 4rem (`h-16`). The main content area must not extend behind it:

- `app/root.tsx`: main-content div uses `flex flex-1 flex-col pb-16 md:pb-0` — no `overflow-y-auto` (nested scroll containers cause pointer event interception)
- Footer also gets `pb-24 md:pb-8` to clear the bottom nav on mobile
- Audio player uses `bottom-16 md:bottom-0` to sit above the bottom nav

## Artist & Album Pages

Search results link to dedicated pages (not `/library` query params):

| Entity | Route | File |
|---|---|---|
| Track | `/library/:trackId` | `app/routes/library.$trackId.tsx` |
| Album | `/albums/:albumId` | `app/routes/albums.$albumId.tsx` |
| Artist | `/artists/:artistId` | `app/routes/artists.$artistId.tsx` |
| Playlist | `/playlists/:playlistId` | `app/routes/playlists.$playlistId.tsx` |

Artist page: header (name, genre, bio, image), albums grid, tracks list. Album page: header (name, artist link, year, cover), track listing with numbers.

## Deleted Dead Code

`validateSearchQuery`, `validateSearchLimit`, `validateSearchType`, `validateCursor` — thin Zod `.parse()` wrappers, never called in production. Schemas used directly via `.safeParse()`.

## FTS5 Admin Page

`app/routes/admin+/fts-index.tsx` — `/admin/fts-index` (admin-only, in user dropdown).

Shows FTS5 row counts vs entity row counts per type with health badges:
- **Healthy**: FTS rows ≥ entity rows and entity count > 0
- **Stale**: FTS rows < entity rows  
- **Empty**: entity count = 0

**Rebuild command** (runs via `prisma.$executeRawUnsafe`):

```sql
INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild');
INSERT INTO albums_fts(albums_fts) VALUES('rebuild');
INSERT INTO artists_fts(artists_fts) VALUES('rebuild');
```

Per-entity button + Rebuild All. Use `useNavigation().formData` to detect which entity is being rebuilt for per-button loading states.
