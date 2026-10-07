# CLAUDE.md — frontend

Run these from `frontend/`, or prefix them with `bun run --cwd frontend` from the root.

| Task | Command |
| --- | --- |
| All tests | `bun run test` (vitest, jsdom, `--maxWorkers=4`; two projects, `components` and `server`, plus the front's tests in `scripts/serve.test.ts`). Not `bun test`: that is Bun's own runner and does not compile Svelte |
| One file | `bun run test src/lib/api/client.test.ts` |
| One case | `bun run test src/lib/api/client.test.ts -t "test name"` |
| Typecheck | `bun run check` (svelte-check, then a second pass with `--tsgo` via `check:native`) |
| Lint / format | `bun run check:biome` (runs `biome ci ..`, which uses the root `biome.json`); fix with `bunx --no-install biome check --write .`. Biome is installed at the repo root, so run `bun install` there first |
| Regenerate API types | `bun run generate:api` (backend must be running on `:8000`) |

## Gotchas

- `src/lib/api/types.d.ts` is generated from the backend OpenAPI schema. Don't edit it by hand. After `generate:api`, run `bunx --no-install biome format --write src/lib/api/types.d.ts`. The committed file is Biome-formatted, and `check:biome` checks that form.
- Styling is UnoCSS (`uno.config.ts`: presetWind4, presetShadcn, presetIcons). `tailwind.config.js` is an empty stub kept only for the shadcn-svelte CLI, so theme settings there have no effect. The app's own colors are `--cr-*` variables in `src/app.css`, exposed as `cr-*` utilities in `uno.config.ts`.
- Environment variables are declared in `src/env.ts` (SvelteKit 3 exposes only declared ones; an undeclared one reads as `undefined`) and read through `$app/env/private` or `$app/env/public`. `src/env.test.ts` fails when a read variable is not declared. `vitest-setup.ts` mocks both modules with every variable `undefined`, so `PUBLIC_API_URL` and friends are always unset in tests.
- Component tests are named `*.svelte.test.ts` (plain `*.test.ts` is for non-component modules) and run in the `components` Vitest project, the only one with `svelteTesting()`; a plain `*.test.ts` that renders must be added to `componentTests` in `vite.config.ts`. Never render components in the `server` project: Kit 3's server `redirect()` breaks under the browser condition. Components that need `children` snippets or `bind:this` are rendered through a `*-test-wrapper.svelte`, as in `src/lib/components/error-boundary-test-wrapper.svelte`.
- `src/hooks.server.ts` redirects unauthenticated requests to `/login` unless the path is in `PUBLIC_PATHS`. A new public page needs an entry there. It also rejects any `POST`/`PUT`/`PATCH`/`DELETE` whose `Origin` is not `event.url.origin` (403, `FRONTEND_ORIGIN_MISMATCH`), and cookies the frontend sets or deletes take `secure` from `isSecureRequest(event.url)` (`$lib/server/request-origin.ts`).
- Everything that calls the backend (the `/api/[...path]` proxy, `/api/auth/setup`, the session refresh in `hooks.server.ts`) goes through `$lib/server/backend-relay.ts`: `backendRequestHeaders` drops hop-by-hop headers, the front's `x-zondarr-*` headers and client `X-Forwarded-*`/`Forwarded` (it keeps `Origin` and `Referer` for the backend's CSRF check), and backend `Set-Cookie` headers get `Secure` from `event.url` (`relayResponseHeaders`, or `event.cookies.parse` plus `relayedCookieOptions`), never from the backend.
- `@sveltejs/adapter-bun` is configured in `vite.config.ts` (`precompress: true`; no `svelte.config.js`), and `$lib` is an explicit alias there and in `tsconfig.json`. Production runs `NODE_ENV=production bun scripts/serve.ts` (the `start` script's command; run it directly: under `bun run start` Bun 1.4.2's default shell delivers one Ctrl+C or group `SIGTERM` twice, and the adapter treats the second as a second signal and exits 1 without the drain): with `ORIGIN` set it fronts the adapter over a private Unix socket; without it the adapter listens directly and assumes `https` + `Host`. It parses `ORIGIN` by the origin contract every edbfi front shares (trimmed; canonical `url.origin` exported as `process.env.ORIGIN`; one fixed startup error and one fixed warning text, both pinned by tests) and forwards the raw request path (`forwardPath`), never `new URL(request.url)`. Its idle window (`CONNECTION_IDLE_TIMEOUT`/`IDLE_TIMEOUT`) applies to the client only: the timer is off from the end of the request body until the app answers, then re-armed (Bun 1.4.2 otherwise closes a request still waiting on the app). On shutdown it drains both sides within `SHUTDOWN_TIMEOUT` and exits at that deadline even if the app still has work in flight (a request waiting on the backend would otherwise keep the process alive). Its tests run in the `server` project against `scripts/fixtures/standin-adapter.js`.

## Calling the backend

| Question | → `$lib/api/client.ts` | → `$lib/api/auth.ts` |
| --- | --- | --- |
| Endpoint under `/api/v1/*`? | ✅ | |
| Endpoint under `/api/auth/*` (login, setup, refresh, TOTP)? | | ✅ |
| Typed via | `openapi-fetch` `paths` | raw `fetch` + `components` types |
| In a `load` function, pass SvelteKit's `fetch` as | `createScopedClient(fetch)` as the last argument | the `customFetch` argument |

Add new wrappers to the matching module rather than calling `api.GET` or `fetch` in components. For the standard error toast in components, wrap the call in `withErrorHandling(() => ...)` from `client.ts`. The pattern in `load` functions (`src/routes/(admin)/servers/+page.ts`):

```ts
export const load: PageLoad = async ({ fetch }) => {
	const client = createScopedClient(fetch);
	const result = await getServers(undefined, client);
```

Wrappers take the client as their last parameter, defaulting to the browser client (`client: ApiClient = api`).

## Where `.agents/rules/svelte5-sveltekit-app.md` disagrees with this repo

| Rule file says | This repo does (follow this) |
| --- | --- |
| `vite dev` runs on Node; no `preview` script | Scripts force Bun: `bun --bun vite dev` / `build` / `preview` |
| `vitest-browser-svelte` in Browser Mode | `@testing-library/svelte` + jsdom in both Vitest projects (`vite.config.ts`) |

## Biome configuration

Biome is pinned to an exact version in the root `package.json`. The configuration uses Git ignores, the recommended lint and assist presets, and experimental full Svelte support, and formats every component, `{@const ...}` blocks included. Keep type checking separate from Biome. Project quote, comma and indentation conventions remain explicit in the configuration.

The frontend extends the root configuration with `"extends": "//"`. The root limits Biome to the frontend and its own configuration. The three generic form components remain excluded because of parser limitations. Generated API types remain formatted under the existing generation contract.
