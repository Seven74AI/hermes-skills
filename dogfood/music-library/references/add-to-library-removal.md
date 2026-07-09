# Add-to-Library Removal & Restoration

Commit `bfb8fde` (2025-11-28) removed add-to-library from YouTube services. Rationale was: "Since audio files cannot be downloaded from services." Since audio archiving was re-implemented (ADR-011), this is no longer valid.

## Deleted files

- `app/utils/service-import.server.ts` (233 lines) — `importTrackDirectly()`, `ServiceImportHandler`, registry
- `app/routes/music+/services+/youtube+/import.tsx` (360 lines) — standalone import page

## Removed from existing files

| File | What was removed |
|------|-----------------|
| `app/utils/service-playlist.server.ts` | `addTrackToUserLibrary()`, `removeTrackFromUserLibrary()`, `isInUserLibrary` computation in `getPlaylistTracksWithUserStatus()` |
| `app/types/youtube-intents.ts` | `ADD_TO_LIBRARY`, `REMOVE_FROM_LIBRARY` intents |
| `app/types/frontend/shared.ts` | `isInUserLibrary` from `TrackWithUserStatus` |
| `app/types/frontend/tracks.ts` | `isInUserLibrary` from type guard |
| `app/components/track-list-item.tsx` | 120 lines — library add/remove buttons, in-library status |
| `app/routes/music+/services+/youtube+/playlist.$id.tsx` | 79 lines — library actions in action handler |
| Various routes | Import links, in-library indicators |

## Old code issues

The removed code had three problems we're fixing on restoration:

1. **`ServiceAPIError` re-wrapped `YouTubeAPIError`** just to rename the class. Pointless.
2. **Handler defined its own return type** instead of using `VideoData` from `youtube-search.server.ts`, then hand-copied every field.
3. **Registry pattern** (`serviceHandlers: Record<string, ServiceImportHandler>`) over-abstracted for a single implementation. Dropping it.

## Restoration decisions (grill-with-docs, 2026-07-08)

Full decisions logged in `docs/CONTEXT.md` § Add-to-Library Restoration (decisions 17–29).

Key points:
- Both import paths restored: standalone page + inline buttons
- `importTrackDirectly` auto-enqueues (idempotent per `trackId`)
- `addTrackToUserLibrary` does NOT enqueue (track already enqueued during sync)
- Dedicated `resources+/track-library.tsx` route for toggle
- `itemActions` render prop on `TrackListItem` for inline buttons
- Bulk "Add All Missing" with confirmation dialog
- Deleted tracks (`isDeleted: true`) can still be added
- Import page stays after success for batch importing
- `publishedAt` from YouTube API surfaced as `releaseDate` (not null)
- ⚠️ Must remove `AUDIO_ARCHIVE_ENABLED` guard from `auto-enqueue.server.ts:25`
