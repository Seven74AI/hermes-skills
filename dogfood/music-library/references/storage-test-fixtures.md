# Storage Test Fixtures — Local File Pattern

**Date:** 2026-07-09
**When to use:** Any test hitting the audio/image resource routes that falls through to `getFileUrl()` (requires S3 env vars).

## Problem

Routes like `audio.$trackId.tsx` check for local files first:
```typescript
const localFilePath = join(process.cwd(), 'tests', 'fixtures', 'uploaded', audioFile.objectKey)
if (existsSync(localFilePath)) { /* serve locally */ }

// Falls through → requires S3 config
const { url } = await getFileUrl(audioFile.objectKey, 3600)
```

Without S3 env vars (`AWS_ENDPOINT_URL_S3`, `BUCKET_NAME`, etc.), `getFileUrl` throws `"Storage is not configured"`.

## Pattern

In the test file, add a helper that creates a tiny fixture file at the expected path:

```typescript
import { mkdirSync, writeFileSync, rmSync } from 'fs'
import { join } from 'path'
import { afterAll } from 'vitest'

const fixtureDirs: string[] = []
afterAll(() => {
    for (const dir of fixtureDirs) {
        try { rmSync(dir, { recursive: true, force: true }) } catch {}
    }
})

function createAudioFixture(objectKey: string) {
    const fixturePath = join(process.cwd(), 'tests', 'fixtures', 'uploaded', objectKey)
    const dir = fixturePath.substring(0, fixturePath.lastIndexOf('/'))
    mkdirSync(dir, { recursive: true })
    writeFileSync(fixturePath, Buffer.from([0xFF, 0xFB, 0x90, 0x00, ...Array(40).fill(0)]))
    fixtureDirs.push(join(process.cwd(), 'tests', 'fixtures', 'uploaded', objectKey.split('/')[0]!))
}
```

Call `createAudioFixture(objectKey)` after creating the `TrackAudioFile` record in `setupTestData()`.

## TypeScript Note

`objectKey.split('/')[0]` is `string | undefined` — use `!` non-null assertion since the key always contains `/` (e.g., `audio/tracks/...`).
