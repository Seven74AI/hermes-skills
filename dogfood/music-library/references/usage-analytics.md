# Usage Analytics / Play Counter

How the admin "Plays (30d)" counter works, and whether it records which tracks were played.

## Two-table split (the key mental model)

Every usage event is written to a **raw log** and an **aggregate counter** at the same time
(`app/features/usage-analytics/record-usage.server.ts` → `recordUsageEvent`):

| Table | Purpose | Schema |
|---|---|---|
| `UsageEvent` | Raw event log — the *detail* | `type`, `userId?`, **`trackId?`**, `meta?`, `createdAt`. Indexes: `[type, createdAt]`, `[userId, createdAt]`. **No FK on `trackId`.** |
| `DailyUsageStat` | Pre-aggregated daily counter — the *totals* | `day`, `metric`, `value`. `@@unique([day, metric])`. Metrics: `signups`, `logins`, `library_adds`, `plays_started`, `plays_completed`, `dau`. |
| `DailyActiveUser` | DAU dedupe | `day`, `userId`. `@@unique([day, userId])` — written in the same `$transaction` as the DAU increment so a dedupe row never suppresses its counter. |

`EVENT_TO_METRIC` maps each `UsageEventType` (`signup`, `login`, `library_add`, `play_started`,
`play_completed`) to its `UsageMetric`. DAU increments only for `signup|login|play_started|play_completed`.

## Play event flow (start to finish)

1. **Client fires** (`app/components/audio-player.tsx`): `reportPlayEvent(type, track.id)`
   - `play_started` — once per track, guarded by `playStartedForTrackRef` so seek/replay doesn't double-count.
   - `play_completed` — either the `ended` event, **or** `currentTime / duration >= 0.5` (the ≥50% heuristic). Guarded by `playCompletedForTrackRef`.
2. **Transport** (`app/features/usage-analytics/report-play-event.client.ts`): fire-and-forget
   `fetch POST /resources/play-event`, `credentials: same-origin`, all errors swallowed — analytics must never break playback.
3. **Server** (`app/routes/resources+/play-event.tsx`):
   require auth → `consumePlayEventBudget` (per-user rate limit) → zod-validate → verify the track **exists** in DB → `recordUsageEvent`.

## The admin page reads ONLY the aggregate

`app/routes/admin+/index.tsx` queries `DailyUsageStat` for the last 30 days (via `buildDayRange`
/ `buildSeries` in `admin-users.server.ts`). It never reads `UsageEvent`, so it renders totals
(`playsStarted30d`, `playsCompleted30d`) and bar charts — no per-track breakdown.

## "Does it track which tracks were played?"

**Yes at the raw level, no in the UI.** `UsageEvent.trackId` records the exact track for every
play event, with `userId` + timestamp. But nothing surfaces it — no per-track view exists.

Caveats:
- `UsageEvent` has **no index on `trackId`** — a "which tracks" query is a full scan until you add `@@index([trackId, createdAt])`.
- `trackId` carries **no FK** (the play-event route validates existence manually to stop metric inflation).
- `play_completed` is a heuristic (≥50% heard), not exact completion.
- Rate limit: `PLAY_EVENT_MAX_PER_WINDOW = 60` per `PLAY_EVENT_WINDOW_MS = 60_000` per user (`play-event-rate-limit.server.ts`, `remember`-backed LRU). Bites only scripted abuse; real playback emits ~2 events/track.
