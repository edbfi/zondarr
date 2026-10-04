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

### Public origin and proxies

Set `ORIGIN` to the address people open in the browser, for example
`ORIGIN=http://192.168.1.10:3000`. It is required for plain HTTP: without it the
frontend assumes it is served over HTTPS behind a proxy that preserves the `Host`
header, so over plain HTTP signing in and saving changes (including first-run setup)
fail, and one startup warning says so. Leave `ORIGIN` unset only behind an HTTPS
reverse proxy that passes the original `Host`. `ORIGIN` must be a bare `http(s)`
origin (no path, query, fragment or credentials), or the frontend refuses to start;
letter case, a default port and a trailing `/` are normalized. With `ORIGIN` set,
`start` fronts the SvelteKit server and supplies that origin.

The backend's own CSRF check reads `CSRF_ORIGIN`: set it to the same value. The
Docker image defaults `CSRF_ORIGIN` to `ORIGIN`.

Cookies follow `ORIGIN`'s scheme: the frontend marks the session cookies it relays
from the backend `Secure` exactly when the public origin is `https`. The backend's
`SECURE_COOKIES` setting only affects clients that call the backend port directly.

Every write (`POST`, `PUT`, `PATCH`, `DELETE`) through the frontend must carry an
`Origin` header equal to the public origin; browsers send it. Scripts and API
clients that write through the frontend port must send it too, or get 403
(`FRONTEND_ORIGIN_MISMATCH`).

Behind a reverse proxy:

- Set `ADDRESS_HEADER=x-forwarded-for` (with `XFF_DEPTH` set to the number of
  proxies, default 1) only when every request goes through the proxy; otherwise a
  client can forge its address.
- `PROTOCOL_HEADER` and `HOST_HEADER` (for example `x-forwarded-proto` and
  `x-forwarded-host`) are only for deployments without `ORIGIN`, behind a trusted
  proxy that sets them. `ORIGIN` wins over them.

Other frontend settings: `SHUTDOWN_TIMEOUT` (default 30 seconds) is how long a
stopping frontend waits for open requests, such as the log viewer's stream, before
closing them; the Docker image sets a shorter default that fits Docker's stop
timeout. With `ORIGIN` set, the frontend exits at that deadline even if the app
is still waiting on the backend. `BODY_SIZE_LIMIT` (default `512K`) caps request bodies. See
[.env.example](.env.example) for every variable.

## License
GNU Affero General Public License v3.0
