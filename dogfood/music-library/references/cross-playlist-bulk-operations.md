# Cross-Playlist Bulk Operations

New resource routes on the synced playlists list page (`synced-playlists.tsx`).

## Routes

### `POST /resources/add-all-service-tracks-to-library`

Adds all active (non-deleted) tracks from **all** synced service playlists to the user's library in one operation.

- Queries all `ServicePlaylistTrack` where `isDeleted: false` across all user's synced playlists
- Diffs against existing active `UserTrack` records — only adds missing
- Reuses `addTracksToUserLibrary()` from `app/features/user-library/user-library.server.ts`
- Returns `{ addedCount, totalTracks }`

### `POST /resources/service-playlist-to-user-playlist`

Converts one service playlist's tracks into a user playlist.

**Body params:**
- `playlistId` — service playlist ID
- `action` — `"create"` | `"add"`
- `title` — (for create) new playlist title
- `targetPlaylistId` — (for add) target user playlist ID

**Create flow:** validates ownership, checks for duplicate title via `userPlaylistTitleTaken()`, creates `UserPlaylist` + bulk `UserPlaylistTrack.createMany()` in a transaction.

**Add flow:** validates ownership of both playlists, queries existing `UserPlaylistTrack` in target, filters out dupes (silent skip), appends new tracks with correct positions. Returns `{ addedCount, skippedCount }`.

## Loader Counts

The `synced-playlists.tsx` loader was enhanced to include `totalTracks` and `missingTracks` counts for the confirmation dialog. The query pattern:

```ts
// 1. All active track IDs across synced playlists
const playlistTracks = await prisma.servicePlaylistTrack.findMany({
  where: { playlistId: { in: playlistIds }, isDeleted: false },
  select: { trackId: true },
})

// 2. Library track IDs
const libraryTrackIds = await prisma.userTrack.findMany({
  where: { userId, trackId: { in: uniqueTrackIds }, isActive: true },
  select: { trackId: true },
})

// 3. Diff for missing count
const librarySet = new Set(libraryTrackIds.map(ut => ut.trackId))
missingTracks = uniqueTrackIds.filter(id => !librarySet.has(id)).length
```

## Frontend Component

`ConvertPlaylistDialog` (`app/components/convert-playlist-dialog.tsx`) — per-card overflow "…" button with two modes:

- **Create New** — pre-filled title input (defaults to service playlist title), inline validation for duplicate titles
- **Add to Existing** — fetches `/resources/playlists`, searchable picker, submits on click

Uses `Dialog` (not `AlertDialog`) for the multi-step flow. Reuses the search + filter pattern from `AddToPlaylistMenu`.

## Design Decisions

- **All server-side** — no track data sent to client beyond counts
- **Deleted tracks excluded** — `isDeleted: false` filter on all `ServicePlaylistTrack` queries
- **Silent duplicate skip** when adding to existing playlist — toast reports counts
- **No per-card "Add All Missing"** — the per-playlist "Add All Missing" lives on `playlist.$id.tsx` (playlist detail page)
