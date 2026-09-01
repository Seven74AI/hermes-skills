# Integration testing against the real SQLite DB

Use when a test must exercise real DB behavior — unique-constraint collisions,
upsert matching, foreign-key cascades. `vi.mock("#app/utils/db.server")` cannot
reproduce these (a mocked `upsert` has no unique key to collide on); use the real
client instead.

## Harness (already wired)

- `tests/setup/global-setup.ts` builds `tests/prisma/base.db` (migrate deploy + seed).
- `tests/setup/db-setup.ts` (imported by `setup-test-env.ts`) copies `base.db` to a
  per-pool `tests/prisma/data.<VITEST_POOL_ID>.db` and points `DATABASE_URL` at it,
  so each test pool gets an isolated, already-migrated database.
- Real client: `import { prisma } from "#app/utils/db.server"` — do **not** `vi.mock` it.

## Steps

1. Import the real `prisma` and leave `db.server` unmocked.
2. Build fixtures with `createUser()` from `#tests/db-utils`.
3. Clean up in `beforeEach` with `deleteMany()` on the tables you touched
   (children first, or rely on `onDelete: Cascade`).
4. For route loader/action tests, mock only the external collaborators
   (`requireUserId`, OAuth/service modules). Pass a real `url` in the args —
   React Router v8 `LoaderFunctionArgs` includes `url: URL`, so
   `url.searchParams.get(...)` works when the loader is called directly.
5. Shared mock fns referenced by `vi.mock` factories: declare them with
   `vi.hoisted(() => ({ mockGetTokens: vi.fn(), ... }))` when the module under
   test is statically imported, so the hoisted factory does not run before the
   `const` initializes (TDZ error).

## Example

`app/routes/music+/services+/youtube+/callback.test.tsx` — connects two users in
sequence and asserts each keeps their own token (regression test for the
global-`Connection`-key bug).
