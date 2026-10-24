# Spec: zondarr

**Status:** the ground floor (skeleton) is specified here, approved by the orchestrator
(2026-10-18) and built. The capability map below is approved; no product module is specified yet.

## Objective

zondarr lets the owner of private Plex and Jellyfin servers invite people with a code and a link:
the invitee completes the owner's welcome steps and joins the servers, and the owner manages
invitations, members, servers and wizards from an admin console
([PRODUCT.md](../PRODUCT.md), [legacy spec](product/legacy-spec.md)).

**This spec covers only the ground floor:** an empty, production-shaped SvelteKit app that builds,
type-checks, tests, lints and serves on Bun, styled from the design tokens, with the edbfi Bun web
CI around it. It has no database, authentication, Plex, Jellyfin or product features. Its job is to
make the first module spec cheap to build: every later PR adds behaviour, not plumbing.

## Capability map

**Status:** approved by the owner (2026-10-24). Module ids never change. Each module gets its own
`docs/SPEC-<id>.md`, which the owner approves just before it is built.
Sources: [PRODUCT.md](../PRODUCT.md), [decisions.md](decisions.md), the
[legacy spec](product/legacy-spec.md) and the [surface briefs](../.impeccable/surfaces/).

**Every module keeps to [Code structure](../AGENTS.md#code-structure).** Its spec names the files it
adds in that layout, and review checks them. In short:
- The same role folders as every edbfi app. A folder exists only once it holds a real file.
- One purpose per file. No `utils`, `helpers`, `common` or `misc` files.
- Group by domain under the role folders. The folder says where; the file name says what.
- Imports only go downwards. Routes, hooks and jobs stay thin and call services.
- Tests sit next to their source.

**Every module writes its text in English and Danish** through `i18n` (D21): no user-facing text in
components or services, and dates and numbers formatted for the viewer's locale.

| # | Module id | Responsibility | Depends on | Surfaces |
|---|---|---|---|---|
| 1 | `secrets` | Encrypts stored secrets (media server API keys, two-factor secrets, the OIDC client secret) before they reach the database (D20) | — | — |
| 2 | `i18n` | The translation groundwork (D21) with Paraglide JS (D22): message files in English and Danish, choosing each request's language, the language switcher, formatting dates and numbers for the viewer's locale, and a check that every message exists in both languages | — | the language switcher in each shell |
| 3 | `setup` | Startup checks, database and migrations, settings with their environment locks (legacy §8.2, §9.2), the bootstrap token, and claiming the instance for its one owner, keeping the origin it was claimed from as the trusted origin (legacy §6.1 pre-filled it). Replaces `/healthz` with the legacy §9.4 health (ground-floor choice 5) | `secrets`, `i18n` | first-run setup (no brief yet); `/healthz` |
| 4 | `sign-in` | Owner sign-in with username and password, sessions, sign-out, lockout and rate limits on sign-in (legacy §12.11), origin check and the trusted origin with its test (the first value comes from `setup`), secure cookies, security headers, referrer policy and CSP, and the admin shell | `setup` | owner sign-in (no brief yet); the admin shell; `/admin/settings`, which it builds first with the General, Account and About tabs; later modules add their tabs and sections |
| 5 | `two-factor` | Optional but strongly recommended (D20): authenticator codes, backup codes and the challenge after every way of signing in, with replay protection and the attempt limit (legacy §6.2, §10). Adds the offer to first-run setup, right after the owner account is created and before any connection step, and the reminder in the admin shell while it is off | `sign-in` | the two-factor offer in first-run setup; the two-factor section of `/admin/settings` (Account); the reminder in the admin shell |
| 6 | `plex-provider` | The Plex provider (D12, D18): connection test, server info, libraries, the user list with relationship types, direct share, friend and home accounts, removal stepped by relationship, disabling as a share with no libraries (D23), library access, permissions and PIN sign-in. Reconciles shares by machine id and account id after every write (legacy §12.14) | `setup` | — |
| 7 | `jellyfin-provider` | The Jellyfin provider (D19): connection test, server info, libraries, the user list with administrators flagged (legacy §12.15), create with password, delete, enable and disable, library access and permissions | `setup` | — |
| 8 | `servers` | Adding a server with the mandatory connection test and type detection, the list and detail, editing with a re-test that works with the stored key (legacy §12.3), deleting with defined cascade rules (legacy §12.7), the per-provider environment overrides, library sync, and the optional first-server step after `setup` and the two-factor offer | `sign-in`, `plex-provider`, `jellyfin-provider` | `/admin/servers` (no brief yet); the Servers tab of `/admin/settings` |
| 9 | `members` | Identities and their per-server users, the members list with search and filters, the detail with linked users, enable and disable (on Plex, a share with no libraries, D23), permissions loaded from the server (legacy §12.6), and delete stepped by relationship | `servers` | `/admin/members/[id]` |
| 10 | `wizards` | Wizards, steps, interactions and translations, the content allow-list, keyboard reordering (legacy §12.20), the preview, and the server-side step check: signed progress and completion tokens, the quiz cool-down and a timer started on the server (legacy §12.10). A disabled or empty wizard counts as none (legacy §12.9) | `sign-in` | `/admin/wizards/[id]`; the wizard list (no brief yet) |
| 11 | `invitations` | Invitations with target servers, libraries, expiry, max uses, access duration and wizards; generated and normalised codes (legacy §12.12), the validation order, clear errors for max uses below the use count (legacy §12.8), the copy link, and the invitation expiry job | `servers`, `wizards` | `/admin/invitations` |
| 12 | `join` | The public join shell, code validation with its exact reasons, the server check, and the pre- and post-registration wizard stages, with rate limits on validation (legacy §12.11) | `invitations`, `wizards` | `/join/[code]`, `/join/[code]/welcome` |
| 13 | `redemption` | Plex sign-in for invitees (opaque handles, one-time redemption tokens, the real reason when one is invalid, legacy §12.16), the Jellyfin account form, the reservation, creating each account once, rollback with the partial-success report, an idempotency key against double submits (legacy §12.23), the default permissions, the receipt, and the cleanup job for expired sign-in attempts | `join`, `members` | `/join/[code]/account`, `/join/[code]/complete` |
| 14 | `sync` | User sync (matched, orphaned, stale; dry run by default, import, relationship refresh), the media server sync job with per-server timeouts, retries and circuit breakers, sync runs, an interval that takes effect without a restart (legacy §12.2), and running it by hand | `members` | the Sync tab of `/admin/settings`; the sync panel on server detail; "Sync members" on `/admin/members/[id]` |
| 15 | `member-expiry` | The expiry policy (D23): the default in the settings and the override on each invitation, the job that applies it, and showing on each invitation what happens at expiry (PRODUCT.md, legacy §12.1) | `members`, `invitations` | a section of `/admin/settings`; the policy on the invitation editor and detail |
| 16 | `owner-plex-sign-in` | Linking the owner's account to their Plex account in the admin settings, after which "Sign in with Plex" signs them in as the owner, through two-factor when it is on (D20) | `two-factor`, `plex-provider`, `redemption` | the Plex section of `/admin/settings` (Account); the Plex button on owner sign-in |
| 17 | `oidc-sign-in` | Connecting one OpenID Connect provider (Authentik, Authelia, Pocket ID, Tinyauth and others) by its issuer, client id and secret, and linking the owner's account to it, after which it signs them in as the owner, and offering to skip `two-factor` when the provider's `amr` claim reports its own second factor (D20) | `two-factor` | the OIDC section of `/admin/settings` (Account); its button on owner sign-in |
| 18 | `logs` | The live log viewer: the in-memory buffer of recent entries, the stream with reconnects that don't repeat entries, filters, search and the detail panel (legacy §6.9) | `sign-in` | `/admin/logs` (no brief yet) |
| 19 | `overview` | The owner dashboard: member, invitation and server counts, server health, pending invitations, recent activity, and a reminder while no server is connected (legacy §12.21) | `servers`, `invitations`, `members`, `sync` | `/admin` |

Build order: `secrets` → `i18n` → `setup` → `sign-in` → `two-factor` → `plex-provider`,
`jellyfin-provider` → `servers` → `members`, `wizards` → `invitations` → `join` → `redemption` →
`sync`, `member-expiry`, `owner-plex-sign-in`, `oidc-sign-in`, `logs` → `overview`. A comma means
either order works. The first five are the opening every edbfi app shares (D20). The first of the
two providers adds the provider contract with its capability declarations (legacy §7.1) and the
SSRF-safe outbound HTTP (D8). `redemption` is the first time an invitee gets something they can
use, so everything before it is the shortest path there.

### Where modules live

Paths are under `src/lib/server/`, except those starting with `routes/` (under `src/`) or `lib/`
(under `src/`), and `hooks.server.ts` (`src/hooks.server.ts`). They follow the
[Code structure](../AGENTS.md#code-structure) layout:

| Module | Main homes |
|---|---|
| `secrets` | `security/secrets/`; loading the key in `config/` |
| `i18n` | `messages/en.json` and `messages/da.json`, `project.inlang/` (Paraglide's settings), `lib/shared/i18n/` (formatting); `paraglideMiddleware` in `hooks.server.ts` |
| `setup` | `db/` (client, migrations, settings and owner schema), `config/`, `logging/`, `services/setup/`, `services/health.ts`, `security/bootstrap-token.ts`; `routes/setup/`, `routes/healthz/`, and the setup gate in `hooks.server.ts` |
| `sign-in` | `services/sign-in/`, `security/` (sessions, password hashing, rate limits, origin check, headers); `routes/(admin)/` layout and sign-in page, `routes/(admin)/admin/settings/`, `lib/components/layout/` |
| `two-factor` | `services/two-factor/`, the owner schema's two-factor fields in `db/`; the offer in `routes/setup/`, the challenge page beside the sign-in page, its section in `routes/(admin)/admin/settings/`, and the reminder in `lib/components/layout/` |
| `plex-provider` | `providers/plex/`, `providers/media-server.ts` (the contract, if first), `http/` (if first) |
| `jellyfin-provider` | `providers/jellyfin/`, `providers/media-server.ts` and `http/` (if first) |
| `servers` | `services/servers/`, `db/` server and library schema; `routes/(admin)/admin/servers/` |
| `members` | `services/members/`, `db/` identity and member schema; `routes/(admin)/admin/members/` |
| `wizards` | `services/wizards/`, `db/` wizard schema, `lib/components/wizard/` (the invitee view, shared by the preview and the join flow); `routes/(admin)/admin/wizards/` |
| `invitations` | `services/invitations/`, `db/` invitation schema, `jobs/invitation-expiry.ts`; `routes/(admin)/admin/invitations/` |
| `join` | `services/join/`; `routes/(public)/join/[code]/`, `routes/(public)/join/[code]/welcome/` |
| `redemption` | `services/redemption/`, `services/provider-sign-in/`, `db/` sign-in attempt schema, `jobs/provider-sign-in-cleanup.ts`; `routes/(public)/join/[code]/account/`, `routes/(public)/join/[code]/complete/`, the sign-in polling endpoint under `routes/api/` |
| `sync` | `services/sync/`, `db/` sync-run schema, `jobs/media-server-sync.ts` |
| `member-expiry` | `services/member-expiry/`, `jobs/member-expiry.ts` |
| `owner-plex-sign-in` | `services/sign-in/plex.ts` (uses `services/provider-sign-in/`) |
| `oidc-sign-in` | `services/sign-in/oidc.ts`, the provider settings and the owner's link in `db/`; its callback route beside the sign-in page |
| `logs` | `logging/` (the buffer), `services/logs/`; `routes/(admin)/admin/logs/` and its stream endpoint |
| `overview` | `services/overview/`; `routes/(admin)/admin/` |

### Open decisions each module closes

- `i18n`: the validation that D22 lists (pinned versions, the adapter-bun build, a Weblate round
  trip).
- `setup`: D15 (Drizzle and Turso pair) and the logging library half of D14. The secrets half of
  D16's backup and restore goes with `secrets`.
- The first module with a background job closes the job half of D14: `sign-in` if its session
  cleanup is a job, otherwise `invitations`.
- `plex-provider`: D18, including whether Plex keeps a share with no libraries (D23).
  `jellyfin-provider`: D19.
- D13: `redemption`'s sign-in polling is the first JSON endpoint; its spec decides whether it needs
  a generated client. D17 stays open as an accepted limit.

### Left out on purpose

- Any role beyond the one owner, and admin management (legacy §4, §12.4; PRODUCT.md, D20).
- Rotating refresh tokens, short-lived access tokens and the bearer header for scripts (legacy
  §6.2, §10). D20's server-side sessions replace them, and no script needs the API.
- Owner sign-in with a Jellyfin account (legacy §6.2; owner decision, D20).
- Signing in through a reverse proxy's headers (D20): `oidc-sign-in` covers the same identity
  providers.
- Connecting Weblate (D21): later work, outside this map. The message files are ready for it.
- Checking that a Plex sign-in belongs to the owner of a configured Plex server (legacy §6.2). The
  signed-in owner links their Plex account themselves (D20), and zondarr may have several Plex
  servers or none.
- Per-invitation permissions (legacy §12.5): the field was never used, and redemption applies the
  default set.
- The debug mode's auth bypass, test-only PIN endpoint and API documentation pages (legacy §9.2):
  development tooling, not product.
- Email, notifications and a member portal (PRODUCT.md, legacy §12.25).

### Surfaces with no brief yet

First-run setup, owner sign-in, `/admin/servers`, the wizard list and `/admin/logs` are needed (all
are in the legacy app and in PRODUCT.md's admin shell) but have no brief. The
`/join/[code]/account` brief covers only Plex; the Jellyfin account form joins it. Each gets its
brief before its module is specced.

## Tech stack

The stack decisions are in [decisions.md](decisions.md) (D1–D12). Versions are exact pins in
`package.json` (Bun from its `packageManager` field) and `bun.lock`; Dependabot moves them. Every
package is a dev dependency, so adapter-bun bundles it and `bun ./build` needs no `node_modules`.

| Part | Package |
|---|---|
| Runtime and package manager | Bun |
| Language | `typescript` (6.x) |
| UI framework | `svelte` / `@sveltejs/kit` |
| Build | `vite` / `@sveltejs/vite-plugin-svelte` |
| Adapter | `@sveltejs/adapter-bun` |
| Styling | `@pandacss/dev`, `@pandacss/vite` (its Vite plugin), `@pandacss/preset-base` |
| Primitives | `@ark-ui/svelte` |
| Type check | `svelte-check` |
| Unit tests | `vitest` (`node` environment); `happy-dom` joins with the first component test |
| e2e | `@playwright/test` (Chromium) |
| Lint and format | `@biomejs/biome` |

Setup facts for this stack:
- SvelteKit 3 is configured through its Vite plugin (`vite.config.ts`); there's no
  `svelte.config.js`. `tsconfig.json` extends `$app/tsconfig`, which `svelte-kit sync` generates.
- Package subpath imports replace `$lib` and need explicit file targets: `#lib/*` maps to
  `./src/lib/*` and imports name the file with its extension (`#lib/server/services/health.ts`);
  `#styled-system/*` maps to the generated `./styled-system/*/index.js`.
- `svelte-kit sync` runs before Panda's codegen, in `prepare` and in `check`.
- The Panda Vite plugin appends the generated CSS to the stylesheet that declares the layer order
  (`src/app.css`), and `transform: true` turns static `css()` calls into class strings at build
  time.
- Hook types come from `@sveltejs/kit/hooks`.
- Tools run under Bun with `--bun`; a lifecycle script (`prepare`) calls each bin as
  `bun --bun <bin>`, because `bun ci` doesn't apply `--bun` to lifecycle scripts.
- Bun blocks `@parcel/watcher`'s install script (it builds with Node); Panda works without it.

## Commands

| Command | Does |
|---|---|
| `bun ci` | frozen install; `prepare` runs `svelte-kit sync` and Panda codegen |
| `bun run --bun dev` | Vite dev server |
| `bun run --bun build` | production build through adapter-bun into `build/` |
| `bun run --bun preview` | runs the built server (`bun ./build`; `PORT`, default 3000, and `HOST`) |
| `bun run --bun check` | `svelte-kit sync`, Panda codegen, then `svelte-check` failing on any error or warning |
| `bun run --bun test` | Vitest unit tests, once (no watch) |
| `bun run --bun smoke` | Playwright e2e smoke; it starts the built server, so `build` comes first, and Chromium comes from `bunx --bun playwright install chromium` |
| `bun run --bun lint` | `biome check` |
| `prek run --all-files --hook-stage manual` | everything CI's `checks` job runs |

## Project structure

The folder tree is in [AGENTS.md](../AGENTS.md#structure) and its rules in
[Code structure](../AGENTS.md#code-structure).

## Code style

Biome's defaults with the shared `biome.json` (tabs, double quotes, 100 columns). TypeScript strict;
`#lib/…` imports. File names and layout follow
[Code structure](../AGENTS.md#code-structure).

```ts
import { healthResponse } from "#lib/server/services/health.ts";
import type { RequestHandler } from "./$types";

export const GET: RequestHandler = () => healthResponse();
```

## Design tokens

- [`panda.config.ts`](../panda.config.ts) holds every design token: colours, type styles,
  spacing, radii, layout sizes, breakpoints and motion durations, under the names DESIGN.md uses.
  It replaced the seed token files that came with the design package.
- Colours are semantic tokens behind a colour-mode condition (`_dark`), dark by default
  (`class="dark"` on `<html>` in `src/app.html`); light values can be added later without touching
  components.
- Only `@pandacss/preset-base` is loaded (utilities and conditions), so no preset palette competes
  with the app's tokens, and `strictTokens` makes a raw value in `css()` a type error that `check`
  reports.
- The placeholder page uses only Panda tokens: no raw colour, size or font values in components. Its
  heading uses the `h1` style (Outfit); DM Serif Display stays reserved for the public welcome and
  success surfaces.

## Testing strategy

- **Unit (Vitest, `node` environment):** one test, for the `/healthz` handler: status 200, body
  `ok`, `cache-control: no-store`. Component tests use happy-dom when components exist; never jsdom.
- **e2e (Playwright, Chromium, under Bun):** one smoke test against the built adapter-bun server.
  It checks that `/` returns 200, shows the placeholder heading, hydrates (it waits for the
  `data-hydrated` attribute the root layout sets when mounted), applies the Panda background token
  and `h1` text style and logs no console errors, and that `/healthz` returns `ok`.
- prek runs the unit tests (`tests` hook); CI's `smoke` job builds and runs the smoke test.

## CI and repo tooling

zondarr is a Bun web repo with edbfi-ci's Bun web templates:
- `.pre-commit-config.yaml`: Biome, `biome-migrate`, `check-peers`, the `tests` hook, plus a
  `check` hook (`bun run --bun check`), keeping the vendored-skill exclusions and the `docs-set`
  hook.
- `.github/workflows/ci.yml`: `checks` (prek), `smoke` (Chromium install, build, smoke) and `audit`
  (outside PRs); `checks` and `smoke` sit behind `ci-ok`, every job that installs runs with failing
  `node`, `npm` and `npx` on `PATH`, and the weekly run is `2 4 * * 0`.
- `.github/dependabot.yml` covers `github-actions`, `pre-commit` and `bun`, and
  `.github/workflows/biome-migrate.yml` applies Biome migrations to Dependabot's Biome PRs.

## Boundaries

- **Always:** Bun with `--bun` for every tool; tokens only through Panda; keep SvelteKit's
  configuration in the Vite plugin; prek green before each commit.
- **Ask first:** any dependency not in the tech stack table; any change to `biome.json` (it is
  shared by the five rewrite apps); any CI shape that differs from the edbfi-ci template.
- **Never:** a database, authentication, Plex, Jellyfin or any product feature; a second styling
  tool or primitive library; Node, npm or npx anywhere, including CI.

## Success criteria

1. A fresh clone passes `bun ci`, `bun run --bun check` (zero errors and warnings), `bun run --bun
   test`, `bun run --bun build`, `bun run --bun smoke` and `prek run --all-files --hook-stage
   manual`, with no Node on `PATH`.
2. The built server (`bun ./build`) serves `/` with the placeholder page and `/healthz` with `ok`.
3. `panda.config.ts` holds every design token; the seed token files are gone, and nothing in `src/`
   uses a raw colour, size or font value.
4. Only folders with real files exist; `#lib` resolves in app code, tests and `svelte-check`.
5. CI on the PR runs `checks`, `smoke` and `ci-ok` green; `audit` runs outside PRs.

## Ground-floor choices

Choices 1–3 were settled for the first rewrite app's skeleton and are reused here, since zondarr's
design doesn't call for anything different; choices 4 and 5 are zondarr's own.

1. **Fonts.** DESIGN.md wants DM Serif Display, Outfit and IBM Plex Mono bundled locally (the legacy
   app loaded them from a hosted service, legacy spec §9.4). The skeleton defines the font tokens
   with system fallbacks; the first surface adds the font files (a dependency the owner approves
   then).
2. **Ark UI before its first use.** The skeleton installs `@ark-ui/svelte`, so the Panda and Ark
   pairing and `check-peers` are settled early; the first `ui/` wrapper comes with the first surface
   that needs one.
3. **Security headers and CSP.** The legacy join page suppresses the referrer (legacy spec §6.6,
   §10). Security headers, the referrer policy and a CSP belong to the first module that serves real
   pages (the public join flow or admin sign-in), not the skeleton.
4. **Where the logo lives.** SvelteKit serves static files from `static/`, so the logo is
   `static/zondarr-logo.svg` (it was in `public/`), which the README shows and `src/app.html` uses
   as the favicon, the layout the other rewrite apps use.
5. **Health.** `/healthz` always answers `ok`. The module that adds the database replaces it with
   legacy spec §9.4's health: overall (healthy, or degraded by a persistence check), liveness and
   readiness, unauthenticated.
