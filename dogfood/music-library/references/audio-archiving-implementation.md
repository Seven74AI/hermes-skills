# Audio Archiving — Condensed Implementation Reference

> Derived from three source docs in `/tmp/`:
> `audio-archive-feature.md`, `003-audio-worker-architecture.md`, `refactor-storage-system.md`
> Adapted per settled decisions in `CONTEXT.md`.

## Models

### ArchiveJob (new)
```prisma
model ArchiveJob {
  id          String   @id @default(cuid())
  trackId     String   @unique  // one job per track
  track       Track    @relation(fields: [trackId], references: [id], onDelete: Cascade)
  status      String   @default("pending") // pending | processing | completed | failed
  priority    Boolean  @default(false)
  retryCount  Int      @default(0)
  errorHistory String? // JSON array: [{code, message, attemptAt, retryCount}]
  lastAttemptAt DateTime?
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt

  @@index([status, priority, createdAt]) // queue ordering
  @@index([status, lastAttemptAt])       // retry logic
}
```

### WorkerState (new)
```prisma
model WorkerState {
  id                  String    @id @default("singleton")
  status              String    @default("running") // running | paused | long_break
  currentlyProcessing Int       @default(0)
  lastQueueRun        DateTime?
  nextLongBreakAt     DateTime?
  lastStateChange     DateTime  @default(now())
  updatedAt           DateTime  @updatedAt
}
```

### YoutubeCookie (new)
```prisma
model YoutubeCookie {
  id          String   @id @default("singleton")
  updatedAt   DateTime @updatedAt
  updatedBy   String?  // userId
  valid       Boolean  @default(true)
}
```

### TrackAudioFile (existing — no queue fields)
Used by both user uploads and completed archives. Queue state lives in ArchiveJob.

## yt-dlp Command
```bash
yt-dlp -x --audio-format mp3 --audio-quality 0 -f bestaudio \
  --no-playlist --quiet --no-warnings --newline \
  --sleep-interval 2-5 --max-sleep-interval 10 \
  --user-agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..." \
  --cookies /data/youtube-cookies.txt \
  --embed-thumbnail --add-metadata \
  --retries 3 --fragment-retries 3 \
  -o "/tmp/%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v={VIDEO_ID}"
```

## Worker Loop (ADR-003 baseline)

```
Interval: 2 minutes
Concurrency: 2 (Promise.all on two ArchiveJob rows)

Each tick:
1. Check WorkerState.status — skip if paused or long_break
2. Check if long break is due (now >= nextLongBreakAt)
   → If yes: wait for currentlyProcessing→0, set status=long_break, sleep 1-2h (polling 30s)
3. Query: ArchiveJob WHERE status='pending' ORDER BY priority DESC, createdAt ASC LIMIT 2
4. Process both concurrently: download → upload → create TrackAudioFile → mark job completed
5. On failure: increment retryCount, append to errorHistory
   Retry schedule: 1st=5min, 2nd=30min, 3rd=2h. After 3rd failure: status=failed

Cookie expiry: if 3+ consecutive 403s → set YoutubeCookie.valid=false → Telegram notification
```

## Files to Create

1. `app/features/audio-archive/audio-archive.server.ts` — downloadTrackAudio(), uploadAudioToStorage(), archiveTrackAudio()
2. `app/features/audio-archive/audio-queue.server.ts` — enqueueTrack(), processQueue(), retry logic
3. `app/features/audio-archive/audio-worker.server.ts` — interval loop, long break, startup cleanup, startWorker()/stopWorker()
4. `app/features/audio-archive/audio-worker-control.server.ts` — pauseWorker(), resumeWorker(), breakLongPause(), getWorkerStatus()
5. `app/features/audio-archive/youtube-cookie.server.ts` — read/write /data/youtube-cookies.txt, validate
6. `app/routes/admin+/audio-queue.tsx` — admin queue page with worker controls
7. `app/routes/admin+/youtube-cookies.tsx` — cookie upload (textarea paste + file upload)
8. `app/routes/resources+/track.$trackId.download.tsx` — signed URL redirect

## Files to Modify

1. `prisma/schema.prisma` — add ArchiveJob, WorkerState, YoutubeCookie
2. `server/index.ts` — import and call startWorker()/stopWorker() from feature dir
3. `app/utils/env.server.ts` — add AUDIO_ARCHIVE_ENABLED
4. `app/utils/service-import.server.ts` — auto-enqueue on track import
5. `app/utils/service-playlist.server.ts` — auto-enqueue on playlist sync
6. `app/routes/library.$trackId.tsx` — download button + archive status badge (check ArchiveJob)
7. `app/routes/library.index.tsx` — download icons
8. `app/routes/resources+/audio.$trackId.tsx` — return presigned URL directly (no redirect, per decision 13)
9. `other/Dockerfile` — install yt-dlp + ffmpeg

## Storage Paths
- Archive: `audio/{serviceName}/{trackId}.mp3` (e.g., `audio/youtube/ckl123.mp3`)
- User upload: `audio/tracks/{trackId}/{service}/{format}/{timestamp}-{fileId}.{ext}` (existing)
- Cookie file: `/data/youtube-cookies.txt`

## Env Vars
```env
AUDIO_ARCHIVE_ENABLED=true
AUDIO_ARCHIVE_MAX_CONCURRENT=2
AUDIO_ARCHIVE_INTERVAL_MS=120000
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
```

## Retry Strategy
| Attempt | Backoff |
|---------|---------|
| 1st     | 5 min   |
| 2nd     | 30 min  |
| 3rd     | 2 hours |
| After   | permanent failure |

## Dependencies
- `execa` (npm) — spawn yt-dlp
- `yt-dlp` (pip, in Dockerfile)
- `ffmpeg` (apt, in Dockerfile)
