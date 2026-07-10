# Audio Player — Service Playlist API Mismatch (next/auto-advance)

## Symptom
On the YouTube playlist page (`playlist.$id.tsx`), next button and auto-advance
silently break. The player works for the first track but cannot advance to the next.

## Root Cause
`AudioPlayerProvider.fetchAllTracks` and `loadFullTrackData` only handle two
context types, but use the wrong API for service (YouTube) playlists.

### Context → API mapping (broken)

| `playContext.type` | API called | Queries | Correct for |
|---|---|---|---|
| `'library'` | `/api/user-tracks` | `UserTrack` | ✅ Library page |
| `'playlist'` | `/api/playlist-tracks` | `UserPlaylistTrack` | ✅ User-created playlists |
| `'playlist'` (from YouTube page) | `/api/playlist-tracks` | `UserPlaylistTrack` ❌ | ❌ Should query `ServicePlaylistTrack` |

The YouTube playlist page (`playlist.$id.tsx:659`) passes:
```tsx
playlistContext={{ type: 'playlist', playlistId: playlist.id }}
```

Where `playlist` is a `ServicePlaylist`, but `fetchAllTracks` unconditionally
calls `/api/playlist-tracks?playlistId=...` which queries `UserPlaylistTrack`
— wrong table, wrong data. Returns empty.

The correct endpoint for service playlists is `/api/service-playlist-tracks`,
which queries `ServicePlaylistTrack` and always includes `audioFiles`.

## Two APIs, same shape

| API | Queries | audioFiles |
|---|---|---|
| `/api/playlist-tracks` | `UserPlaylistTrack` | Only with `fields=full` |
| `/api/service-playlist-tracks` | `ServicePlaylistTrack` | Always included |

Both return `{ tracks: [...], pagination: { hasNext, nextCursor, limit } }`.

## Fix options

**A) New context type:** Introduce `'service-playlist'` alongside `'playlist'`.
YouTube page passes `{ type: 'service-playlist', playlistId }`.
Provider branches to `/api/service-playlist-tracks`.

**B) Add `playlistType` field:** Keep `type: 'playlist'`, add
`playlistType: 'user' | 'service'`. Provider branches internally.

Option A is cleaner — two distinct context types, zero ambiguity.

## Files to change

- `app/components/audio-player-provider.tsx`:
  - `PlayContext` type: add `'service-playlist'`
  - `fetchAllTracks`: branch on `'service-playlist'` → `/api/service-playlist-tracks`
  - `loadFullTrackData`: same branch
- `app/routes/music+/services+/youtube+/playlist.$id.tsx`:
  - Change `playlistContext={{ type: 'playlist', ... }}` to `{ type: 'service-playlist', ... }`
- `app/components/track-list-item.tsx`:
  - `PlaylistContext` prop type: add `'service-playlist'` to the union
