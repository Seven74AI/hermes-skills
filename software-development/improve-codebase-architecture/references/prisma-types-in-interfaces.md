# Prisma types in provider-agnostic interfaces

Two recurring patterns from reviewing Prisma-heavy codebases.

## Pattern 1: Hand-written interfaces that diverge from Prisma

When a function's declared return type is `Omit<Prisma.TrackCreateInput, 'artist'>`
and a separate interface (`BatchProcessorProvider`) hand-writes a subset of that
return type, they will drift. The `as any` cast is the symptom.

### How to detect

Look for `as any` casts at seams between provider interfaces and their
implementations. The cast is almost always hiding a structural mismatch.

### How to fix

1. Find the actual Prisma-generated type (in `generated/prisma/models/`).
2. Compare each field in the hand-written interface against the generated type.
3. The fix is one of:
   - **Use the generated type directly** if both sides of the seam are
     Prisma-aware (e.g., two server-side modules that both import Prisma).
     This is what we did with `Prisma.ServiceCreateNestedOneWithoutTracksInput`
     — the generated type has `connect?`, `create?`, and `connectOrCreate?`,
     all optional. The hand-written version had `{ connect: { id: string } }`
     (required, wrong shape).
   - **Widen to `unknown`** if the field is destructured and discarded by all
     callers, and you want to signal "don't touch this."
   - **Remove the field from the interface** if no caller reads it and it's
     purely an artifact of the Prisma return type.

### Example (from music-library)

```typescript
// ❌ Hand-written guess — required, only connect allowed
export interface BatchProcessorProvider {
  transformPlaylistItem(...): {
    service: { connect: { id: string } }  // wrong in TWO ways
  }
}

// ✅ Generated type — all optional, three sub-fields
type ServiceCreateNestedOneWithoutTracksInput = {
  create?: Prisma.XOR<ServiceCreateWithoutTracksInput, ...>
  connectOrCreate?: ServiceCreateOrConnectWithoutTracksInput
  connect?: Prisma.ServiceWhereUniqueInput
}
```

The real fix: `service?: Prisma.ServiceCreateNestedOneWithoutTracksInput`

## Pattern 2: When NOT to use Prisma-derived types

Prisma `GetPayload<>` and `CreateInput` types are auto-generated and always
accurate — but they're also deeply nested, verbose, and coupled to Prisma's
query structure.

### The decision framework

| Context | Use Prisma type? | Why |
|---------|-----------------|-----|
| Server-to-server seam where both sides import Prisma | ✅ Yes | Both consumers know Prisma; the generated type prevents drift |
| Provider interface with Prisma-aware implementations | ✅ Yes | Same reason as above |
| Frontend component prop types | ❌ No | `Prisma.TrackGetPayload<{ include: { artist: { select: { id, name } }, ... } }>` is unreadable. Hand-write a concise named interface. |
| Route loader return types consumed by components | ❌ No | The component only needs a subset. A purpose-built name like `PlaylistCoverTrack { id, coverImage }` is self-documenting. |
| Utility function returns (`{ id, name }`) | ❌ No | `Prisma.ArtistGetPayload<{ select: { id, name } }>` adds noise without value for a two-field type. |

### The "named subset" pattern

When five components each define a local `interface Track`, the problem isn't
that they're hand-written — it's that they share the same generic name. Fix by
giving each a purpose-built name:

```
TrackListItemData   — the full display shape (id, title, artist, duration, coverImage, serviceUrl, service, audioFiles)
SortableListTrack   — adds createdAt: string, omits thumbnailUrl
PlaylistCardTrack   — bare minimum for a card (id, title, artist, duration, coverImage)
PlaylistHeroTrack   — same subset as card
PlaylistCoverTrack  — only id + coverImage
```

The name tells you what data the component actually needs. `PlaylistCoverTrack`
with only `id` and `coverImage` is more informative than `TrackWithUserStatus`
(with its 15+ fields) or `Prisma.TrackGetPayload<...>` (unreadable).
