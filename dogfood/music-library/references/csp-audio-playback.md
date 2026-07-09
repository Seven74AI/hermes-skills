# CSP Audio Playback Block — Diagnostic Reference

## Symptom triad

When CSP `media-src 'self'` blocks audio from Tigris/S3:

1. **Player renders** (bar visible) but shows `0:00` duration or `--:--`
2. **Nothing plays** — clicking play does nothing, no audio
3. **Download button works** — `<a>` click bypasses `media-src` CSP

## Root cause (current code)

The current implementation uses a 302 redirect, which is wrong per decision #22:

```
Browser → GET /resources/audio/{id} → 302 → {bucket}.fly.storage.tigris.dev/{key}?...
                                                    ↑ different origin
CSP: media-src 'self'  ← BLOCKS this
```

## Settled decision (CONTEXT.md #22)

> **No redirect — direct presigned URL.** The audio resource route returns the presigned Tigris URL directly (no 302 redirect). Client fetches it and sets `<audio src>` to the S3 URL. Presigned URL exposes only the access key ID + signature — can only GET that single MP3 until expiry. CORS config on Tigris bucket enables Range-seeking directly against the CDN.

The redirect was deemed useless because:
- It adds an extra HTTP round-trip
- The presigned URL is already safe (1-hour, single file, no secret key)
- CORS on the Tigris bucket handles Range-seeking directly against the CDN

## Why dev works, prod doesn't

`server/index.ts:84`:
```js
reportOnly: MODE !== 'production'
```

- Dev: `Content-Security-Policy-Report-Only` → violations logged, NOT enforced
- Prod: `Content-Security-Policy` → violations enforced, audio blocked

## Verification

```bash
# Check prod CSP headers
curl -sI "https://music-library-5a00.fly.dev/" | grep content-security-policy

# Look for: media-src 'self'  ← no Tigris domain
```

## Full fix (three parts)

### Part 1: CSP — allow Tigris domain

Two files, must be kept in sync. Without this, the `<audio>` element can't load from S3 even after removing the redirect.

#### `server/index.ts` (helmet middleware, line 92)

```js
// Before:
'media-src': ["'self'"],

// After:
'media-src': ["'self'", "https://*.fly.storage.tigris.dev"],
```

#### `app/utils/csp.server.ts` (static CSP for SSR, line 17)

```js
// Before:
'media-src': "'self'",

// After:
'media-src': "'self' https://*.fly.storage.tigris.dev",
```

### Part 2: Audio route — return URL instead of redirect

`app/routes/resources+/audio.$trackId.tsx` — remove `return redirect(url)` (line 110), return the URL as JSON:

```tsx
// Before (line 107-110):
const { url } = await getFileUrl(audioFile.objectKey, 3600)
return redirect(url)

// After:
const { url } = await getFileUrl(audioFile.objectKey, 3600)
return Response.json({ url })
```

### Part 3: Audio player — fetch URL, set on `<audio>`

The player currently sets `src="/resources/audio/${track.id}"`. Change to fetch the URL first:

```tsx
// Before (audio-player.tsx line 54):
const audioUrl = audioFile && track ? `/resources/audio/${track.id}` : null
<audio ref={audioRef} src={audioUrl} ... />

// After:
const [audioUrl, setAudioUrl] = useState<string | null>(null)
useEffect(() => {
  if (!track || !audioFile) return
  fetch(`/resources/audio/${track.id}`)
    .then(r => r.json())
    .then(({ url }) => setAudioUrl(url))
}, [track?.id])
<audio ref={audioRef} src={audioUrl ?? undefined} ... />
```

### Why wildcard is OK for the Tigris domain

The Tigris bucket name comes from `BUCKET_NAME` env var. Using `*.fly.storage.tigris.dev` is safe because:
- Files are already protected by short-lived presigned URLs (1-hour expiry)
- The S3 bucket has its own access controls (AWS IAM)
- Anyone who has the presigned URL can already access the file regardless of CSP

### Alternative: exact domain via env var

If preferred, read the bucket name and construct the exact domain:
```js
const tigrisDomain = `https://${process.env.BUCKET_NAME}.fly.storage.tigris.dev`
// then add tigrisDomain to media-src
```

## Troubleshooting checklist

1. Is `reportOnly` false in production? (yes by default with `MODE !== 'production'`)
2. Does `media-src` include the Tigris domain? (check with curl)
3. Is the audio route returning JSON with the presigned URL (not 302 redirect)?
4. Is the player fetching the URL and setting it on `<audio src>`?
5. Does the redirect target match the domain in CSP? (must be exact, wildcards only work for subdomains like `*.example.com`)
