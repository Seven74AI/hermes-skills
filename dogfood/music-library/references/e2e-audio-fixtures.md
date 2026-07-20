# E2E Audio Fixtures

## Prerequisites for Transport Control Tests

Player/transport E2E tests (play/pause toggle, seek, next/prev, keyboard shortcuts) require dummy MP3 files in mock storage.

```bash
python3 tests/fixtures/create-dummy-audio.py
```

## How it works

1. Tigris mock (`tests/mocks/tigris.ts`) serves files from `tests/fixtures/uploaded/`
2. E2E tests create `TrackAudioFile` rows with `objectKey` like `audio/test-transport.mp3`
3. Browser requests signed URL → Tigris mock resolves to `tests/fixtures/uploaded/audio/test-transport.mp3`

## Known test keys

From `tests/fixtures/create-dummy-audio.py`:
- `test-transport.mp3` — play/pause toggle test
- `test-keyboard.mp3` — keyboard shortcuts test
- `test-playlist.mp3` — playlist playback test

When adding new transport tests that use a new `objectKey`, add the key to the script.
