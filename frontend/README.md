# Zondarr frontend

The SvelteKit app for Zondarr (Svelte 5, TypeScript, UnoCSS), run with Bun. The
Python backend lives in [`../backend`](../backend); the repository
[README](../README.md) covers the whole project, and [`CLAUDE.md`](CLAUDE.md) in
this directory lists the conventions and gotchas.

## Requirements

Bun **1.4.2**, matching `packageManager` in `package.json`. The Biome and prek
tooling is installed at the repository root, so run `bun install` there once as
well.

## Commands

Run these from `frontend/`, or prefix them with `bun run --cwd frontend` from the
repository root.

| Task | Command |
| --- | --- |
| Install dependencies | `bun install --frozen-lockfile` |
| Development server | `bun run dev` |
| Production build | `bun run build` |
| Preview the build | `bun run preview` |
| Start the built server | `NODE_ENV=production bun scripts/serve.ts` (from `frontend/`) |
| Type check | `bun run check` |
| Lint and format check | `bun run check:biome` |
| Tests | `bun run test` |
| Regenerate API types | `bun run generate:api` (backend running on `:8000`) |

Use `bun run test`, not `bun test`: the latter is Bun's own runner and does not
compile Svelte.

Start the server directly, as above; the `start` script runs the same command. With
Bun 1.4.2's default shell, `bun run start` and `bun start` deliver one Ctrl+C twice,
which skips the `SHUTDOWN_TIMEOUT` drain and stops at once with exit status 1.

## Running with the backend

`uv run dev_cli` from the repository root starts the backend and this dev server
together. To run the frontend alone against a backend that is already running:

```sh
bun install --frozen-lockfile
bun run dev
```

Start that backend with `DEBUG=true` (as `dev_cli` does) or with
`CSRF_ORIGIN=http://localhost:5173`. Otherwise its CSRF check rejects the browser's
writes from the dev server with 403 (sign-in and setup are exempt, so the failures
start after login).

In production the browser calls same-origin `/api/*`, which the server proxies to
`INTERNAL_API_URL`; leave `PUBLIC_API_URL` empty. See
[`.env.example`](../.env.example) for the settings.
