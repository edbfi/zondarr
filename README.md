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

`start` runs the built SvelteKit server with Bun in production mode. The Python
backend runs separately; configure `INTERNAL_API_URL` for the frontend's server-side
API proxy. Leave `PUBLIC_API_URL` empty for same-origin browser requests. See
[.env.example](.env.example) for backend security, database and bootstrap settings.
The container keeps both services under s6 and directly runs the same Bun entry point.

## License
GNU Affero General Public License v3.0
