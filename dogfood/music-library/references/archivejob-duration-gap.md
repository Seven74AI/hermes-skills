# ArchiveJob Duration Gap — Diagnostic Reference

## Symptom

`Track.duration` is `null` for ALL tracks imported from YouTube playlists (and any track where the ArchiveJob downloaded the audio). This causes:
- "View details" dialog shows `--:--` (from `formatDuration(null)`)
- Track list items show `--:--` for duration column
- Player bar shows `0:00` until `loadedmetadata` fires

## Root cause

`app/features/audio-archive/worker.server.ts:120-143` — the `processJob` function:

```typescript
// 1. Download via yt-dlp
const result = await executeYtDlp(url, { cookieFile })

// 2. Upload to Tigris
const key = buildObjectKey(trackId, result.filePath)
const uploadResult = await uploadToTigris(result.filePath, key)

// 3. Create TrackAudioFile record — HARDCODED values, NO metadata extraction
await prisma.trackAudioFile.create({
    data: {
        trackId,
        objectKey: uploadResult.key,
        fileName: uploadResult.key.split('/').pop(),
        format: 'mp3',           // ← hardcoded
        mimeType: 'audio/mpeg',  // ← hardcoded
    },
})

// 4. Mark job as completed — Track.duration NEVER updated
```

The downloaded file (`result.filePath`) contains full audio with embedded metadata (duration, bitrate, sample rate, format). This data is available on disk BEFORE uploading to Tigris. The worker never reads or extracts it.

## What's missing

1. **Read the audio file buffer**: `const buffer = readFileSync(result.filePath)`
2. **Extract metadata**: `const metadata = await extractAudioMetadata(buffer)`
3. **Update Track.duration**: `await prisma.track.update({ where: { id: trackId }, data: { duration: metadata.duration } })`
4. **Enrich TrackAudioFile**: Use real `format`, `mimeType`, `fileSize`, `bitrate`, `sampleRate` from metadata instead of hardcoded `'mp3'` / `'audio/mpeg'`

## Verification

```bash
# Check if any tracks in user's library have null duration
# (requires DB access — run on the Fly.io instance)
sqlite3 /data/data.db "SELECT COUNT(*) FROM Track WHERE duration IS NULL;"

# Check specific track
sqlite3 /data/data.db "SELECT id, title, duration FROM Track LIMIT 20;"
```

## Affected files

- `app/features/audio-archive/worker.server.ts` — primary fix location
- `app/utils/audio-metadata.server.ts` — `extractAudioMetadata()` to use
- `app/features/audio-archive/tigris-upload.server.ts` — `uploadToTigris()` returns `{ key }`

## Backfill

Existing tracks with null duration need a backfill script. For each track with an `AudioFile` record:
1. Download the file from Tigris (via presigned URL)
2. Extract metadata with `extractAudioMetadata()`
3. Update `Track.duration` and `TrackAudioFile` fields

This is a separate task from the worker fix (which prevents new gaps).
