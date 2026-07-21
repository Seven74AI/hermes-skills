# FTS5 Index Rebuild

The FTS5 tables are standalone (no `content=` option) — they store their own copies of content alongside the index, kept in sync by triggers. When search results are stale, rebuild the index.

## Which approach to use

### 1. Native `rebuild` command (fast, rebuilds from FTS-stored content)

SQLite FTS5's `INSERT INTO ft(ft) VALUES('rebuild')` works on these tables because they store content (not contentless). It rebuilds the index from the FTS table's own stored copies:

```sql
INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild');
INSERT INTO albums_fts(albums_fts) VALUES('rebuild');
INSERT INTO artists_fts(artists_fts) VALUES('rebuild');
```

From Prisma:
```ts
await prisma.$executeRawUnsafe(`INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')`)
```

This is fast but rebuilds from the FTS copies — if triggers missed an update, the stale data persists.

### 2. DELETE + INSERT from source tables (rebuilds from ground truth)

When the FTS-stored content itself may be stale (trigger bugs, bulk imports, direct SQL), rebuild from the source tables directly. Wrap in a transaction to prevent an empty-search window:

```sql
BEGIN;
DELETE FROM tracks_fts;
INSERT INTO tracks_fts(track_id, title, artist_name, album_name)
SELECT t.id, t.title, a.name, COALESCE(alb.name, '')
FROM Track t
JOIN Artist a ON t.artistId = a.id
LEFT JOIN Album alb ON t.albumId = alb.id;
COMMIT;
```

Same pattern for albums and artists — see the migration backfill at `prisma/migrations/20251202130000_add_fts5_search/migration.sql`.

From Prisma:
```ts
await prisma.$executeRawUnsafe(`BEGIN`)
await prisma.$executeRawUnsafe(`DELETE FROM tracks_fts`)
await prisma.$executeRawUnsafe(`
  INSERT INTO tracks_fts(track_id, title, artist_name, album_name)
  SELECT t.id, t.title, a.name, COALESCE(alb.name, '')
  FROM Track t
  JOIN Artist a ON t.artistId = a.id
  LEFT JOIN Album alb ON t.albumId = alb.id
`)
await prisma.$executeRawUnsafe(`COMMIT`)
```

## Admin Page

`app/routes/admin+/fts-index.tsx` — at `/admin/fts-index` (admin only). Shows FTS row counts vs entity counts, health badges, per-entity rebuild and rebuild-all buttons. Requires `clientAction` export for React Router 8 code-splitting.

## Diagnosis

If search returns no results but the database has data:

| Query | What it checks |
|---|---|
| `SELECT COUNT(*) FROM tracks_fts` | FTS5 indexed rows |
| `SELECT COUNT(*) FROM Track` | Actual track rows |

If FTS count < entity count, triggers may have missed updates — use approach 2 (DELETE+INSERT from source).
