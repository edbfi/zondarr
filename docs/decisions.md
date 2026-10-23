# Decisions

Each entry is a decision and why it was made. Open entries keep their number when they're settled.
The stack entries come from the shared rewrite recipe used by all five edbfi apps, cut down to what
applies to zondarr. Versions live in `package.json` and `bun.lock`.

## Decided

### D1. SvelteKit on one origin

Svelte 5 and SvelteKit 3, with TypeScript for browser and server code. SvelteKit serves pages, form
actions, API endpoints and assets on one origin, with server rendering on and interactive components
in the browser. Backend work happens in server routes, server `load` functions and form actions,
which call application services.

Why: one framework and one origin for both surfaces (the public join flow and the admin console)
keeps sessions, origin checks and deployment simple without the legacy app's separate web layer
relaying to a backend, and it's the recipe all five apps share.

### D2. TypeScript 6, strict

The latest stable TypeScript 6.x at bootstrap, locked; no prereleases, and major upgrades wait until
the Svelte tooling supports them. Strict type checking, run explicitly (the `check` script): running
TypeScript under Bun doesn't type-check it. External input is validated at runtime.

Why: [SvelteKit 3 requires TypeScript 6](https://svelte.dev/docs/kit/migrating-to-sveltekit-3#Updated-dependencies).

### D3. Bun everywhere, no Node

Bun is the runtime and package manager in development, CI and production. Tools run with `--bun`
(`bun run --bun`, `bunx --bun`) so their Node shebangs don't apply; no `node`, `npm` or `npx`.
Packages still come from the npm registry. `bun.lock` is committed and CI installs with
`bun install --frozen-lockfile`.

Why: one runtime for every step, and the official Bun adapter needs it.

### D4. One container, one process, one port

[`@sveltejs/adapter-bun`](https://svelte.dev/docs/kit/adapter-bun) builds a Bun server. zondarr runs
as one application process with one HTTP port in one container; container packaging lives in the
separate `zondarr-docker` repository. Secrets are configured separately from the database and used
only in server-only code.

Why: a single self-hosted instance for one owner's servers and up to a few thousand members doesn't
need more, and in-memory state (sign-in handshakes, rate limits, sync circuit breakers, the log
buffer, the scheduler lock) can assume one process (see D17).

### D5. Embedded Turso through Drizzle

The database is embedded Turso (`@tursodatabase/database`) through Drizzle
(`drizzle-orm/tursodatabase/database`), with the database file on a persistent data volume. Drizzle
Kit generates SQL migrations, which are reviewed and committed. Migrations run before the app
accepts requests or starts jobs, with one migration owner per database. The legacy app's optional
client-server store isn't carried over.

Drizzle must be `1.0.0-rc.5-5935859` (the verified reference, D15) or a later release that keeps its
Turso transaction fix (Drizzle
[`25abe07`](https://github.com/drizzle-team/drizzle-orm/commit/25abe0785e09cb562d999c9b6b8d92d85e3e7053),
using the API from [Turso #7898](https://github.com/tursodatabase/turso/pull/7898)). Never
`1.0.0-rc.4`: it can roll back unrelated writes that share the connection, and upgrading Turso alone
doesn't fix it.

Why: one file on one volume matches the one-process deployment and keeps backup simple; the
rollback-isolation check passed with the fixed adapter and no application-level write queue.

### D6. Transactions and data access

Database access sits behind named operations (reserve an invitation use, claim a due job).
Application services own the business rules and the transaction boundaries. Every statement in a
transaction goes through the callback's transaction object; transactions stay short, and network
calls (account creation on a media server, sync) happen outside them. No generic layer that promises
interchangeable SQL dialects.

Why: Turso transactions use async callbacks, and a statement outside the transaction handle escapes
it. zondarr targets one engine, so a dialect abstraction would be cost without benefit.

### D7. In-process background jobs

Jobs (invitation expiry, media server sync, session and sign-in cleanup) belong to application
startup and shutdown, never to page requests. Job state is persisted so work recovers after a
restart, runs never overlap, and retries are safe.

Why: SvelteKit and Drizzle provide none of this lifecycle, and sync must stay safe to run unattended
across restarts.

### D8. SSRF-safe outbound HTTP

Every outbound call goes through server-side `fetch` with explicit address validation and a redirect
policy.

Why: Plex and Jellyfin server addresses are admin-supplied, so the server must not become a proxy to
arbitrary hosts. Which address ranges are allowed is product behaviour (legacy spec §6.3 and §10).

### D9. Generated HTTP API clients

Typed HTTP API clients come from `@hey-api/openapi-ts`, generated from the app's own OpenAPI
document during the build. Generated files are never edited by hand. Page loads and form actions use
SvelteKit's generated types instead; services call database operations directly.

Why: one typed contract for the JSON endpoints, without hand-written client code drifting from it.

### D10. Panda CSS and Ark UI only

Styling is Panda CSS 2 through its Vite plugin, with build-time transforms on. Accessible primitives
come from Ark UI for Svelte, unstyled and styled with Panda tokens. Design tokens are defined once,
in Panda's configuration, which loads only `@pandacss/preset-base` (utilities and conditions, no
preset palette) and sets `strictTokens`, so a raw value in a component fails type checking. No
second styling tool or primitive library.

Why: one token source and one primitive library keep the design system (DESIGN.md) enforceable.

### D11. Structured logs to standard output

Logs are structured, one entry per line, written to standard output. The library is open (D14).

Why: the container runtime collects stdout; structured lines can be filtered without parsing prose.

### D12. Plex through `@ctrl/plex` behind a provider

zondarr uses [`@ctrl/plex`](https://github.com/scttcper/plex) wherever it supports the needed
behaviour, and Bun's `fetch` only for missing endpoints or app-specific variations, after checking the
library's implementation. Both sit behind one server-only Plex provider: services call methods such
as `listLibraries()` or `updateLibraryAccess()`, never build Plex requests. The provider applies
consistent timeouts, error handling and runtime response validation. Each custom method documents the
missing library behaviour beside it and is revisited when the library gains it. The
[official Plex API specification](https://developer.plex.tv/) is the reference for Media Server
operations, and `@hey-api/openapi-ts` may generate types or calls from a pinned copy; there's only
ever one implementation of an operation.

zondarr's Plex scope is sharing, invitation acceptance, managed users, permissions and access
removal. It preserves sharing without friendship, matching invitations to the intended server, and
the mapping from local to cloud library ids. The working v2 invitation flow is kept; direct updates
to an accepted server share for library and permission changes are evaluated, with
[Wizarr's custom Plex methods](https://github.com/Wizarrrr/wizarr/blob/main/app/services/media/plex_custom.py)
as a reference, preserving unrelated settings and verifying the resulting access. A Plex friendship
and a server share are different relationships.

Why: a maintained library covers most operations, and one provider boundary keeps the access rules
(share, friendship, home user) explicit and testable.

### D20. Shared opening modules and owner sign-in, in the same shape in every app

Every edbfi rewrite app builds five modules before any feature module, in this order: `secrets`,
`i18n`, `setup`, `sign-in`, then `two-factor`. Each app also gets `oidc-sign-in` later. These
modules have the same shape in all five apps, so signing in works the same way everywhere. Each
app keeps its own copy; there is no shared package.

- **One owner.** Each instance has exactly one owner account, with no other roles: no co-admins,
  viewers or operators, and none planned for later.
- **`secrets`.** Secret values are encrypted in the app before they reach the database, with
  AES-256-GCM through WebCrypto, so this works on any database engine:
  - The key is 32 random bytes from an environment variable or a secret file. It is never derived
    from a password, and a missing or malformed key stops the app at startup.
  - Every encryption uses a fresh random 12-byte nonce.
  - Associated data ties each value to its record and field, so a value copied to another row or
    field fails to decrypt.
  - Every stored value carries its key ID, so the key can be rotated.
- **`i18n`.** The translation groundwork (D21), in place before the first screen.
- **`setup`.** If nobody has claimed the instance yet, the app prints a one-time bootstrap token to
  its log at startup. Whoever types that token claims the instance and creates the owner account.
  After that, setup no longer exists: its routes answer "not found".
- **`sign-in`.** The owner signs in with the username and password created in `setup`. Sessions
  are server-side, and only a hash of each session token is stored.
- **`two-factor`.** Optional, but strongly recommended: the last first-run step offers it, and the
  admin shell keeps reminding the owner until it is on. It uses authenticator-app codes (TOTP), with
  the secret encrypted by `secrets`, single-use backup codes stored only as hashes, each code
  accepted once and a limit on failed attempts. When it is on, every way of signing in passes
  through it, except where an `oidc-sign-in` spec decides to trust the identity provider's own
  second factor.
- **Plex for the owner is an option.** In the apps that use Plex (all of them except comradarr and
  zimuarr), the owner can link their account to their own Plex account in the admin settings once
  setup is done. After that, "Sign in with Plex" also signs them in as the owner. The password
  keeps working, and Plex sign-in for the owner stays off until they link. Where an app has users
  besides the owner, those users sign in with Plex.
- **`oidc-sign-in`.** The owner can also link their account to one OpenID Connect provider, such as
  Authentik, Authelia, Pocket ID or Tinyauth, which then signs them in as the owner. It uses
  discovery and the authorization code flow with PKCE, and keys the link on the provider's issuer
  and subject. As with Plex, linking never creates an owner, and the password keeps working.
  Signing in through a reverse proxy's headers isn't supported.

Each app's connection modules add their own first-run steps after `setup`, such as adding the first
media server here. Invitees never sign in to zondarr; Plex sign-in on the join page only proves
which Plex account gets the share. The owner can't sign in with a Jellyfin account (owner decision:
Jellyfin is a local server, while Plex sign-in runs on Plex's own site).

Why: the owner wants the five apps to look and work alike, and everything else depends on these
modules: every app stores upstream secrets, shows text that must be translatable, needs a safe
first claim and has to know who its owner is. Encrypting in the app (D4: secrets are configured
apart from the database) keeps stolen database files unreadable without the key. Two-factor and
OIDC sign-in were the owner's call for every app; one standard OIDC flow covers the self-hosted
identity providers without a client for each. A copy per app is enough for five apps and avoids
building a shared package before it's needed (YAGNI). A random key with key IDs replaces the legacy
app's keys derived from one application secret, whose rotation broke every stored key (legacy spec
§9.2, §12.22).

### D21. Every interface is translatable, in English and Danish

Every edbfi app is built for translation from its first screen. No user-facing text is written into
components or services: it comes from message files, one per language. English is the source
language and the default, and Danish is the second language. Each request uses the viewer's own
choice, then the browser's preferred languages, then English. Dates, times and numbers are formatted
for the viewer's locale through `Intl`, never in a fixed format. The message files use a format
Weblate reads, plurals included, so a Weblate project can be connected later without changing code.
Connecting Weblate is later work and belongs to no module yet. Text the owner writes, such as
zondarr's wizard steps, is content, translated per step as before (legacy spec §6.7), not through
the message files.

Why: the owner wants full translation support in every app, with Weblate as the translation tool,
and English and Danish now. Adding translation afterwards touches every screen; building it in from
the first one costs little. This fixes legacy spec §12.17 (English only, fixed US dates).

## Open

### D13. Producing the OpenAPI document

How the OpenAPI document is generated from SvelteKit endpoints isn't chosen. The generator must be
validated with the pinned TypeScript 6 and Bun versions. Closes when the first JSON endpoint needs a
generated client.

### D14. Logging library and job lifecycle

The logging library (D11) and the concrete job lifecycle implementation (D7) aren't chosen. Close
before the first background job lands.

### D15. Turso and Drizzle versions

The exact Drizzle ORM and Drizzle Kit pair for Turso is still to be validated in the app: migrations,
type checking, production builds and rollback isolation (D5). Only a focused rollback-isolation check
has passed (Drizzle `1.0.0-rc.5-5935859` with Turso `0.8.3` and `0.9.0-pre.1`). Closes with the first
database module.

### D16. Runtime validation gaps

Not yet validated for this stack: browser interaction with a real component, production containers,
realistic load, and job recovery after a restart. Hydration is validated: the e2e smoke test waits
for the hydrated app in Chromium against the built server, with no console errors.
A crash test doesn't prove recovery from power loss or storage faults. The Turso backup and restore
procedure is still to be defined and tested; the database file and the secrets must be restored
together. Each closes with the work that first depends on it.

### D17. One process

The deployment assumes one application process per database. Horizontal scaling and job
coordination across processes would need a new design. Stays open as an accepted limit.

### D18. Plex library audit

The Plex operations zondarr needs (D12) still have to be audited against a pinned `@ctrl/plex`
version, checked for Bun and TypeScript 6 compatibility, and tested for request payloads and
response parsing. Sign-in, sharing and permission changes must be verified against Plex before they
replace a working flow. Closes with the Plex provider.

### D19. Jellyfin client

The rewrite recipe covers Plex only. How the Jellyfin provider talks to Jellyfin (a maintained
library or focused `fetch` methods, as D12 does for Plex) isn't chosen; either way it sits behind the
same server-only provider contract as Plex (legacy spec §7.1) and uses the SSRF-safe fetch (D8).
Closes with the Jellyfin provider.

### D22. Translation library and message format

Which translation library (D21) and which Weblate-readable file format to use isn't chosen. One
candidate is Paraglide JS storing its messages as i18next JSON; gettext PO and XLIFF are others.
The choice must work with SvelteKit 3 on Bun, with server rendering, plurals and TypeScript 6.
Closes with the `i18n` module.
