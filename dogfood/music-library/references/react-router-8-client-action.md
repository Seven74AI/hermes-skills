# React Router 8 Client Action Proxy

In React Router 8, route modules that export a server `action` AND use `<Form>`,
`useSubmit`, or `useFetcher` to submit to that action MUST also export a
`clientAction`. Without it, code-split route modules throw a 405 error:

```
405 Error: Route "routes/_auth+/login" does not have a clientAction,
but you are trying to submit to it.
```

## The fix

Add a `clientAction` that delegates to the server action using the shared utility:

```tsx
import { proxyClientActionToServer } from '#app/utils/server-proxy-client-action.ts'

export async function clientAction(args: Route.ClientActionArgs) {
  return proxyClientActionToServer(args)
}
```

The utility at `app/utils/server-proxy-client-action.ts`:

```ts
export async function proxyClientActionToServer<T>({
  serverAction,
}: {
  serverAction: () => Promise<T>
}): Promise<T> {
  return serverAction()
}
```

The generic `<T>` is critical: without it, the function returns `Promise<unknown>`,
which React Router infers as `actionData: {}` in `Route.ComponentProps`. Components
accessing `actionData?.result` silently get `undefined` instead of the server action's
real return shape. With `<T>`, the type flows through and `actionData` retains its
proper type.

## Which routes need it

Any route that exports a server `action` and is code-split needs a `clientAction`.
This includes routes in `_auth+`, `admin+`, `resources+`, `settings+`, and any other
route directory that uses `<Form method="post">`, `useSubmit`, or `useFetcher`.

Known routes that need it:
- `login.tsx`
- `signup.tsx`
- `reset-password.tsx`
- `onboarding.tsx`
- `onboarding_.$provider.tsx`
- `verify.tsx`
- `forgot-password.tsx`
- `admin+/fts-index.tsx`

Always check the route for `<Form>`, `useSubmit`, or `useFetcher` usage.
Routes that only render content (no form submission) do NOT need `clientAction`.
