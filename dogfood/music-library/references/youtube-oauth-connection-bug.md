# YouTube OAuth Connection Bug — global `Connection` unique key

## Symptom

"Connect to YouTube" works for the first user, then breaks:

- The second user who connects appears **"not connected"** (empty playlists) even though the callback "succeeded".
- The first user's tokens get **silently clobbered** — they now see the wrong account's playlists / a broken connection.

## Root cause

`prisma/schema.prisma` — the unique key is **global**, not per-user:

```prisma
model Connection {
  id           String   @id @default(cuid())
  providerName String
  providerId   String
  userId       String
  tokens       String?
  // ...
  @@unique([providerName, providerId])   // ← no userId
}
```

The YouTube OAuth callback (`app/routes/music+/services+/youtube+/callback.tsx`) hardcodes `providerId: "youtube"` and its `update` branch never sets `userId`:

```ts
prisma.connection.upsert({
  where: { providerName_providerId: { providerName: "youtube", providerId: "youtube" } },
  update: { tokens },   // ← no userId
  create: { userId, providerName: "youtube", providerId: "youtube", tokens },
})
```

Contrast: the login callback (`app/routes/_auth+/auth.$provider.callback.ts`) correctly uses
`providerId: String(profile.id)` — the real provider account id. So the `providerName_providerId`
key is meant to encode "one provider account ↔ one user"; YouTube breaks that invariant by using a constant.

Consequence: every YouTube connection collides on `("youtube","youtube")`. Only ONE row can ever
exist. The second connect matches that row, overwrites its `tokens`, and leaves `userId` pointing
at the first user.

Lookup side (`app/features/service-connection/service-connection.server.ts` →
`resolveYouTubeAccessToken`) uses `findFirst({ where: { providerName, userId } })`, so the second
user finds nothing → "not connected".

## Correct fix

Set `providerId` to the **real YouTube channel id** (from `getYouTubeUserInfo()` → `channel.id`)
instead of `"youtube"`, and set `userId` in the `update` branch too. This restores the
"one provider account ↔ one user" invariant the schema was designed for. Do NOT just add `userId`
to the unique key — that would also weaken the login-provider flow, which relies on the global
`providerName_providerId` key to reject the same Google/GitHub account linking to two users.

## Reproduction recipe (proven)

Ad-hoc script against the real schema, run from repo root:

```ts
// scripts/repro-connection-bug.ts
import { PrismaClient } from "#prisma/client.js";
import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";

const prisma = new PrismaClient({ adapter: new PrismaBetterSqlite3({ url: "file:./data.db" }) });

async function youtubeCallbackUpsert(userId: string, tokens: string) {
  return prisma.connection.upsert({
    where: { providerName_providerId: { providerName: "youtube", providerId: "youtube" } },
    update: { tokens },
    create: { userId, providerName: "youtube", providerId: "youtube", tokens },
  });
}
// create A → connect A → create B → connect B → findFirst({ providerName, userId }) for both
```

```bash
DATABASE_URL="file:./data.db" npx tsx scripts/repro-connection-bug.ts
```

Result: after B connects there is ONE row with `userId = A, tokens = TOKEN_B`;
A resolves `TOKEN_B` (wrong), B resolves `null` (wrong).

## Pitfall: `?connection_limit=1` breaks ad-hoc better-sqlite3 scripts

`DATABASE_URL="file:./data.db?connection_limit=1"` — the `PrismaBetterSqlite3` adapter treats the
query param as part of the FILENAME and opens a literal `data.db?connection_limit=1` file (empty,
no tables → `TableDoesNotExist`). The app strips it via `getDatabaseUrl()`
(`app/utils/database-url.server.ts`).

For throwaway repro scripts, pass `DATABASE_URL="file:./data.db"` (no query param) or replicate
`getDatabaseUrl()`. Also note the Prisma CLI and the runtime adapter resolve relative `file:`
paths differently — always confirm which `.db` actually holds the tables (`sqlite3 <file> .tables`).
