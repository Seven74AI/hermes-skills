# FTS5 Index Management

## Rebuild command

SQLite FTS5 rebuild via SQL:

```sql
INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild');
INSERT INTO albums_fts(albums_fts) VALUES('rebuild');
INSERT INTO artists_fts(artists_fts) VALUES('rebuild');
```

Admin route: `app/routes/admin+/fts-index.tsx` at `/admin/fts-index` (requires admin role).

## Health check

Compare FTS row counts vs entity table counts:

```sql
SELECT COUNT(*) FROM tracks_fts;   -- should >= SELECT COUNT(*) FROM Track;
SELECT COUNT(*) FROM albums_fts;   -- should >= SELECT COUNT(*) FROM Album;
SELECT COUNT(*) FROM artists_fts;  -- should >= SELECT COUNT(*) FROM Artist;
```

FTS rows can exceed entity rows (deleted records may still be in the index). FTS < entity means stale index → needs rebuild.

## FTS5 table schema

```sql
CREATE VIRTUAL TABLE tracks_fts USING fts5(
  track_id, title, artist_name, album_name,
  tokenize='unicode61'
);

CREATE VIRTUAL TABLE albums_fts USING fts5(
  album_id, name, artist_name,
  tokenize='unicode61'
);

CREATE VIRTUAL TABLE artists_fts USING fts5(
  artist_id, name, genre,
  tokenize='unicode61'
);
```

## When to rebuild

- After bulk imports that bypass Prisma (raw SQL inserts don't trigger FTS triggers)
- After restoring from backup
- When search returns no results for known data
- FTS row count < entity row count
