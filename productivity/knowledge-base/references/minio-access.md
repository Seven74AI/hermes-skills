# MinIO Access — Browser/HTTP Quirks

## HTTP, not HTTPS

MinIO on port 9000 serves **plain HTTP only**. No TLS is configured.
Browsers (especially Chrome on mobile) auto-upgrade `http://` to `https://`,
which fails with `ERR_SSL_PROTOCOL_ERROR`.

Always use **`http://`** explicitly:
```
http://vmi3304846.tail5c02a1.ts.net:9000/knowledge-base/reels/<slug>.mp4
```

## Credentials

MinIO uses its own credentials, not system users:

- **Username:** `kb-admin`
- **Password:** `kb-a8b475286106705a`

These are in `~/.hermes/profiles/researcher-videos/.env` as
`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`.

## Buckets

- **`knowledge-base`** — Primary bucket. All notes link here. 13 GB / 456 objects.
## mc CLI

The `minio` alias has credentials:
```
mc alias list  # shows 'minio' with kb-admin
mc ls minio/knowledge-base/
```
The `local` alias has NO credentials — don't use it for MinIO operations.
