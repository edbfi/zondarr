# Spec: zondarr

**Status:** the ground floor (skeleton) is specified here, approved by the orchestrator
(2026-10-18) and built. The capability map below is approved; module 1, `secrets`, is built
([SPEC-secrets.md](SPEC-secrets.md)).

## Objective

zondarr lets the owner of private Plex and Jellyfin servers invite people with a code and a link:
the invitee completes the owner's welcome steps and joins the servers, and the owner manages
invitations, members, servers and wizards from an admin console
([PRODUCT.md](../PRODUCT.md)).

**This spec covers only the ground floor:** an empty, production-shaped SvelteKit app that builds,
type-checks, tests, lints and serves on Bun, styled from the design tokens, with the edbfi Bun web
CI around it. It has no database, authentication, Plex, Jellyfin or product features. Its job is to
make the first module spec cheap to build: every later PR adds behaviour, not plumbing.

## Capability map

**Status:** approved by the owner (2026-10-24; shared rows aligned 2026-10-30). Module ids never
change. Each module gets its own `docs/SPEC-<id>.md`, which the owner approves just before it is
built.
Sources: [PRODUCT.md](../PRODUCT.md), [decisions.md](decisions.md) and the
[surface briefs](../.impeccable/surfaces/).

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
| 1 | `secrets` | **Built.** Encrypts stored secrets (media server API keys, two-factor secrets, the OIDC client secret) before they reach the database (D20, D25), and the secret wrapper that shows only a redaction marker and opens at one named call | — | — |
| 2 | `i18n` | The translation groundwork (D21) with Paraglide JS (D22): message files in English and Danish, choosing each request's language, the language switcher, formatting dates and numbers for the viewer's locale, and a check that every message exists in both languages | — | the language switcher in each shell |
| 3 | `setup` | Startup checks, database and migrations, settings, structured logging with redaction, security headers and CSP (ground-floor choice 3), the setup gate, the bootstrap token, printed to the console and never through the stored logs, and claiming the instance for its one owner. zondarr adds environment locks on settings and the referrer policy among the headers, and replaces `/healthz` with the fuller health of ground-floor choice 5 | `secrets`, `i18n` | first-run setup (no brief yet); `/healthz` |
| 4 | `sign-in` | Owner sign-in with username and password, signing the new owner in at the claim (D20), sessions, sign-out (POST only), rate limits on sign-in, the cross-origin check (it asks the browser, stores no address and takes `ORIGIN` as an optional override), app-named cookies that work over plain HTTP at home and behind an HTTPS proxy, password change, error pages, recovery (D20), and the admin shell. zondarr adds the lockout on sign-in and the origin test, which only diagnoses: it compares the address the browser uses with the `Host` the app receives and `ORIGIN` when set, suggests `ORIGIN=<address>` or the proxy line `proxy_set_header Host $http_host`, and saves nothing; its suggestion also shows on the claim and owner sign-in pages, so someone without a session can recover | `setup` | owner sign-in (no brief yet); the origin test's hint on the claim and owner sign-in pages; the admin shell; `/admin/settings`, which it builds first with the General, Account and About tabs; later modules add their tabs and sections; the password section of `/admin/settings` (Account) |
| 5 | `two-factor` | Optional but strongly recommended (D20): authenticator codes, backup codes and the challenge after every way of signing in (except the optional OIDC skip, D20), with replay protection and the attempt limit. Recovery turns it off. Adds the offer to first-run setup, right after the owner account is created and before any connection step, and the reminder in the admin shell while it is off | `sign-in` | the two-factor offer in first-run setup; the two-factor section of `/admin/settings` (Account); the reminder in the admin shell |
| 6 | `plex-provider` | The Plex provider (D12, D18): connection test, server info, libraries, the user list with relationship types, direct share, friend and home accounts, removal stepped by relationship, disabling as a share with no libraries (D23), library access, permissions and PIN sign-in. Reconciles shares by machine id and account id after every write | `setup` | — |
| 7 | `jellyfin-provider` | The Jellyfin provider (D19): connection test, server info, libraries, the user list with administrators flagged, create with password, delete, enable and disable, library access and permissions | `setup` | — |
| 8 | `servers` | Adding a server with the mandatory connection test and type detection, the list and detail, editing with a re-test that works with the stored key, deleting with defined cascade rules, the per-provider environment overrides, library sync, and the optional first-server step after `setup` and the two-factor offer | `sign-in`, `plex-provider`, `jellyfin-provider` | `/admin/servers` (no brief yet); the Servers tab of `/admin/settings` |
| 9 | `members` | Identities and their per-server users, the members list with search and filters, the detail with linked users, enable and disable (on Plex, a share with no libraries, D23), permissions loaded from the server, and delete stepped by relationship | `servers` | `/admin/members/[id]` |
| 10 | `wizards` | Wizards, steps, interactions and translations, the content allow-list, keyboard reordering, the preview, and the server-side step check: signed progress and completion tokens, the quiz cool-down and a timer started on the server. A disabled or empty wizard counts as none | `sign-in` | `/admin/wizards/[id]`; the wizard list (no brief yet) |
| 11 | `invitations` | Invitations with target servers, libraries, expiry, max uses, access duration and wizards; generated and normalised codes, the validation order, clear errors for max uses below the use count, the copy link, and the invitation expiry job | `servers`, `wizards` | `/admin/invitations` |
| 12 | `join` | The public join shell, code validation with its exact reasons, the server check, and the pre- and post-registration wizard stages, with rate limits on validation | `invitations`, `wizards` | `/join/[code]`, `/join/[code]/welcome` |
| 13 | `redemption` | Plex sign-in for invitees (opaque handles, one-time redemption tokens, the real reason when one is invalid), the Jellyfin account form, the reservation, creating each account once, rollback with the partial-success report, an idempotency key against double submits, the default permissions, the receipt, and the cleanup job for expired sign-in attempts | `join`, `members` | `/join/[code]/account`, `/join/[code]/complete` |
| 14 | `sync` | User sync (matched, orphaned, stale; dry run by default, import, relationship refresh), the media server sync job with per-server timeouts, retries and circuit breakers, sync runs, an interval that takes effect without a restart, and running it by hand | `members` | the Sync tab of `/admin/settings`; the sync panel on server detail; "Sync members" on `/admin/members/[id]` |
| 15 | `member-expiry` | The expiry policy (D23): the default in the settings and the override on each invitation, the job that applies it, and showing on each invitation what happens at expiry (PRODUCT.md) | `members`, `invitations` | a section of `/admin/settings`; the policy on the invitation editor and detail |
| 16 | `owner-plex-sign-in` | Linking the owner's account to their Plex account in the admin settings, after which "Sign in with Plex" signs them in as the owner, through two-factor when it is on (D20) | `two-factor`, `plex-provider`, `redemption` | the Plex section of `/admin/settings` (Account); the Plex button on owner sign-in |
| 17 | `oidc-sign-in` | Connecting one OpenID Connect provider (Authentik, Authelia, Pocket ID, Tinyauth and others) by its issuer, client id and secret, and linking the owner's account to it, after which it signs them in as the owner, and offering to skip `two-factor` when the provider's `amr` claim reports its own second factor (D20) | `two-factor` | the OIDC section of `/admin/settings` (Account); its button on owner sign-in |
| 18 | `logs` | The live log viewer: the in-memory buffer of recent entries, the stream with reconnects that don't repeat entries, filters, search and the detail panel | `sign-in` | `/admin/logs` (no brief yet) |
| 19 | `overview` | The owner dashboard: member, invitation and server counts, server health, pending invitations, recent activity, and a reminder while no server is connected | `servers`, `invitations`, `members`, `sync` | `/admin` |

Build order: `secrets` → `i18n` → `setup` → `sign-in` → `two-factor` → `plex-provider`,
`jellyfin-provider` → `servers` → `members`, `wizards` → `invitations` → `join` → `redemption` →
`sync`, `member-expiry`, `owner-plex-sign-in`, `oidc-sign-in`, `logs` → `overview`. A comma means
either order works. The first five are the opening every edbfi app shares (D20). The first of the
two providers adds the provider contract with its capability declarations (its Module notes) and the
SSRF-safe outbound HTTP (D8). `redemption` is the first time an invitee gets something they can
use, so everything before it is the shortest path there.

### Where modules live

Paths are under `src/lib/server/`, except those starting with `routes/` (under `src/`) or `lib/`
(under `src/`), and `hooks.server.ts` (`src/hooks.server.ts`). They follow the
[Code structure](../AGENTS.md#code-structure) layout:

| Module | Main homes |
|---|---|
| `secrets` | `security/secrets/` (key checks, keyring, cipher, `Secret`), `config/secret-key.ts`, `src/env.ts` and the `init` hook in `hooks.server.ts` |
| `i18n` | `messages/en.json` and `messages/da.json`, `project.inlang/` (Paraglide's settings), `lib/shared/i18n/` (formatting); `paraglideMiddleware` in `hooks.server.ts` |
| `setup` | `db/` (client, migrations, settings and owner schema), `config/`, `logging/`, `services/setup/`, `services/health.ts`, `security/bootstrap-token.ts`, `security/headers.ts`; `routes/setup/`, `routes/healthz/`, and the setup gate and the headers in `hooks.server.ts` |
| `sign-in` | `services/sign-in/` (sessions and their storage, recovery), `db/` session schema, `security/` (session-token and password hashing, rate limiting, the cross-origin check), `vite.config.ts` (SvelteKit's own form check off); the sign-in at the claim in `routes/setup/`, `routes/(admin)/` layout and sign-in page, `routes/(admin)/admin/settings/`, `lib/components/layout/` |
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
- `setup`: D15 (Drizzle and Turso pair) and the logging library half of D14.
- `sign-in`: how long an owner session lasts.
- `sign-in`: the password rules: the minimum length, whether a list of common passwords is refused,
  and how repeated failed sign-ins are slowed beyond the rate limits (backoff, or a lockout where
  the app's approved docs allow one). zondarr's row promises a lockout on sign-in: one that grows
  with repeated failures and ends by itself, never one that keeps the owner out until recovery.
- The first module with a background job closes the job half of D14: `sign-in` if its session
  cleanup is a job, otherwise `invitations`.
- `plex-provider`: D18, including whether Plex keeps a share with no libraries (D23).
  `jellyfin-provider`: D19.
- `servers`: what happens to an invitation whose only target server is deleted, since an
  invitation always targets at least one server.
- D13: `redemption`'s sign-in polling is the first JSON endpoint; its spec decides whether it needs
  a generated client. D17 stays open as an accepted limit.

### Left out on purpose

- Any role beyond the one owner, and admin management (PRODUCT.md, D20).
- Rotating refresh tokens, short-lived access tokens and the bearer header for scripts. D20's
  server-side sessions replace them, and no script needs the API.
- Owner sign-in with a Jellyfin account (owner decision, D20).
- Signing in through a reverse proxy's headers (D20): `oidc-sign-in` covers the same identity
  providers.
- Connecting Weblate (D21): later work, outside this map. The message files are ready for it.
- Checking that a Plex sign-in belongs to the owner of a configured Plex server. The signed-in owner
  links their Plex account themselves (D20), and zondarr may have several Plex servers or none.
- Per-invitation permissions: the legacy app's field was never used, and redemption applies the
  default set.
- The debug mode's auth bypass, test-only PIN endpoint and API documentation pages: development
  tooling, not product.
- Email, notifications and a member portal (PRODUCT.md).
- **The container image's first start** (deferred: a note, not a design). It is specified and
  built only when Zondarr is first tested through its image (`edbfi/zondarr-docker`); building
  images through GitHub, including the nightly build of `main`, is a later goal. The intent, with
  the app's code unchanged: when `ZONDARR_SECRET_KEY` and `ZONDARR_SECRET_KEY_FILE` are both unset
  or empty, the image's setup script points `ZONDARR_SECRET_KEY_FILE` at `/config/secret.key`
  whenever that file exists. It creates the file first (a random 32-byte key in standard base64,
  written atomically, mode 0600, owned by the app's user) only when `/config/data` is empty and
  nothing shows an older install (such as the previous app's secret or database variables; the
  image's own defaults don't count, and the exact checks are decided with the image); otherwise it
  creates nothing, and the app stops with its own key error. An operator's own key or secret file
  always wins, and the README tells the operator to keep a copy of the key file. Nothing the v0.1.x
  images left is ever used as a key; how such an install upgrades is decided with the image.

### Surfaces with no brief yet

First-run setup, owner sign-in, `/admin/servers`, the wizard list and `/admin/logs` are needed (all
are in PRODUCT.md's admin shell, with their behaviour in the Module notes) but have no brief. The
`/join/[code]/account` brief covers only Plex; the Jellyfin account form joins it. Each gets its
brief before its module is specced.

### Module notes

What a capability-map row commits to in more detail than a clause fits, carried over from the legacy
app and adapted to the decisions. It is behaviour to keep unless the module's approved spec or a
decision changes it. Layout, placement, visuals and exact wording are not behaviour: where a note
describes them, DESIGN.md and the surface's brief win, and for a surface with no brief yet the note
is only a starting point for that brief. Each block moves into its module's `SPEC-<id>.md` when that
module is specced. Rate limits are listed once, under `sign-in`. `i18n`, `setup`, `sign-in` and
`two-factor` are shared with the other edbfi apps (D20): a bullet or clause marked "(zondarr)" is
this app's own, and the rest is the shared wording; a "(zondarr)" mark inside a bullet covers the
rest of that bullet, and "(zondarr: …)" only its own parentheses.

#### i18n

- A number in a message that states how the app behaves (a limit, a duration, a count) is passed in
  as a parameter from the constant the logic uses, never written into the text, so the copy can't
  drift from the behaviour.

#### setup

- **The claim** is a POST, cross-origin-checked like any other (`sign-in`), and it stores no
  address. It needs a valid bootstrap token and the browser's address (`sign-in`). Using up the
  token and creating the owner are one atomic step, and the owner session it starts follows
  `sign-in`'s cookies. (zondarr) The legacy app's ten-minute, single-use, same-site-strict browser
  authorisation from its setup link is not kept: the token is checked when the claim is submitted.
- **The referrer policy,** among the security headers, is `same-origin` or
  `strict-origin-when-cross-origin`, never `no-referrer` (which makes browsers send `Origin: null`
  on the app's own form posts). (zondarr) On the join page this replaces the legacy app's suppressed
  referrer and still keeps the invitation code from other sites: `same-origin` sends them no
  referrer, and `strict-origin-when-cross-origin` only the app's address, never the path.
- **Strict transport security** (zondarr: when the headers include it) is sent only over HTTPS
  (known when `ORIGIN` is `https`, or when the browser sent `Sec-Fetch-Site` to a host that isn't
  loopback, since browsers send it only to HTTPS and loopback addresses).
- **The setup gate.** Until first run is complete, every page except static assets, the claim,
  sign-in and first run's own helpers sends the browser to the current first-run step. The server
  keeps one current-step pointer: the browser can't skip ahead, each step's action checks that it is
  the current step, and a step that offers Previous only moves the pointer back. Only the last
  step's action completes first run. (zondarr) First run is the claim, the two-factor offer
  (`two-factor`) and the optional first server (`servers`), each later step skippable; after an
  interruption it resumes at the current step.
- **The bootstrap token** (zondarr) is printed with the setup URL and never served over the network.
  The claim page has a field for the token and says where to find it: the container's logs, or the
  console when zondarr runs directly.
- **The owner's username** (zondarr) is 3–32 characters: lowercase letters, digits and underscores,
  starting with a letter.
- **Records** (zondarr) have random ids and created and updated times, stored in UTC; a time given
  without a zone is UTC. Nothing is soft-deleted: disabling is the only reversible way to switch
  something off.
- **Environment locks** (zondarr; obzorarr is the reference, AGENTS.md Shared groundwork). A setting
  the environment supplies wins: its field is read-only and says that the deployment's configuration
  owns the value. zondarr's are the sync interval (`sync`) and each provider's server address and
  key (`servers`).
- **Logging** (zondarr). Every error response carries a correlation id that the matching log entries
  carry too, and an upstream failure shown to the owner names it. A request's log entry records its
  method, path, content type and parameters, redacted like every entry, never its body, headers or
  cookies.
- **Startup and shutdown.** Startup runs once, before any request is served: migrations (D5), then
  each module's startup work, then starting the jobs. Shutdown stops the jobs, flushes the logs and
  drains open requests and live streams for a bounded time, then exits even if an upstream call is
  still outstanding. Streams it closes end cleanly, so browsers reconnect, and a hang-up counts as a
  stop. The environment sets the drain time (default 30 seconds, kept below the container's stop
  timeout). (zondarr) Jobs get up to ten seconds to finish. The environment also sets the idle
  timeout (default 10 seconds, live streams exempt) and the request body limit (default 512 KB).

#### sign-in

- **SvelteKit's own form check is off:** `sveltekit({ csrf: { trustedOrigins: ['*'] } })` in
  `vite.config.ts` (SvelteKit 3 takes its options in the `sveltekit()` call, with no `kit:`
  wrapper). Remote functions stay off. A config test asserts both, so SvelteKit's only remaining
  check before `handle` is the remote-function one, which nothing uses. The cross-origin check
  replaces SvelteKit's form check.
- **The cross-origin check** asks the browser, so the app doesn't need to know its own address and
  stores none. It runs first in `handle` for every method except GET, HEAD and OPTIONS, and for
  every content type (form, JSON, multipart, `text/plain`, empty). Internal `event.fetch`
  subrequests (`event.isSubRequest`) skip it.
  - An `Origin` header, whenever it is present, must parse as one bare `http` or `https` origin;
    `null`, a malformed value or several values are refused. This applies on every branch below.
  - With `ORIGIN` set, a present `Origin` must equal `ORIGIN`, compared as parsed origins. Without
    `Origin`, `Sec-Fetch-Site` must be `same-origin` or `none`.
  - With `ORIGIN` unset, a present `Sec-Fetch-Site` passes only as `same-origin` or `none`
    (`same-site` and `cross-site` are refused). Otherwise `Origin`'s host and port must equal the
    `Host` header, with default ports normalised. Browsers send `Sec-Fetch-Site` only to HTTPS,
    `localhost` and loopback addresses, so over plain HTTP outside loopback every browser gets
    this comparison.
  - A request with neither `Origin` nor `Sec-Fetch-Site` doesn't come from a browser. It passes only
    on an explicit list of machine routes (zondarr: none, so it refuses every such request): the
    API-key endpoints and other machine routes the app's approved docs already name, each with the
    credentials those docs require. The session cookie is never honoured on it: such a request that
    carries only a session cookie gets a 403.
  - A refusal is a 403 with the app's own "Access denied" page, or a JSON error for JSON callers,
    with the security headers and in the viewer's language.
- **The browser's address** is `ORIGIN` when it is set, and otherwise the validated `Origin` of the
  POST that passed the cross-origin check. It decides the cookies' `Secure` flag, the OIDC
  `redirect_uri` and, where the app has Plex sign-in, Plex's forward URL. Every POST that sets or
  deletes a cookie needs it, such as the claim, sign-in, the two-factor challenge, recovery,
  sign-out and the start of OIDC sign-in (and of Plex sign-in, where the app has it): when a
  browser stripped `Origin`, they get a 403 that says so (the "Access denied" page, or a JSON
  error for JSON callers). OIDC sign-in (and Plex sign-in, where the app has it) keeps the address
  in the flow's state. The OIDC callback address is saved when the owner configures OIDC, and must
  match. Links shown on GET pages for copying, such as the OIDC callback to register (zondarr: and
  invite links), are built in the browser from the address the user is on, or from `ORIGIN` when it
  is set. App code never uses `event.url.origin` or `event.url.protocol` for security, cookies or
  rendered URLs, which a test that searches the code enforces, and redirects stay relative.
  (zondarr) Plex sign-in starts from the browser for the invitee on the join page (`redemption`)
  and for the owner when linking in `/admin/settings` (Account) or signing in on owner sign-in
  (`owner-plex-sign-in`); each follows this rule.
- **The address hint:** when `ORIGIN` is set and doesn't match the address the browser is on, or
  when `ORIGIN` is unset and that address's host and port don't match the `Host` header, the claim
  and owner sign-in pages suggest setting `ORIGIN=<that address>` (or removing a wrong `ORIGIN`) or
  adding the proxy line `proxy_set_header Host $http_host`, so someone without a session can
  recover. (zondarr) The origin test adds it, with the check behind it.
- **`ORIGIN`** is optional and never required. It is plain `ORIGIN`, not an app-prefixed name (an
  app prefix would mean setting adapter-bun's `envPrefix`, which would then reject the master key's
  variable). When set, it must be a bare `http` or `https` origin (a trailing `/` is fine; no path,
  query, fragment or credentials), compared as a parsed origin, or startup stops with an error that
  doesn't echo the value. adapter-bun 1.0.0 ignores `ORIGIN`; from 1.0.1 a set `ORIGIN` also
  corrects SvelteKit's `event.url`, and an empty `ORIGIN=""` throws with the value in the message,
  so the container image's entrypoint unsets an empty `ORIGIN` and its templates leave it out (the
  image's work, not this repo's). (zondarr) It is an environment value, never a stored setting:
  there is no console setting for the environment to lock, and the settings page only shows it,
  read-only. It takes the place of the legacy app's public origin. The legacy app's trusted origin,
  with its first-run Test Origin, Save and Skip, and its secure-cookies setting are not kept,
  because the cross-origin check stores no address and cookies follow the browser's address.
- **When `ORIGIN` or a proxy fix is still needed:** behind a proxy that rewrites `Host`, over plain
  HTTP for every browser, and over HTTPS only for browsers without `Sec-Fetch-Site` (Safari before
  16.4, Firefox before 90, Chrome before 76). The proxy fix is `proxy_set_header Host $http_host`
  (not `$host`, which drops a non-default port). Remote functions would need it too; they stay
  off.
- **Accepted residual risks.** Over plain HTTP, the `Origin` and `Host` comparison can't tell `http`
  from `https`, which is harmless on a port that speaks only HTTP; over HTTPS it affects only
  browsers without `Sec-Fetch-Site`, and only against a network attacker, and HSTS or `ORIGIN`
  closes it. DNS rebinding reaches only actions that need no sign-in, because cookies don't follow
  a rebind, and those are gated by a console token or rate-limited (zondarr: the join flow's
  actions also need a valid invitation code).
- **Tests:** the cross-origin check is one pure module, unit-tested against a matrix of headers and
  copied to each app as D20 shares the opening modules. One Playwright test against the built server
  (`bun ./build`) checks that a cross-site form POST is refused and that a same-origin POST carrying
  no `Sec-Fetch-*` headers passes, both on `localhost` and on a plain-HTTP host name that isn't
  loopback (such as Chromium's `--host-resolver-rules="MAP app.test 127.0.0.1"`).
- **Cookies:** session cookies are named after the app (zondarr: `zondarr_session` for the owner
  session), because cookies ignore ports and apps on one address would otherwise sign each other
  out. They are host-only, `HttpOnly` and `SameSite=Lax`. Every cookie is `Secure` exactly when the
  browser's address is `https`, so a plain-HTTP install at home still works. Every cookie write and
  deletion sets `secure` explicitly (SvelteKit's default is `Secure` on every host but `localhost`),
  and a deletion whose scheme isn't known uses `secure: false`, which works over HTTP and HTTPS.
- **A wrong address never locks the owner out.** No stored address can stop password sign-in: a
  wrong `ORIGIN` is fixed or removed, then the app restarts. The OIDC callback address is stored,
  so OIDC may need registering again after a move, but password sign-in always remains (D20).
- **Who needs a session** (zondarr). Every page and endpoint needs the owner's session except the
  join flow (`join`, `redemption`), the claim, owner sign-in with its two-factor challenge and
  recovery, and `/healthz`. Someone without a session who opens an owner page goes to owner sign-in.
  `/` sends the owner to `/admin` and anyone else to owner sign-in, and a signed-in owner who opens
  owner sign-in goes to `/admin`.
- **Rate limits** apply per client address. The client address comes from the connection, or from a
  header and a proxy depth (default 1) set in the environment, which should be set only when every
  request passes through that proxy. (zondarr) Signing in, code validation on the join page (`join`)
  and starting a Plex sign-in from the join page (`redemption`) are limited.
- **Signing in** (zondarr). A wrong username and a wrong password give the same message. Passwords
  are hashed with a memory-hard function and hashed again at the next sign-in when its parameters
  change.
- **Sessions** (zondarr). Every request checks its session in the database, so a session that ends
  stops working at once. Sign-out ends only the session it comes from. Changing the password needs
  the current one and ends every other session.
- **Errors:** an unexpected error is logged and the user sees "Something went wrong. Try again.";
  expected errors pass through in plain words (zondarr: such as a taken username, an unreachable
  server or an invitation that is no longer valid); stack traces, file paths and database text never
  reach the browser.
- **The About tab** (zondarr) of `/admin/settings` shows the owner zondarr's version, the Bun
  version, the database engine and the operating system. No public page or endpoint shows them
  (D24).

#### two-factor

This block is zondarr's own: obzorarr, the reference, had nothing to carry for `two-factor`.

- **Codes** are six digits for 30-second steps, with one step of drift accepted either side. The
  authenticator shows the product name as the issuer and the owner's username as the label. Once a
  code is accepted, no code from that step or an earlier one is accepted again.
- **Turning it on** shows a QR code and the key to type in (hidden until asked for), then asks for a
  code. Confirming turns two-factor on and issues ten single-use backup codes in `XXXX-XXXX` form,
  which replace any shown before; the owner can copy them or download them as text.
- **Backup codes** ignore case and spaces and each works once. New ones need a valid code.
- **Failed attempts:** five block verification until fifteen minutes after the last failure; a
  success resets the count.
- **The challenge.** When two-factor is on, a correct password, or a Plex or OIDC sign-in (D20),
  opens a five-minute challenge bound to a single-use nonce instead of a session. The code is
  checked before the nonce is used up, so a typo doesn't end the challenge, and a passed challenge
  can't be replayed. A backup code works in place of a code.
- **Turning it off** needs the password and a valid code, and clears the secret and the backup
  codes. Recovery turns it off too (D20).

#### plex-provider

- **The provider contract** comes with whichever provider is built first (D12, D19). Each provider
  declares its display name, the help for finding its API key, the environment variables that
  override its address and key, its capabilities, the permissions it supports, its join style (sign
  in with Plex, or a username and password) and whether it offers PIN sign-in. Every client can test
  the connection without throwing, read the server's name and version, list libraries and users,
  create and delete a user, enable and disable one, set library access, update permissions and
  remove a share. The permission vocabulary is download, stream, offline sync and transcode; each
  provider maps what it can and ignores the rest. Screens are built from the declarations, never
  from a product's name.
- **Requests** to Plex time out after 30 seconds by default (at least 5, set in the environment).
  Errors are classed as already a friend, username taken, not found, invalid token, timeout,
  connection, rate-limited (temporary), permission denied, or other.
- **Adding a member.** With their email and their own Plex sign-in (the join page always asks for
  it): a direct share of this server with the chosen libraries and no friendship, after removing any
  relationship left from an earlier invitation; then, in the background, the pending share is
  accepted on their behalf (a few tries) and stale pending invitations to that email are cancelled.
  The type is shared. With an email only: a friend invitation the invitee accepts, and if Plex says
  they are already a friend, the orphaned relationship is removed and the invitation tried once
  more. The type is friend. With no email: a managed home user.
- **Removing a member** finds them by their numeric Plex id, removes this server's share first, then
  the home user or the friendship, and succeeds if either removal worked.
- **Permissions:** only downloads, as Plex's "allow sync". Libraries are set when the server is
  shared.

#### jellyfin-provider

- **Creating a member** creates the user by name, then sets the password; an "already exists" reply
  means the username is taken. Library access turns off "all libraries" and sets the enabled list.
  Enabling and disabling flip the account's disabled flag. Permissions: download, stream, offline
  sync and transcode.
- **Errors:** timeouts, DNS failures, refused connections, 5xx and unauthorised replies are the
  server's failures; anything else is a client error.

#### servers

- **Adding a server** (also first run's optional step): a name, the type (one of the registered
  providers), the address (a full `http` or `https` URL) and the API key, with the provider's help
  on where to find it. When the environment holds a provider's complete address and key, the form
  offers them, and choosing them shows those fields read-only.
- **The connection test** must succeed before the server can be added. Changing a connection field
  clears its result, and a late result for old fields is dropped. With a type chosen, only that type
  is tried; without one, every provider is tried at once, ten seconds each, and the first success
  wins and sets the type (Plex is the first guess). Success shows the detected product and the
  server's name and version (with D24's warning for an untested version); a failure is a message,
  never an error page.
- **Addresses** (D8) are `http` or `https`. Private, loopback, link-local and similar addresses, and
  host names that resolve to them, are allowed by default, because self-hosting is the normal case;
  the environment can refuse them for public hosting.
- **On add,** the key is encrypted (`secrets`) and two best-effort syncs run at once, libraries and
  then a user import, recorded as onboarding runs (`sync`); their failure doesn't fail the add.
  Adding the first server completes first run's server step.
- **Environment overrides.** Per provider type, an address or a key in the environment overrides the
  stored one for every server of that type, field by field, and those fields are locked. No key,
  stored or from the environment, reaches the browser: the provider detection sends only whether
  each is set, and a key shows only as a masked receipt (DESIGN.md Components).
- **Detail** shows the server's information, its libraries (name, type, id on the server), its sync
  state (`sync`) and the actions: sync users, sync libraries, reset the circuit breaker (only while
  it is open) and delete. It refreshes every 15 seconds while open.
- **Library sync** matches libraries by their id on the server: new ones are added, changed names or
  types updated (counted only when something changed) and missing ones removed, with any
  invitation's links to them. It reports the total, added, updated and removed.
- **Deleting a server** deletes its libraries, its sync runs and the local member records on it, and
  invitations lose their links to it and its libraries; the accounts on the media server stay, and
  the confirmation says so.
#### members

- **Identities and users.** An identity is one person (display name, optional email, optional
  expiry, enabled) with one or more users, each one account on one server (its id and username
  there, the invitation it came from, the Plex relationship type, an optional expiry, enabled). A
  remote account is one user per server, and the same id may exist on other servers; usernames are
  unique per server too. Deleting an invitation keeps its users and clears their link; deleting an
  identity's last user deletes the identity.
- **The list** has no create action: members come only from joins and imports. It is paginated (50 a
  page by default, at most 100), searched on the server (username, id on the server, display name,
  email, server name and type, and invitation code), filtered by server, invitation, enabled and
  expiry, and sorted by created date, username or expiry, so it stays usable beyond a thousand
  members. Like every list, it keeps its filter, sort and page in the address, and a new filter goes
  back to page one.
- **Labels,** in priority order: Disabled, Expired, Expiring soon (within seven days), Active. A
  Plex member's relationship type (home, shared or friend) shows as text, and is unknown, with a
  hint to run a sync, until a sync finds it.
- **Detail** shows the user's facts, the permissions their server supports, read from the server
  (row 9), each saved on the server at once and put back on failure, and locked while the user is
  disabled; then the identity, the source invitation and the identity's other users.
- **The server comes first.** Enabling and disabling change the media server, then the local record
  only on success (on Plex, D23). Permissions live only on the server; zondarr stores none and only
  edits them. Deleting removes the account on the server, then locally; if the server says it
  doesn't exist, the delete is refused unless forced, which removes only the local record. No single
  action removes a person from every server.
- **Deleting a Plex member** goes by relationship: a shared member first loses the share (libraries
  unshared, friendship kept, now a friend), then the friendship; a friend has that one step; a home
  user is removed from the Plex Home; any other user has one step that covers the server and the
  local record.

#### wizards

- **A wizard** is a named, reusable list of steps (a name, a description of up to 2,000 characters,
  enabled), attached to any number of invitations before registration, where it must be finished
  before the account exists, or after, where it can be cancelled. Steps are added once the wizard is
  saved. Their positions run from 0 with no gaps, renumbered when a step is deleted or moved.
  Deleting a wizard deletes its steps and clears invitations' links to it.
- **A step** has a title, formatted content, a primary language (English by default) with any
  translations, and zero or more interactions, at most one of each type, all of which must be
  completed.
- **Editing:** turning an interaction on or off saves at once; its settings are checked as they're
  typed and saved shortly after a valid change. The preview shows the invitee's view exactly and
  records no progress.
- **Content** renders through one allow-list everywhere (the editor's preview, the admin preview and
  the join page): headings, paragraphs, emphasis, links, lists, quotes, code, images and rules only.
  Scripts, styles, frames, embedded objects, event handlers, script-scheme links and tables are
  stripped, and every link opens in a new tab with no opener and no referrer. It is tested against
  generated hostile input.
- **Translations** are keyed by two-letter language codes, chosen from a list with native names and
  English first. Saving a step replaces its whole set, and a translation can swap places with the
  primary. The invitee gets a language switch on a step with more than one language, remembered for
  the visit, and a step without that language falls back to its primary.
- **Interactions** and when each is complete:
  - click confirmation (button text, default "I understand"): acknowledged;
  - timed wait (1–300 seconds, default 10): completes itself once that much real time has passed
    since the server first served the step (row 10), through reloads, background tabs and locked
    screens;
  - terms (checkbox label, default "I accept the terms of service"): accepted;
  - text input (a required label, a placeholder, required by default, a minimum and maximum length
    with the minimum not above the maximum): not blank when required, and within the lengths;
  - quiz (a question, 2–10 options and the correct one): the correct option chosen. The correct one
    never reaches the browser, and a wrong answer waits 3, then 5, 7, 9 and 10 seconds before the
    next try.
- **The order is checked on the server.** Each step is checked before the invitee moves on. The
  first needs nothing; every later one needs a signed progress token, at most an hour old, for the
  same wizard, listing exactly the earlier steps in order. Passing a step returns the extended
  token, and passing the last returns a signed completion token, valid for an hour, that
  `redemption` accepts. Editing a wizard's steps invalidates the tokens in flight, going back clears
  the current and later steps, and the submitted interactions must match the step's exactly.

#### invitations

- **An invitation** has a code, an optional expiry, optional maximum uses with its use count, an
  optional access duration in days, enabled, its target servers (at least one, each existing and
  enabled), its allowed libraries (on those servers; none chosen means all of them) and optional
  pre- and post-registration wizards (enabled ones). The use count never exceeds the maximum. People
  who joined with it keep their access when it is deleted, and the confirmation says so.
- **Codes.** A custom code is 1–20 letters or digits. A generated one is 12 capital letters and
  digits without 0, O, I and L, from a cryptographic random source, tried again on a collision. A
  duplicate is reported plainly. Codes are normalised the same way when created and when looked up
  (row 11).
- **Creating:** an expiry must be in the future; maximum uses and the access duration are positive
  whole numbers, and empty means unlimited and permanent.
- **States** are computed, never stored. Active means enabled, not past its expiry and under its
  maximum; remaining uses never go below zero and are absent when unlimited; pending means active
  and never used. Labels, in priority order: Disabled; Used up (capped with none left); Expired
  (inactive because of its date, as the server decides); Limited (three or fewer uses left); Active.
- **The validation order,** for the join page and redemption: not found, expired, disabled, used up.
  Expiry comes before disabled because the expiry job disables expired invitations, and the invitee
  should see the real reason. Validating never uses a use.
- **The expiry job** disables every enabled invitation whose expiry has passed. It runs hourly by
  default (at most every minute), an interval set only in the environment.
- **Editing** changes enabled, the expiry, maximum uses, the access duration, the targets, the
  libraries and both wizards, at once; the code, the use count and the creation time never change. A
  field left out stays as it is, and clearing the expiry, a limit or a wizard means none. The
  libraries are checked again against the new targets.
- **The list** is paginated as `members`' is, filtered by enabled and by expired or active, and
  sorted by created date, expiry or use count, either way. Copying the invite link, the join address
  for the code, is the main way to share an invitation.

#### join

- **Progress** for each code (the wizard stages done, the registration's result) is kept per browser
  tab, so a refresh doesn't lose it.
- **Validation** runs on load. An invalid code shows its exact reason: it doesn't exist, the owner
  disabled it, it expired, or it is used up. A valid one shows the access duration, the target
  servers by name and type only, the allowed libraries (or all of them), that welcome steps come
  first when a pre-registration wizard is attached, and Continue.
- **The server check:** Continue probes each target server at once, ten seconds each. Unreachable
  servers are listed by name, with Retry and Continue anyway. If the code has become invalid
  meanwhile, the invitee is told; any other failure of the check lets them go on.
- **Wizards:** cancelling the pre-registration wizard goes back to the validation and clears the
  progress; cancelling the post-registration one goes to the receipt, since the account exists.

#### redemption

- **Registration** follows the targets' join style. For Jellyfin: a username (3–32 characters:
  lowercase letters, digits and underscores, starting with a letter), a password (8–128 characters,
  which can be shown) and an optional email. For Plex: sign-in with Plex. An invitation with both
  uses the Jellyfin form and still needs the Plex sign-in for its Plex targets. The Jellyfin
  password goes only to Jellyfin; zondarr never stores it.
- **Plex sign-in.** The server asks Plex for a PIN (retrying transient failures) and keeps the
  attempt under an opaque random handle for ten minutes, so Plex's ids never reach the browser; it
  returns the handle, Plex's sign-in link and the expiry. The page opens the link in a popup and
  checks the handle every two seconds, showing that it is waiting and when checks are missed, with a
  way to open Plex again and Cancel; no PIN is shown. On success the server reads the member's email
  and returns it with a one-time redemption token; the Plex token never reaches the browser and is
  wiped once exchanged. The page shows the email it signed in with and makes a username from it
  (lowercased, starting with a letter, only letters, digits and underscores). An expired sign-in can
  be tried again, and a job deletes expired attempts. The mechanics follow obzorarr's Plex sign-in,
  the reference (AGENTS.md Shared groundwork), and `sign-in`'s rule for the browser's address.
- **Redeeming,** in this order:
  1. exchange the redemption token, if given, for the Plex token and email, atomically and once;
  2. reserve one use atomically, only if the invitation is still enabled, unexpired and under its
     cap; a failed reservation reports why, and a valid-looking invitation that couldn't be reserved
     is used up, because another join took the last place;
  3. with a pre-registration wizard, require its signed completion token for that wizard, at most an
     hour old;
  4. for every Plex target, require a Plex token from Plex sign-in (a redemption token is bound to
     its provider);
  5. refuse a username that already exists locally on any target;
  6. create the account on each target, one after another, with that server's libraries, retrying
     only the connection, never the create;
  7. set the expiry from the access duration on the identity and each user;
  8. remove any stale local record of the same account on the same server (from an import or an
     earlier invitation), deleting an identity left empty;
  9. create the identity (display name the username; the email from the form, else from Plex, else
     the first a server reported) and one user per server, linked to the invitation;
  10. then, in the background, apply library restrictions (not for Plex friend invitations, which
      set them when inviting) and the default permissions: streaming and transcoding on, downloads
      and offline sync off. Failures here are only logged, because the member already has access.
- **A failure after the reservation** rolls back the local transaction, which releases the use and
  leaves the redemption token usable, and deletes, best effort and one by one, every account already
  created on other servers. The invitee sees the cause (username taken, server unreachable,
  invitation no longer valid, invalid input, or a general failure), the failed server's name, which
  accounts had been created, and a way to try again from the right form.

#### sync

- **User sync** compares each server's accounts with the local users by their id on the server:
  matched, orphaned (only on the server) and stale (only local). Run by hand it is a dry run by
  default that changes nothing and reports the usernames it would import and the stale ones. A real
  run imports each orphan as a new identity (display name the server's username, the server's email
  if known, no expiry, no invitation) and, for matched users, refreshes the Plex relationship type
  and fills in a missing identity email without overwriting one. It never changes whether a user is
  enabled and never deletes; running it twice changes nothing. Jellyfin administrators are imported
  and flagged (row 7).
- **The sync job** runs every 15 minutes by default (at most every minute), first 15 seconds after
  start so it doesn't hold up startup. For each enabled server it runs library sync, then user sync
  with import.
- **Per server,** each phase has a time limit (default 5 minutes) and a few retries (default 2) with
  exponential backoff from 2 seconds and jitter, honouring the server's retry-after hint. Permanent
  failures (invalid token, user not found, username taken, permission denied, invalid input) and
  unknown errors are never retried. A circuit breaker per server covers both phases: after 3
  failures in a row it opens and skips the server, recording each skip as a failed run with the
  reason; after the recovery period (default 5 minutes) it lets one try through, and a success
  closes it. Its state is in memory (D4) and resets on restart, and the owner can reset it from the
  server's page. The environment sets these values within bounded ranges, and a value out of range
  stops startup.
- **Sync runs** record each run: the server, libraries or users, automatic, manual or onboarding,
  success or failure, start, finish and error. Every automatic, onboarding and real manual run
  writes one, they feed `overview`'s recent activity, and they go with their server. An unreachable
  server is skipped and recorded, and a missing email is filled in by a later sync.
- **The sync panel** on server detail shows, for libraries and for users, the next scheduled run, a
  run in progress, the last completed one and the breaker's state (open with its failure count,
  recovering, or recent failures).

#### logs

- **The buffer** keeps the last 5,000 entries in memory, lost on restart. A new viewer receives up
  to the 500 most recent matching entries, then new ones as they come. A heartbeat keeps the stream
  open, the server closes it after 30 minutes, and the viewer reconnects without repeating entries.
  The browser keeps about 2,000 entries, and the list stays fast with thousands.
- **The viewer** can pause (entries keep collecting), filter by minimum level (with the error and
  warning counts) and by source, search, clear, and open an entry's detail with the whole entry and
  a way to copy it as structured text; the arrow keys move the selection. It follows the newest
  entry until the owner scrolls up, then offers to jump to the latest.
- The stream's own requests aren't logged, so it can't feed itself.

#### overview

- **The counts:** invitations, with how many are active; active members out of the total; servers,
  with how many are enabled; and pending invitations (active and never used).
- **Recent activity** is the ten newest of: a member joined, an invitation was created, a sync
  finished, a server was added. The page doesn't refresh itself.

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
- SvelteKit 3 exposes only the environment variables declared in `src/env.ts`.
- Tools run under Bun with `--bun`; a lifecycle script (`prepare`) calls each bin as
  `bun --bun <bin>`, because `bun ci` doesn't apply `--bun` to lifecycle scripts.
- Bun blocks `@parcel/watcher`'s install script (it builds with Node); Panda works without it.

## Commands

| Command | Does |
|---|---|
| `bun ci` | frozen install; `prepare` runs `svelte-kit sync` and Panda codegen |
| `bun run --bun dev` | Vite dev server; needs a key in `.env` or the environment, and without one every request fails with the key error |
| `bun run --bun build` | production build through adapter-bun into `build/`; needs no key and never embeds one |
| `bun run --bun preview` | runs the built server (`bun ./build`; `PORT`, default 3000, and `HOST`); without a valid key it exits before listening |
| `bun run --bun check` | `svelte-kit sync`, Panda codegen, then `svelte-check` failing on any error or warning |
| `bun run --bun test` | Vitest unit tests, once (no watch) |
| `bun run --bun smoke` | Playwright e2e: the browser smoke test and the startup tests, with a key it generates, never a developer's `.env` or exported key; it starts the built server, so `build` comes first, and Chromium comes from `bunx --bun playwright install chromium` |
| `bun run --bun lint` | `biome ci`, read-only; `biome.json` lists the file extensions Biome checks |
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

- **Unit (Vitest, `node` environment):** the `/healthz` handler (status 200, body `ok`,
  `cache-control: no-store`) and the `secrets` module (`config/secret-key.test.ts`, and
  `key-text.test.ts`, `keyring.test.ts`, `cipher.test.ts` and `secret.test.ts` in
  `security/secrets/`, under `src/lib/server/`). Component tests use happy-dom when components
  exist; never jsdom.
- **e2e (Playwright, Chromium, under Bun):** against the built adapter-bun server, with a master key
  Playwright generates for each run, so CI needs no stored secret.
  - `smoke.test.ts` checks that `/` returns 200, shows the placeholder heading, hydrates (it waits
    for the `data-hydrated` attribute the root layout sets when mounted), applies the Panda
    background token and `h1` text style and logs no console errors, and that `/healthz` returns
    `ok`.
  - `secret-key.test.ts` checks that the built server refuses to start without a valid key.
- prek runs the unit tests (`tests` hook); CI's `smoke` job builds with no key and runs `smoke`.

## CI and repo tooling

zondarr is a Bun web repo with edbfi-ci's Bun web templates:
- `.pre-commit-config.yaml`: Biome, `biome-migrate`, `check-peers`, the `tests` hook, plus a
  `check` hook (`bun run --bun check`), keeping the vendored-skill exclusions and the `docs-set`
  hook.
- `.github/workflows/ci.yml`: `checks` (prek), `smoke` (Chromium install, build, smoke) and `audit`
  (outside PRs); `checks` and `smoke` sit behind `ci-ok`, every job that installs runs with failing
  `node`, `npm` and `npx` on `PATH`, and the weekly run is `2 4 * * 0`.
- `.github/dependabot.yml` covers `github-actions`, `pre-commit` and `bun`, and
  `.github/workflows/biome-migrate.yml` applies Biome migrations and formatter output to
  Dependabot's Biome PRs.

## Boundaries

- **Always:** Bun with `--bun` for every tool; tokens only through Panda; keep SvelteKit's
  configuration in the Vite plugin; prek green before each commit.
- **Ask first:** any dependency not in the tech stack table; any change to `biome.json` (it is
  shared by the five rewrite apps); any CI shape that differs from the edbfi-ci template.
- **Never:** a database, authentication, Plex, Jellyfin or any product feature before its module's
  approved spec builds it; a second styling tool or primitive library; Node, npm or npx anywhere,
  including CI.

## Success criteria

1. A fresh clone passes `bun ci`, `bun run --bun check` (zero errors and warnings), `bun run --bun
   test`, `bun run --bun build`, `bun run --bun smoke` and `prek run --all-files --hook-stage
   manual`, with no Node on `PATH`.
2. The built server (`bun ./build`) serves `/` with the placeholder page and `/healthz` with `ok`
   when started with a valid key.
3. `panda.config.ts` holds every design token; the seed token files are gone, and nothing in `src/`
   uses a raw colour, size or font value.
4. Only folders with real files exist; `#lib` resolves in app code, tests and `svelte-check`.
5. CI on the PR runs `checks`, `smoke` and `ci-ok` green; `audit` runs outside PRs.

## Ground-floor choices

Choices 1–3 were settled for the first rewrite app's skeleton and are reused here, since zondarr's
design doesn't call for anything different; choices 4 and 5 are zondarr's own.

1. **Fonts.** DESIGN.md wants DM Serif Display, Outfit and IBM Plex Mono bundled locally (the legacy
   app loaded them from a hosted service). The skeleton defines the font tokens with system
   fallbacks; the first surface adds the font files (a dependency the owner approves then).
2. **Ark UI before its first use.** The skeleton installs `@ark-ui/svelte`, so the Panda and Ark
   pairing and `check-peers` are settled early; the first `ui/` wrapper comes with the first surface
   that needs one.
3. **Security headers and CSP.** The legacy app's join page suppressed the referrer; the rewrite
   keeps the invitation code out of other sites' referrers with a policy that still lets the app's
   own form posts carry `Origin` (`setup`'s Module notes). Security headers, the referrer policy and
   a CSP belong to the first module that serves real pages (`setup`, whose claim page comes before
   admin sign-in and the join flow), not the skeleton.
4. **Where the logo lives.** SvelteKit serves static files from `static/`, so the logo is
   `static/zondarr-logo.svg` (it was in `public/`), which the README shows and `src/app.html` uses
   as the favicon. Where the logo lives is each app's own choice: obzorarr imports its icon from
   `src/lib/assets/` instead.
5. **Health.** `/healthz` always answers `ok`. The module that adds the database replaces it with a
   fuller health: overall (healthy, or degraded by a persistence check), liveness and readiness,
   unauthenticated, and never showing a version (D24).
