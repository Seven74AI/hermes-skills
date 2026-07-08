---
name: interface-type-safety
description: Patterns for keeping interfaces type-safe when ORM-generated types are involved. Use when you find `as any` casts at interface boundaries, or when hand-written type approximations are drifting from auto-generated types.
---

# Interface Type Safety

Catch-all for patterns that keep interfaces honest when auto-generated types
(Prisma, Drizzle, GraphQL codegen, etc.) are in play.

## Core principle

**Use the generated type, not a hand-written approximation of it.**

ORMs and code generators produce exact types. When an interface hand-writes an
approximate version of one of those types, they drift. The symptom is an `as any`
cast at the call site. The fix is importing the real type.

## The signal

An `as any` cast at an interface boundary means two types that should agree don't.
Before reaching for `unknown`, check: does one come from an auto-generated source?

## The fix

```typescript
// ❌ Hand-written approximation (drifts)
service: { connect: { id: string } }

// ❌ Unknown (throws away knowledge)
service?: unknown

// ✅ Real generated type (stays in sync)
service?: Prisma.ServiceCreateNestedOneWithoutTracksInput
```

## When to use `unknown` vs the real type

| Situation | Use |
|-----------|-----|
| Field always destructured-out by callers | Real type — documents intent |
| Two providers return incompatible shapes | Real type — pick ORM's supertype |
| Field has no known shape (external data) | `unknown` |
| Hiding ORM type for "provider-agnosticism" | **Don't.** The ORM type IS the contract |

## Verification

Remove the `as any`, import the type, run typecheck. If it passes, done.
If it doesn't, the mismatch is deeper — surface it, don't paper over it.

See `references/orm-generated-types.md` for the full write-up with Prisma-specific
examples (nested `create`/`connectOrCreate`/`connect` unions).
