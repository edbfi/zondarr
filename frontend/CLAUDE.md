# CLAUDE.md — frontend

Run these from `frontend/`, or prefix them with `bun run --cwd frontend` from the root.

| Task | Command |
| --- | --- |
| All tests | `bun run test` (vitest, jsdom, `--maxWorkers=4`). Not `bun test`: that is Bun's own runner and does not compile Svelte |
| One file | `bun run test src/lib/api/client.test.ts` |
| One case | `bun run test src/lib/api/client.test.ts -t "test name"` |
| Typecheck | `bun run check` (svelte-check, then a second pass with `--tsgo` via `check:native`) |
| Lint / format | `bun run check:biome` (runs `biome ci ..`, which uses the root `biome.json`); fix with `node_modules/.bin/biome check --write .` |
| Regenerate API types | `bun run generate:api` (backend must be running on `:8000`) |

## Gotchas

- `src/lib/api/types.d.ts` is generated from the backend OpenAPI schema. Don't edit it by hand. After `generate:api`, run `node_modules/.bin/biome format --write src/lib/api/types.d.ts`. The committed file is Biome-formatted, and both `check:biome` and CI's `bun .github/scripts/check-api.ts` compare against that form.
- Styling is UnoCSS (`uno.config.ts`: presetWind4, presetShadcn, presetIcons). `tailwind.config.js` is an empty stub kept only for the shadcn-svelte CLI, so theme settings there have no effect. The app's own colors are `--cr-*` variables in `src/app.css`, exposed as `cr-*` utilities in `uno.config.ts`.
- `vitest-setup.ts` mocks `$env/dynamic/public` and `$env/dynamic/private` as `{}`, so `PUBLIC_API_URL` and friends are always unset in tests.
- Component tests are named `*.svelte.test.ts` (plain `*.test.ts` is for non-component modules). Components that need `children` snippets or `bind:this` are rendered through a `*-test-wrapper.svelte`, as in `src/lib/components/error-boundary-test-wrapper.svelte`.
- `src/hooks.server.ts` redirects unauthenticated requests to `/login` unless the path is in `PUBLIC_PATHS`. A new public page needs an entry there.
- `smoke/*.spec.ts` is a Playwright test that CI drives through `.github/scripts/smoke.py` against built servers. Vitest never picks it up, and running `bun run smoke:browser` directly fails because `SMOKE_URL` is unset.

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
| `@sveltejs/adapter-node` | `svelte-adapter-bun` (`svelte.config.js`); production runs `bun run start` |
| `vite dev` runs on Node | Scripts force Bun: `bun --bun vite dev` / `build` / `preview` |
| `vitest-browser-svelte` in Browser Mode | `@testing-library/svelte` + jsdom (`vite.config.ts`) |
