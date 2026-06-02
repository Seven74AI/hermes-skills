# `user.id` vs `user.username` Route Parameter Mismatch

## Symptom

A test that logs in as a user and then navigates to `/users/${user.id}` fails with:
- `expect(locator).toBeVisible()` timeout on a button that should be on the page
- Page snapshot shows `No user with the username "<cuid>" exists` (404)

## Root Cause

The user profile route (`app/routes/users+/$username.tsx`) uses `params.username`, NOT `params.id`:

```ts
export async function loader({ params }: LoaderFunctionArgs) {
  const user = await prisma.user.findFirst({
    where: { username: params.username },  // ← expects USERNAME
  })
  if (!user) throw new Response('Not found', { status: 404 })
}
```

The `login()` fixture returns a `user` object with both `id` (a CUID like `cmpv2bovj0000zgkm7b2lse02`) and `username` (a string like `ae_mack_stark88`). Passing `user.id` to the navigate function constructs `/users/cmpv2bovj0000zgkm7b2lse02` which will always 404.

## Fix

```ts
// ❌ WRONG — user.id is a CUID, route expects username
await navigate(`/users/${user.id}`)

// ✅ RIGHT — use user.username
await navigate(`/users/${user.username}`)
```

## Affected Tests

- `2fa.test.ts:63` — fixed 2026-06-01 (was `user.id`, changed to `user.username`)
- Any test that calls `navigate(`/users/${user.id}`)` — search with `grep -rn "users/\$\{user\.id\}" tests/`

## Detection Pattern

When a test fails on a page that should show the user's profile (Logout button, Edit Profile button, etc.) and the page snapshot shows the 404 message with a CUID in the error text, it's this bug. The CUID format (`cmpv...`) is the giveaway — usernames never look like CUIDs.
