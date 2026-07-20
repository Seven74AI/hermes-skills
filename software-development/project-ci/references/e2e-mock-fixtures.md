# E2E Mock Fixture Prerequisites

When E2E tests depend on mock data files (audio, images, etc.) that don't exist in the repo:

## Pattern

1. **Identify what's missing** — check server logs during E2E runs for 404/500 on mock storage endpoints
2. **Create a generation script** — Python or shell script that creates the missing fixture files in the mock storage directory
3. **Make it idempotent** — `os.makedirs(..., exist_ok=True)` so running it multiple times is safe
4. **Run before first E2E run** — or integrate into the project's `setup` / `test:e2e:install` script

## Real case: music-library audio fixtures

The Tigris mock serves files from `tests/fixtures/uploaded/`. Player E2E tests create `TrackAudioFile` rows with fake `objectKey` values like `audio/test-transport.mp3`, but the actual MP3 blob never existed. The browser hit `GET /resources/audio/<id>?stream=1` → signed URL → Tigris mock → 404 → player showed no transport controls → `toBeVisible(Pause)` timed out.

**Fix script** (`tests/fixtures/create-dummy-audio.py`):
```python
import base64, os

silent_mp3_b64 = '...'  # base64-encoded minimal silent MP3
mp3_data = base64.b64decode(silent_mp3_b64 + '==')

os.makedirs('tests/fixtures/uploaded/audio', exist_ok=True)

test_keys = ['test-transport.mp3', 'test-keyboard.mp3', 'test-playlist.mp3']
for key in test_keys:
    filepath = os.path.join('tests/fixtures/uploaded/audio', key)
    with open(filepath, 'wb') as f:
        f.write(mp3_data)
```

**Base64 pitfall:** Long base64 strings may lose padding when copied/saved. Always append `==` padding before decoding and validate with a try/except.

## Prevention checklist

- [ ] Every mock data file referenced by E2E tests exists in `tests/fixtures/`
- [ ] Generation script is idempotent and committed to the repo
- [ ] Script is run by `pretest:e2e:run` or documented in project README/CONTEXT
- [ ] Base64-encoded content has valid padding (use `base64.b64decode(data + '==')`)
