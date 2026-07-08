# Using ORM-generated types on interfaces

Full write-up of the pattern discovered during a music-library architecture review.

## The anti-pattern: hand-written type approximations

```typescript
// ❌ Hand-written approximation
interface BatchProcessorProvider {
  transformPlaylistItem(...): {
    service: { connect: { id: string } }  // guessed the shape wrong
    externalId: string
    // ...
  }
}
```

This decays quickly. The ORM's generated type drifts with schema changes;
the hand-written one doesn't. The result: an `as any` cast at the call site.

In the music-library case, the cast sat at `service-playlist.server.ts:96`
for months, hiding the fact that `service` was `Prisma.ServiceCreateNestedOneWithoutTracksInput`
(all sub-fields optional: `create?`, `connectOrCreate?`, `connect?`) while the
interface claimed it was `{ connect: { id: string } }` (required, single sub-field).

## The real Prisma type

For a relation like `service Service @relation(...)`, Prisma generates:

```typescript
type ServiceCreateNestedOneWithoutTracksInput = {
  create?:          Prisma.XOR<ServiceCreateWithoutTracksInput, ServiceUncheckedCreateWithoutTracksInput>
  connectOrCreate?: ServiceCreateOrConnectWithoutTracksInput
  connect?:         ServiceWhereUniqueInput
}
```

All three sub-fields are optional. The implementation returns `{ connect: { id } }`
which satisfies `connect?: ServiceWhereUniqueInput`.

## Two consumers, one return type

The root cause: `transformYouTubePlaylistItemToTrack` returned a type meant for
direct `prisma.track.create()` consumption, but the batch processor used it as an
intermediate format. The `service` field was populated for Consumer 1 (Prisma insert)
but discarded by Consumer 2 (batch processor):

```
transformYouTubePlaylistItemToTrack()
    │
    ├── Consumer 1: prisma.track.create(data)     ← uses service.connect
    │
    └── Consumer 2: track-batch-processor          ← throws service away
                    const { service: __, ...rest } = transformed
```

The field existed in the return type because Consumer 1 needed it, and both
consumers shared the same function.

## The fix

```typescript
// ✅ Use the generated type
import { type Prisma } from '#prisma/client.js'

interface BatchProcessorProvider {
  transformPlaylistItem(...): {
    service?: Prisma.ServiceCreateNestedOneWithoutTracksInput
    externalId: string
    // ...
  }
}
```

And remove the `as any` cast. The `PlaylistSyncProvider` returns
`Omit<Prisma.TrackCreateInput, 'artist'>` which has `service: Prisma.ServiceCreateNestedOneWithoutTracksInput`
— structurally compatible with `service?:` in the interface.

## When to use `unknown` vs the real type

| Situation | Use |
|-----------|-----|
| Field always destructured-out, never read | Real type — documents intent |
| Two providers return incompatible shapes | Real type — pick ORM's common type |
| Field has no known shape (external data) | `unknown` |
| "Provider-agnostic" by hiding ORM type | **Don't.** ORM type IS the contract |
