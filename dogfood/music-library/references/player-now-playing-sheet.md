# PlayerNowPlayingSheet — Mobile Architecture

The mobile expanded now-playing view is a full-screen bottom sheet in `app/routes/audio-player.tsx`.

## Layout: Three-Tier Actions

### Transport Row (previous / play / next + queue)
The transport controls row has the queue button on the right side, using a `flex-1` spacer layout to keep the play/pause button centered while the queue icon sits flush-right.

### Bottom Action Row (5 buttons, always visible)
| Button | Behavior |
|--------|----------|
| Loop | 3-state cycle: off → all → one |
| Shuffle | Toggle, highlights when active |
| Add to Playlist | Opens a bottom **Sheet** containing `AddToPlaylistMenu` (was Popover dropdown). Self-fetches playlists on mount. Sheet auto-closes via `onSuccess` callback. |
| Sleep Timer | Timer to auto-stop playback |
| … (overflow) | Opens secondary sheet |

### Overflow Sheet (opened by …)
Order is intentional — queue actions first, info/download last:
| # | Button | Behavior |
|---|--------|----------|
| 1 | Play Next | Insert at front of Up Next |
| 2 | Add to Up Next | Append to end of Up Next |
| 3 | Add to Queue | Append after spine |
| 4 | Track Details | Opens `TrackDetailsDialog` |
| 5 | Download | Triggers `/resources/audio/:trackId?stream=1` download |

## Components & Routes

### `AddToPlaylistMenu` (`app/components/add-to-playlist-menu.tsx`)
- `playlists` prop is **optional** — when omitted, self-fetches from `GET /resources/playlists` on mount via `useFetcher`
- Inline create: `POST /resources/create-playlist-with-track`
- Add to existing: `POST /resources/add-track-to-playlist`
- This keeps the player component tree lightweight — no playlist data passed through

### `GET /resources/playlists` (`app/routes/resources.playlists.tsx`)
- Auth required (`requireUserId`)
- Returns `{ playlists: [{ id, title }] }`
- Empty array when user has no playlists

### `TrackDetailsDialog` (`app/components/track-details-dialog.tsx`)
- Fetches data on **open** (not on mount) via `useFetcher` → `GET /resources/track-details?trackId=...`
- Shows: title, artist, album, genre, duration, cover, service name, service URL, added date
- `FullTrack` data model is **not enriched** — dialog fetches its own data

### `GET /resources/track-details` (`app/routes/resources.track-details.tsx`)
- Auth required. Query param: `?trackId=...`
- Returns 200 with track metadata, 400 if missing `trackId`, 404 if not found
- Prisma query includes: `title, artist, album, genre, duration, coverImage, service, serviceUrl, createdAt`

## Desktop Bar

The desktop audio player bar is **unchanged** by the mobile sheet. Desktop continues to use `TrackListItem` dropdown menus for playlist and queue actions. The bottom action row on desktop has the pre-existing layout (Queue, Loop, Shuffle, Download, Close).

## Docs

- `docs/AUDIO_PLAYER_AND_QUEUE.md` — the `PlayerNowPlayingSheet UI (Mobile)` section documents the layout
- `docs/CONTEXT.md` — decisions #58, #59, #60 capture the architectural decisions
