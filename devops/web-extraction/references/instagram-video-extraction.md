# Instagram Reel Video Extraction via yt-dlp

Firecrawl's `video` format is **cloud-only** — not available on the self-hosted Docker instance
(`localhost:3002`). The self-hosted SDK rejects `"video"` as an invalid format (Pydantic validation
error: not in the literal enum). Use yt-dlp instead.

## Quick Recipe

```bash
# 1. List formats (works without login — reads embed page metadata)
yt-dlp --print "%(title)s\n%(uploader)s\n%(duration)s\n%(like_count)s\n%(formats)s" \
  "https://www.instagram.com/reel/DR-rVE1ggZH/"

# 2. If download fails with "login required", extract the CDN URLs from step 1's output
#    and download audio + video streams directly:

# Audio (DASH audio, m4a, ~50kbps)
curl -s -o /tmp/ig_audio.m4a -H "User-Agent: Mozilla/5.0 ..." \
  -H "Referer: https://www.instagram.com/" \
  "<CDN_AUDIO_URL>"

# Video (DASH video, mp4, pick a resolution)
curl -s -o /tmp/ig_video.mp4 -H "User-Agent: Mozilla/5.0 ..." \
  -H "Referer: https://www.instagram.com/" \
  "<CDN_VIDEO_URL>"

# 3. Merge
ffmpeg -y -i /tmp/ig_video.mp4 -i /tmp/ig_audio.m4a -c copy -shortest /tmp/ig_reel_final.mp4

# 4. Cleanup
rm /tmp/ig_video.mp4 /tmp/ig_audio.m4a
```

## How It Works

Instagram Reels use **DASH streaming**: audio and video are separate streams. The embed page
(which yt-dlp reads) exposes signed CDN URLs. These URLs are time-limited (signed with `oe=`
expiry parameter) but valid for several minutes — enough to download both streams.

The `--print` formats call only reads metadata, no download attempt, so it bypasses the login
gate. Once you have the CDN URLs, `curl` with a browser User-Agent + `Referer: instagram.com`
header fetches the raw streams directly.

## Format Selection

Instagram serves multiple DASH video renditions at different bitrates (all same resolution for
a given tier). Pick one — higher bitrate = better quality but larger file:

| Resolution  | Typical bitrates | Approx size (2 min) |
|------------|-----------------|---------------------|
| 640x1136   | ~165-480 kbps   | 2.5-7 MB           |
| 720x1280   | ~165-1355 kbps  | 2.5-20 MB          |
| 1080x1920  | ~1945 kbps      | ~28 MB             |

The combined `1` format (640x1136, mp4 with audio) is the simplest to grab but lowest quality.
For best quality, pick the highest-bitrate video DASH stream + the audio DASH stream.

## Pitfalls

- **CDN URLs expire quickly** (minutes). Download immediately after extracting the format list.
- **No csrf token warning** is harmless — yt-dlp works around it via the embed page.
- **yt-dlp version matters**. Tested working: 2026.03.17. Older versions may not parse embed pages.
- **Firecrawl `video` format is cloud-only** — the self-hosted SDK Pydantic model rejects it.
  The cloud version extracts from YouTube and similar supported platforms; Instagram is not one of them.
- **Instagram `og:video` meta tag is always null** (observed in metadata). The video is loaded
  dynamically via JS — that's why Firecrawl's markdown scrape can't reach it and why yt-dlp
  needs the embed page path.
