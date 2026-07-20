# set-cookie-parser v3 Migration

## Breaking changes

### ESM-only — no default export

```ts
// ❌ v2
import setCookieParser from 'set-cookie-parser'

// ✅ v3
import { parseString, parse, splitCookiesString } from 'set-cookie-parser'
```

### `parseString()` returns `Cookie | null`

In v2, `parseString()` returned `Cookie`. In v3, the return type is `Cookie | null`.

```ts
// ❌ v2 — direct property access
const cookie = setCookieParser.parseString(header)
return new URLSearchParams({ [cookie.name]: cookie.value })

// ✅ v3 — non-null assertion (when guaranteed valid in tests)
const cookie = parseString(header)!
return new URLSearchParams({ [cookie.name]: cookie.value })

// ✅ v3 — optional chaining (when value may be absent)
const match = cookies.find(c => parseString(c)?.name === 'en_session')
```

### Type mismatch with Playwright

`parseString()` returns `{ name?: string; value?: string; ... }` (optional fields). Playwright's `context.addCookies()` expects `{ name: string; value: string; ... }` (required fields). Cast the result:

```ts
const cookieConfig = parseString(setCookie)!
const newConfig = {
  ...cookieConfig,
  domain: 'localhost',
} as Parameters<Page['context']>[0]['addCookies'] extends (cookies: infer C) => any ? C : never
// Or simpler with explicit type
```

## Finding all usages

```bash
rg "set-cookie-parser|setCookieParser|parseString" --include='*.ts' --include='*.tsx'
```
