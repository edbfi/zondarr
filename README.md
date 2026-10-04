<p align="center">
  <img src="public/zondarr-logo.svg" alt="Zondarr Logo" width="256" height="256">
</p>

<h1 align="center">Zondarr</h1>

<p align="center">
  <strong>Unified invitation and user management for Plex and Jellyfin media servers</strong>
</p>

<p align="center">
  <a href="https://github.com/edbfi/zondarr/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Bun-%23000000.svg?logo=bun&logoColor=white" alt="Bun">
  <img src="https://img.shields.io/badge/SvelteKit-FF3E00?logo=svelte&logoColor=white" alt="SvelteKit">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
</p>

## WIP
...

## Development and production frontend

Use Bun **1.4.2**, matching `frontend/package.json`. `uv run dev_cli`
remains the launcher for the Python backend and frontend together.

For frontend-only development (with the backend running):

```sh
cd frontend
bun install --frozen-lockfile
bun run dev
```

Build and start the production frontend from the same directory:

```sh
bun run build
bun run start
```

`start` runs `scripts/serve.ts` with Bun in production mode. The Python
backend runs separately; configure `INTERNAL_API_URL` for the frontend's server-side
API proxy. Leave `PUBLIC_API_URL` empty for same-origin browser requests. See
[.env.example](.env.example) for backend security, database and bootstrap settings.
The container keeps both services under s6 and runs the same entry point.

Set `ORIGIN` to the public origin when serving plain HTTP, for example
`ORIGIN=http://192.168.1.10:3000`. The frontend then fronts the SvelteKit server and
uses that origin for its same-origin checks. Without `ORIGIN` the server assumes
`https://<Host>`, which is right behind a TLS proxy that preserves `Host`; over plain
HTTP it rejects every write (logins, logouts, saves) with 403, and a startup warning
says so. `ORIGIN` must be a bare `http(s)` origin (no path or credentials), or the
frontend refuses to start. Set the backend's `CSRF_ORIGIN` to the same origin.

## License
GNU Affero General Public License v3.0
