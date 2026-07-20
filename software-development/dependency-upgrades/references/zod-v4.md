# Zod v4 Migration — Breaking Changes

## Breaking changes encountered (zod v3 → v4)

### 1. `@conform-to/zod` import path

The default import `@conform-to/zod` only works with Zod v3. For v4, use the `/v4` entrypoint.

```ts
// ❌ v3 — crashes with "ZodPipeline not found"
import { parseWithZod, getZodConstraint } from '@conform-to/zod'

// ✅ v4
import { parseWithZod, getZodConstraint } from '@conform-to/zod/v4'
```

### 2. `required_error` → `error`

```ts
// ❌ z.string({ required_error: 'Name is required' })
// ✅ z.string({ error: 'Name is required' })
```

### 3. `ZodError.errors` → `ZodError.issues`

```ts
// ❌ error.errors
// ✅ error.issues
```

Also affects `.safeParse()` results: `result.error.issues[0]?.message`

### 4. `z.function()` no longer a Zod schema

In v4, `z.function()` is a "function factory", not a schema — it can't be used inside `z.object()` or `z.union()` anymore.

```ts
// ❌ v3 — used purely for type inference
z.function().args(z.object({ loaderData: z.unknown() })).returns(z.custom<React.ReactNode>())

// ✅ v4 — use z.custom<> with a type alias
type BreadcrumbFn = (arg: { loaderData: unknown }) => React.ReactNode
z.custom<BreadcrumbFn>()
```

### 5. `z.string().url()` → `z.url()`

String format methods moved to top-level functions. `z.string().url()` is deprecated but still works in v4.0 — prefer `z.url()`.

```ts
// ❌ deprecated
z.string().url()

// ✅
z.url()
```

Similarly: `z.string().email()` → `z.email()`, `z.string().uuid()` → `z.uuid()`

### 6. `superRefine` return type: `void`, not `null`

Zod v4 expects `void | Promise<void>` from superRefine callbacks. Remove `return null` and `return z.NEVER`.

```ts
// ❌ v3
ActionSchema.superRefine(async (data, ctx) => {
  if (data.intent === 'cancel') return null
  if (!valid) {
    ctx.addIssue({ path: ['code'], code: z.ZodIssueCode.custom, message: 'Invalid' })
    return z.NEVER
  }
  return null
})

// ✅ v4
ActionSchema.superRefine(async (data, ctx) => {
  if (data.intent === 'cancel') return
  if (!valid) {
    ctx.addIssue({ path: ['code'], code: z.ZodIssueCode.custom, message: 'Invalid' })
  }
})
```

`ctx.addIssue()` alone is sufficient — no need for `z.NEVER`.

### 7. Other changes (not hit in our codebase)

- `z.record()` now requires 2 args: `z.record(z.string(), z.string())`
- `.parse()` second arg is now parse options, not custom data
- `z.uuid()` enforces RFC 4122 compliance (use `z.guid()` for v3 compatibility)
- `z.lazyobject` removed
