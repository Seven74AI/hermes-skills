# Threads Media Types

Values of `media_type` in Threads JSON responses.

| media_type | Meaning | Pipeline |
|-----------|---------|----------|
| `1` | Single image | TEXT → `researcher` |
| `2` | Single video (native Threads) | VIDEO → `researcher-videos` |
| `8` | Instagram carousel | TEXT → `researcher` |
| `19` | Instagram video cross-post (NOT a carousel — contains `media_type=2` child with `video_versions` on `cdninstagram.com`) | VIDEO → `researcher-videos` |

**Detection rule**: Never route on `media_type` alone. Always check for `video_versions` regardless of outer type. If `video_versions` is an array (not null), treat as VIDEO.
