# Spec: `setup`

**Status:** drafted for the owner's approval. Module 3 of the capability map
([docs/SPEC.md](SPEC.md)); it closes D15 and the logging half of D14, and ground-floor choices 3
and 5, and the Outfit and IBM Plex Mono half of choice 1. obzorarr is the reference app for `setup`
([Shared groundwork](../AGENTS.md#shared-groundwork)): this spec ports obzorarr's
(`0fb3565:docs/SPEC-setup.md`, the full text before its cut, and `docs/SPEC-setup.md` as it stands)
and its code and tests at `b59b909`, which hold the follow-ups #337–#342: the password-pattern rule,
the redaction allowlist, encoded nested URLs in logs and the linear-time name split. **What differs
from obzorarr:**
- the names: `ZONDARR_` variables, the `data/zondarr.db` default, "zondarr" in the password rule and
  Zondarr in the printed line and the page;
- the decision numbers: D5, D6, D11, D14, D15, D16, D17, D20, D24, D25 (an empty variable counts
  as unset) and D26 (the `rc` dist-tag);
- the health (ground-floor choice 5): `/healthz` reports a database check, and `/healthz/live` and
  `/healthz/ready` join it, where obzorarr keeps its one-word `/healthz`;
- the owner table also has an update time, from zondarr's rule for records;
- the redaction allowlist keeps `keyId` and `authError` and drops Plex's item ids and `maxTokens`:
  zondarr manages no media items and makes no AI requests;
- the claim page: zondarr's own brief and design tokens, its first surface, so it bundles the
  Outfit and IBM Plex Mono fonts and the icon family (below);
- zondarr's own rules for later modules, marked "(zondarr)": the first-run steps, the database
  records, `ORIGIN` as an environment value only, and the content images `wizards` may add to the
  policy.

Everything else is obzorarr's, including the cross-origin check, which comes forward from
`sign-in`'s row for the same reason obzorarr moved it: SvelteKit's own form check would refuse the
claim over plain HTTP. What this spec changes in zondarr's approved capability map and Module notes
is in "Changes to the capability map", below.

**Reading the marks.** A bullet or clause marked "(zondarr)" is this app's own; the rest is the
shared wording. A "(zondarr)" mark inside a bullet covers the rest of that bullet, and "(zondarr:
…)" only its own parentheses. Decision numbers are zondarr's.

## Objective

A fresh install starts safely and is claimed by its one owner (D20):
1. **Startup:** the configuration is checked, the database opened and migrated, and each module's
   startup work run, before any request is served; shutdown stops work, drains and closes cleanly.
2. **The database** (D5, D6): embedded Turso through Drizzle, with reviewed migrations, a settings
   store and the owner account.
3. **Logging** (D11): structured entries on standard output, redacted before they are written.
4. **The request checks:** the cross-origin check on every state-changing request, and security
   headers and a nonce-based CSP on every response the app renders (ground-floor choice 3).
5. **Health** (zondarr, ground-floor choice 5): overall, liveness and readiness.
6. **First run:** the setup gate, the bootstrap token printed to the console, and the claim, which
   creates the owner account.

**Left out on purpose:** signing the owner in at the claim, sessions, the browser's address, rate
limits, cookies and the error pages (`sign-in`); the two-factor offer (`two-factor`); every later
first-run step, such as the first server (`servers`). Until `sign-in` is built, a claimed instance
has no way to sign in, and first run ends at the claim ("Before `sign-in`", below).

## Configuration and startup checks

Each of the app's own variables is read once, at startup, by its own file in `config/`, and
`src/env.ts` declares it (SvelteKit 3 exposes only declared variables). For these, an empty variable
counts as unset (D25's rule; `ORIGIN` differs, below), and a check that fails stops startup with one
line naming the variable and what is wrong, never echoing the value.

| Variable | Default | Checked |
|---|---|---|
| `ZONDARR_SECRET_KEY`, `…_FILE` | — | as `secrets` checks them (D25) |
| `ZONDARR_DATABASE_PATH` | `data/zondarr.db`, against the working directory | its folder exists or can be created, and is writable; the file opens as a database, and the error keeps Turso's reason but never the path |
| `ORIGIN` | unset | below |
| `ZONDARR_LOG_DEBUG` | off | `true` or `false` |

**adapter-bun's own variables** are read and checked by the adapter (1.0.1), with its own defaults
and messages, which may echo a malformed value; the app adds no code for them, and the README lists
them:
- `SHUTDOWN_TIMEOUT` (default 30 s): the drain time. The container's stop timeout must exceed it
  plus the app's 5-second cleanup; the README says so, and the image's Compose templates set
  `stop_grace_period` (Docker's default is 10 seconds);
- `CONNECTION_IDLE_TIMEOUT` (default 10 s, at most 255 s): the idle timeout. The adapter already
  exempts event streams, which `logs`' live stream needs;
- `BODY_SIZE_LIMIT` (default 512 KB). (zondarr: the app takes no uploads, so it needs no change.)

**`ORIGIN`** is optional and never required. It is plain `ORIGIN`, not an app-prefixed name: an app
prefix would mean setting adapter-bun's `envPrefix`, which would then reject the master key's
variable. When set, it is a bare `http` or `https` origin (a trailing `/` is fine), compared as a
parsed origin. It is checked twice:
- **adapter-bun 1.0.1** reads it when the server module loads, before `init`, and uses it to
  correct SvelteKit's `event.url`. An empty or unparseable value stops it with the adapter's own
  message, which includes the value, so the container image's entrypoint unsets an empty `ORIGIN`
  and its templates leave it out (the image's work, not this repo's).
- **The app** then refuses what the adapter accepts and quietly trims: a path, query, fragment or
  credentials. Startup stops with an error that doesn't echo the value.

The cross-origin check, the strict-transport decision and `sign-in`'s browser's address all use the
one value `config/origin.ts` gives.

(zondarr) `ORIGIN` is an environment value, never a stored setting: there is no console setting for
the environment to lock, and the settings page (`sign-in`) only shows it, read-only. It is not the
public invite address (`invitations`), which only builds invite links and has no part in the
cross-origin check, cookies or sign-in. It takes the place of the legacy app's public origin. The
legacy app's trusted origin, with its first-run Test Origin, Save and Skip, and its secure-cookies
setting are not kept, because the cross-origin check stores no address and cookies follow the
browser's address (`sign-in`).

## Startup and shutdown

**Startup** runs once, in SvelteKit's `init` hook, before any request is served, and is skipped
while building:
1. the master key (`secrets`, as now);
2. the configuration above;
3. the database: opened, then migrated (D5: the app is its one migration owner);
4. each module's startup work, in a fixed order. `setup`'s own: load first run's state and, if the
   instance is unclaimed, print the bootstrap token. (zondarr: later modules add clearing expired
   sign-in attempts, `redemption`);
5. starting the jobs (none yet; `sign-in`'s session cleanup is the first, D14). A job that fails to
   start is logged, not fatal.

A failure in steps 1–4 is logged and thrown from `init`: the built server exits non-zero before it
listens, and the dev server stays up with every request failing, as the key error already does.

**Shutdown.** adapter-bun 1.0.1 already drains open requests for `SHUTDOWN_TIMEOUT`, then closes
the rest, exits at once on a second signal, and emits `sveltekit:shutdown` without waiting for its
listeners. The app adds, in the built server only (Vite never emits `sveltekit:shutdown`, and a
`SIGINT` listener would stop Ctrl+C from ending `dev`):
- **On the signal** (`SIGTERM`, `SIGINT`, and `SIGHUP`, which counts as a stop and is passed on to
  the adapter as `SIGTERM`): stop the jobs and timers and close open streams cleanly, so browsers
  reconnect, while the adapter drains. The handlers go in on the turn after `init` resolves, after
  adapter-bun's own, so a signal never reaches only the app's.
- **On `sveltekit:shutdown`:** wait for the jobs stopped on the signal, close the database, then
  flush the logs (so a closing error is written) and exit 0. A failed close is logged, and the exit
  is still 0.
- **A deadline:** if that cleanup hasn't finished 5 seconds after `sveltekit:shutdown`, the app
  exits non-zero anyway, even with an upstream call still outstanding, after flushing its own entry
  for a bounded time. (zondarr) Jobs get up to ten seconds to finish: `sign-in`, which brings the
  first job and its lifecycle (D14), adds their ten seconds to this deadline, and the container's
  stop timeout grows with it.

## The database

**Versions:** `@tursodatabase/database` 0.8.3, `drizzle-orm` and `drizzle-kit` 1.0.0-rc.5 (the `rc`
dist-tag, D5, D26), exact-pinned dev dependencies, or the newest that D5 and D26 allow when the
build starts. The build validates the pair (below), which closes D15.

**Access** follows D6: the client in `db/client.ts` opens the one file; each aggregate's file in
`db/` holds its tables and its named operations; services own the transactions, and every statement
in one goes through its transaction object.

**Migrations** are generated by Drizzle Kit from the schema (`bun run --bun db:generate`, which then
formats them with Biome), reviewed and committed in `drizzle/`. The built server applies them at
startup with only `build/` and the database file: Vite bundles each migration's SQL
(`import.meta.glob` with `?raw`), and Drizzle's Turso migrator that takes the migrations as a record
applies them. It records them as Drizzle Kit's file migrator would, except for an empty `hash`,
which Drizzle reads only to upgrade a pre-1.0 migrations table that no zondarr database has; a test
compares both migrators' rows.

**Turso's native binding** can't be bundled (its loader finds it with a runtime `require`), so the
platform package (`@tursodatabase/database-linux-x64-gnu` or `-linux-arm64-gnu`) ships beside
`build/`, as obzorarr found. SPEC.md's "`bun ./build` needs no `node_modules`" says so, the README
starts the server with `--no-install`, and the container image copies the package.

**Tables** (each with `drizzle/`'s first migration):
- **`settings`:** key, value (text) and update time, through named operations to read and write a
  key. `setup` stores first run's step pointer here; later modules add their own keys.
- **`owner`:** one row at most, enforced by the schema (a fixed id): username, password hash, and
  creation and update times. `two-factor`, `oidc-sign-in` and `owner-plex-sign-in` add their
  fields.

**Records** (zondarr) have random ids and created and updated times, stored and returned in UTC; a
time given without a zone is UTC. Nothing is soft-deleted: disabling is the only reversible way to
switch something off. The owner row is the exception to random ids: its fixed id is what keeps it to
one row, and it never appears in an address. Settings are keyed by name and keep only an update
time, since a key's first write says nothing a later one doesn't.

**Backups:** Turso keeps recent writes in `zondarr.db-wal` beside the file, and closing doesn't fold
them back, so the README says to stop Zondarr and copy the whole folder, with the master key kept
apart (D25). A tested restore procedure stays open in D16.

## Logging

Four levels, debug dropped unless `ZONDARR_LOG_DEBUG` is on. Each entry is one JSON line on standard
output (D11) with a level, a message, a source, structured metadata and a millisecond timestamp.
`logging/` is the app's own small logger, with no library, which closes D14's logging half: the
redaction rules below need key matching at any depth that path-based library redaction doesn't give,
and the entry shape is fixed here. `logs` adds the in-memory buffer when it comes.

**Redaction** runs before an entry is written:
- credentials in URLs, and token-like query parameters, also inside a parameter's value once
  percent-decoded (up to three times), as in Plex's transcoder `url`; such a value is redacted
  whole;
- token, authorisation and cookie fields in payloads and headers;
- at any depth, any metadata key that looks like a token, secret, password, cookie, session or key,
  except the few names `redact.ts` lists as holding no credential, whose values are still cleaned
  like any other (zondarr: `keyId`, the `secrets` key ID, and `authError`; a module adds a name
  only when no value it can hold is a credential);
- a `Secret` (`secrets`) is already `[redacted]`.

Name splitting and the URL scans run in linear time, so a crafted parameter name or URL can't stall
the logger; a growth test guards it.

Console output that is meant for whoever runs the server, such as the bootstrap token, is never a
log entry. It still reaches the container's output, which is why the console is trusted (below).

## The request checks

`handle` runs its stages in this order: the language (`i18n`), the security headers, the
cross-origin check, then the setup gate. `sign-in` later adds its stages between the cross-origin
check and the gate. Every refusal is returned, never thrown
([SPEC-i18n.md](SPEC-i18n.md#choosing-the-language)), so it keeps the language and the headers.

### The cross-origin check

Brought forward from `sign-in`'s row, because the claim is the first form: SvelteKit's own check
compares the browser's `Origin` with `event.url`, which adapter-bun builds as `https` unless
`ORIGIN` or a protocol header says otherwise, so it would refuse the claim over plain HTTP.
- **SvelteKit's own form check is off:** `sveltekit({ csrf: { trustedOrigins: ['*'] } })` in
  `vite.config.ts` (SvelteKit 3 takes its options in the `sveltekit()` call, with no `kit:`
  wrapper). Remote functions stay off. A config test asserts both, so SvelteKit's only remaining
  check before `handle` is the remote-function one, which nothing uses. The cross-origin check
  replaces SvelteKit's form check.
- **The cross-origin check** asks the browser, so the app doesn't need to know its own address and
  stores none. It is the first check in `handle`, after only the language (`i18n`), for every
  method except GET, HEAD and OPTIONS, and for every content type (form, JSON, multipart,
  `text/plain`, empty). Internal `event.fetch` subrequests (`event.isSubRequest`) skip it.
  - An `Origin` header, whenever it is present, must parse as one bare `http` or `https` origin;
    `null`, a malformed value, one the URL parser would repair, or several values are refused. This
    applies on every branch below.
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
  - A refusal is a 403 with the app's own "Access denied" page, or a JSON error (`{ message }`)
    for JSON callers, with the security headers and in the viewer's language. Until `sign-in`
    builds the error pages, the page is the title and its one-line description, unstyled but for
    its colour scheme, since its own policy (below) allows no stylesheet.
- **When `ORIGIN` or a proxy fix is still needed:** behind a proxy that rewrites `Host`, over plain
  HTTP for every browser, and over HTTPS only for browsers without `Sec-Fetch-Site` (Safari before
  16.4, Firefox before 90, Chrome before 76). The proxy fix is `proxy_set_header Host $http_host`
  (not `$host`, which drops a non-default port). Remote functions would need it too; they stay
  off. (zondarr: `sign-in`'s origin test diagnoses it.)
- **Accepted residual risks.** Over plain HTTP, the `Origin` and `Host` comparison can't tell `http`
  from `https`, which is harmless on a port that speaks only HTTP; over HTTPS it affects only
  browsers without `Sec-Fetch-Site`, and only against a network attacker, and HSTS or `ORIGIN`
  closes it. DNS rebinding reaches only actions that need no sign-in, because cookies don't follow
  a rebind, and those are gated by a console token or rate-limited (zondarr: the join flow's
  actions also need a valid invitation code).

`security/cross-origin.ts` is one pure module, copied from obzorarr's as D20 shares the opening
modules.

### Security headers and CSP

On every response that passes through `handle`, early returns and error pages included:
- `X-Frame-Options: DENY`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: same-origin`, never `no-referrer`, which makes browsers send `Origin: null` on
  the app's own form posts. (zondarr) On the join page this replaces the legacy app's suppressed
  referrer and still keeps the invitation code from other sites, which get no referrer at all;
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`;
- `Strict-Transport-Security: max-age=31536000` over HTTPS only, known when `ORIGIN` is `https`, or
  when `ORIGIN` is unset and the browser sent `Sec-Fetch-Site` to a host that isn't `localhost`,
  `*.localhost` or a loopback address (`127.0.0.0/8`, `[::1]`), since browsers send it only to
  HTTPS and those hosts. Never `includeSubDomains`: other apps may share the domain. An accepted
  risk: HSTS covers every port of the host name, so another app on the same host over plain HTTP
  becomes unreachable from that browser until it moves to HTTPS. Forwarded headers never change
  this decision.

**The content security policy** goes on every page through SvelteKit's `csp` option in
`vite.config.ts`, in nonce mode:
- `default-src 'self'`, so a directive not listed falls back to the app;
- `script-src 'self'` with the nonce, so only the app's scripts run;
- `style-src 'self' 'unsafe-inline'`: `src/app.html` and server-rendered pages carry style
  attributes, which a nonce can't cover, and styles can't run code;
- `img-src 'self' data:`;
- `font-src 'self'` (the fonts are bundled, below);
- `connect-src 'self'`;
- `frame-ancestors 'none'`, `frame-src 'none'`, `object-src 'none'`, `base-uri 'self'`,
  `form-action 'self'`.

(zondarr) A later module widens a directive only for what it names in its own spec, such as
`wizards`' content images, which may come from other hosts.

No page is prerendered (`i18n` already forbids it), so every page gets its own nonce.

**A page a `handle` stage builds itself,** such as the cross-origin refusal, never passes through
SvelteKit's renderer, which adds the policy above and fills `<html lang>`. The stage sets both
itself, with a fixed, stricter policy, since the page has no scripts: `default-src 'none';
style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`.

**A limit:** responses produced before `handle` carry none of these headers: the built files
(scripts, styles, fonts), which adapter-bun serves itself, and the adapter's own 400 and 413
answers. None is a document, so framing and the CSP don't apply to them, and Bun sends each file
with its real content type.

## Health

(zondarr) Ground-floor choice 5: `/healthz` stops answering only `ok` now that there is a database.
Each answer is public, unauthenticated, JSON, `cache-control: no-store`, and never shows a version
(D24) or an error's text:

| Path | Answers |
|---|---|
| `/healthz` | 200 `{"status":"healthy","checks":{"database":"ok"}}`, or 503 with `"degraded"` and `"database":"failed"` |
| `/healthz/live` | 200 `{"status":"alive"}` while the process serves requests |
| `/healthz/ready` | 200 `{"status":"ready"}`, or 503 `{"status":"not ready"}` when the database check fails |

The database check runs one trivial query on the open connection, with a short time limit, and
logs a failure. Startup finishes before the server listens, so readiness never waits on it. The
container's health check uses `/healthz/live`, so a database fault shows as degraded rather than
restarting the container in a loop. The paths come from the legacy app's `/health`, `/health/live`
and `/health/ready`, under the ground floor's `/healthz`.

## First run

**The setup gate** is the last `setup` stage in `handle`. Until first run is complete, every request
except the current first-run step, the three health paths and the responses produced before
`handle` gets a 303 to that step (sign-in and first run's own helpers join the exceptions when
their modules add them). It reads first run's state from memory, which startup loads and the claim
updates (one process, D17). SvelteKit removes the `__data.json` suffix before `handle` and turns a
redirect from `handle` into the redirect its router follows, so client-side navigation is gated
too.

**The step pointer.** The server keeps one current-step pointer in `settings`. The browser can't
skip ahead: each step's action checks that it is the current step, a step that offers Previous only
moves the pointer back, and only the last step's action completes first run. Every step after the
claim needs the owner's session, which `sign-in` brings. (zondarr) First run is the claim, the
two-factor offer (`two-factor`) and the optional first server (`servers`), each later step
skippable; after an interruption it resumes at the current step.

**The bootstrap token** (D20):
- 12 random lowercase letters and digits, drawn without bias from WebCrypto, shown as
  `xxxx-xxxx-xxxx`;
- held only in memory: never in a log entry, the database, a response or an address;
- printed to standard output at startup, `Setup token: xxxx-xxxx-xxxx (valid for 15 minutes). Open
  /setup to claim this Zondarr.`, with the full address when `ORIGIN` is set (the server doesn't
  otherwise know its address);
- valid for 15 minutes, after which a new one is printed; a timer that shutdown stops, and that
  waits while a claim is in progress;
- entered with or without the dashes, in any case, with spaces around it trimmed, and compared in
  constant time;
- once the instance is claimed, none is printed again.

(zondarr) The legacy app's ten-minute, single-use, same-site-strict browser authorisation from its
setup link is not kept: the token is checked when the claim is submitted.

**The claim** is `/setup`, the first step, and a POST form action. In this order:
1. **The fields:** after the form is read, the username and password are checked against the rules
   below, with nothing awaited. A field error leaves the token unused.
2. **The token:** checked and used up, with no `await` between the two. A wrong or expired token
   gets one error, "That setup token isn't valid. Use the newest one the server printed.", and
   never reaches the hash, so a guess costs the server nothing.
3. **The hash** of the password.
4. **One transaction** creates the owner and moves the step pointer; its insert fails if an owner
   exists.

If anything after the token is used up fails while the instance is still unclaimed and shutdown
hasn't begun, a new token is printed. A failed claim keeps the typed username and clears the token
and password. The claim stores no address, and nothing but the owner row and the pointer. Startup
reads the pointer back, so a restarted instance stays claimed.

**After it,** the claim no longer exists: `/setup` answers "not found" once first run is complete
(D20), and the claim action answers it whenever the instance is claimed.

**Owner credentials,** in `security/password.ts`, which `sign-in`'s password change and recovery
reuse:
- **Username:** trimmed and normalised to Unicode NFC, then 1–64 characters (Unicode code points),
  no control characters (`\p{Cc}`). Stored in that form, case kept, and compared by `sign-in` after
  `toLowerCase()`, so case doesn't matter.
- **Password:** normalised to NFC, then 15–128 characters (Unicode code points), any characters,
  no composition rules. Ignoring case, it may not be, as a whole, one unit of up to 4 characters
  repeated (the last repeat may be cut short) or one straight run up or down by code point, with
  digits running on from 9 to 0; it may not contain the app's name or, when the username has 4 or
  more characters, the username; and it may not be on the bundled list of common passwords
  (below). 15 is NIST SP 800-63B-4's minimum for a password that is the only factor, which it is
  until two-factor is turned on. NIST also requires a blocklist, and length alone accepts the long
  passwords such lists hold; the list holds only some patterns, hence the pattern rule.
- **The common-password list,** `security/common-passwords.txt`, copied from obzorarr's: the
  10,898 entries of 15–128 code points, after NFC and lower-casing, of SecLists'
  `Passwords/Common-Credentials/xato-net-10-million-passwords-1000000.txt` (MIT licence) at commit
  `180c2d5`, which `password.ts` names with the recipe to rebuild it. Vite bundles it with `?raw`,
  like the migrations.
- **Hashing:** `Bun.password` with argon2id and Bun's defaults, of the NFC form, so `sign-in`
  verifies what was hashed. The password is never logged or returned.
- **The form** has one password field with a control that shows what was typed (DESIGN.md: a
  password field may reveal newly typed input), and no confirmation field.

**Trust:** anyone who can read the server console can claim a fresh install.

## Before `sign-in`

`setup` is built before `sign-in`, which brings the rest of the protections. Until then:
- **Rate limits:** none. The token has 62 bits and lasts 15 minutes, and a wrong token costs no
  hash, so guessing it isn't practical; `sign-in` adds the claim's limit (SPEC.md's `sign-in`
  notes, "Rate limits").
- **The browser's address and cookies:** the claim sets no cookie yet, so it needs neither. Once
  `sign-in` starts the owner's session at the claim, the claim needs the browser's address, and the
  session follows `sign-in`'s cookies. (zondarr: `sign-in` also adds the origin test's hint to the
  claim page.)
- **First run ends at the claim,** its only step: the claim completes first run and sends the
  browser to `/`. `sign-in` signs the new owner in at the claim, and `two-factor` adds the first
  step after it, from which on the claim no longer completes first run.

No release is cut between `setup` and `sign-in`.

## The claim page

`/setup` follows its brief, [`route-setup.md`](../.impeccable/surfaces/route-setup.md), built
through `/impeccable`: one quiet form in the 672px form width, with the logo, the wordmark and the
language switcher, in zondarr's tokens. Every string is a `setup_…` message in English and Danish;
the refusal's are `error_access_denied_…`, which `sign-in`'s error pages reuse. Without JavaScript
the form still works, with no Show control.

It is zondarr's first surface, so it brings what the ground floor left to it (ground-floor choices 1
and 2):
- **Fonts:** `@fontsource-variable/outfit` and `@fontsource/ibm-plex-mono` (400), bundled and served
  from the app (`font-src 'self'`); the font tokens name them ahead of their system fallbacks. DM
  Serif Display waits for the first public welcome surface.
- **Icons:** `@lucide/svelte`, a line family that fits DESIGN.md's "single consistent 20px line
  family with 1.5–2px stroke", for the Show control's eye; later surfaces use the same family.
- **Ark UI:** none needed; the form is native controls.

## Validation

The build runs D15's validation with the pinned versions, and records the evidence in its PR body:
- **Migrations:** Drizzle Kit generates the first migration from the schema; the built server
  applies the bundled migrations to a new database, records them as Drizzle Kit's own migrator
  would (but the empty `hash`), and on a second start finds nothing to apply.
- **Type checking:** `check` passes with the schema, client and operations.
- **The production build:** `bun --no-install ./build` opens the database through Turso's native
  binding on Linux x64 (CI) and arm64, with the platform package beside `build/`.
- **Rollback isolation** (D5): a transaction that rolls back leaves a concurrent, unrelated write on
  the same connection in place, and the test fails on Drizzle `1.0.0-rc.4`.
- **No Node:** all of it with no `node`, `npm` or `npx` on `PATH`.

## Project structure

```text
src/env.ts                                  + ZONDARR_DATABASE_PATH, ORIGIN, ZONDARR_LOG_DEBUG
src/hooks.server.ts                         init: startup; handle: language, headers,
                                            cross-origin check, setup gate
src/lib/server/config/config-error.ts       the error every variable check throws
src/lib/server/config/error-code.ts         a system error's code, for the path and key checks
src/lib/server/config/database-path.ts      the database file's path
src/lib/server/config/origin.ts             ORIGIN, parsed and checked
src/lib/server/config/log-debug.ts          ZONDARR_LOG_DEBUG
src/lib/server/db/client.ts                 opens the database; the health query
src/lib/server/db/migrate.ts                applies the bundled migrations
src/lib/server/db/settings.ts               the settings table and its operations
src/lib/server/db/owner.ts                  the owner table and its operations
src/lib/server/logging/logger.ts            levels, entries, standard output, flushing
src/lib/server/logging/redact.ts            the redaction rules
src/lib/server/security/access-denied.ts    the cross-origin refusal, page or JSON
src/lib/server/security/bootstrap-token.ts  the token: drawing, formatting, comparing, expiry
src/lib/server/security/cross-origin.ts     the cross-origin check
src/lib/server/security/headers.ts          the security headers for a request
src/lib/server/security/password.ts         the credential rules, hashing and verifying
src/lib/server/security/common-passwords.txt
src/lib/server/services/health.ts           the three health answers
src/lib/server/services/setup/startup.ts    the startup steps and shutdown
src/lib/server/services/setup/first-run.ts  the steps, the pointer, the token's timer, the gate
src/lib/server/services/setup/claim.ts      the claim
src/routes/healthz/+server.ts               overall
src/routes/healthz/live/+server.ts          liveness
src/routes/healthz/ready/+server.ts         readiness
src/routes/setup/+page.svelte               the claim form
src/routes/setup/+page.server.ts            its load and the claim action
src/routes/setup/token-format.ts            the token field's dashes as it is typed
drizzle/                                    the reviewed migrations
drizzle.config.ts
vite.config.test.ts                         SvelteKit's form check and remote functions off
tests/e2e/setup.test.ts                     first run, health and the request checks on the
                                            built server
tests/e2e/global-setup.ts                   claims the instance for the other tests
```

The build also changes `package.json` (the six packages and `db:generate`), `vite.config.ts` (the
form check off, the CSP, the exported options and Vitest's `include`), `panda.config.ts` (the font
families), `src/routes/+layout.svelte` (the font imports), `playwright.config.ts` (a temporary
database per run, the token captured from the server's output, the global setup), `messages/`, the
README (the variables, `ORIGIN` and the proxy fix, the database and backups, first run, logs, and
stopping), and `.gitignore` (`/data/` and `*.db*`).

## Testing strategy

- **Unit (Vitest, `node`):**
  - each `config/` reader;
  - the logger's entry shape, debug filter and flush through a slow pipe; the redaction rules, one
    case each and nested, the allowlist, encoded nested URLs (a decoded value also checked as a
    query of its own, so `u=token%3Dabc` is redacted), and the linear-time growth check;
  - the headers for HTTPS, plain HTTP, loopback and `ORIGIN`;
  - the cross-origin check against a matrix of methods, content types and `Origin`,
    `Sec-Fetch-Site`, `Host` and `ORIGIN` values; the refusal in both languages, page and JSON; and
    the config test for SvelteKit's options;
  - the token's format, alphabet, unbiased drawing, expiry and comparison; the token field's
    dashes;
  - the credential rules at their limits, NFC and case included, the patterns (each code point
    lower-cased on its own, so `ΣΣΣ…` and `İabcİabc…` are refused), the list, and an argon2id
    round trip;
  - shutdown against a stand-in process: `SIGHUP` passed on, exit 0 after cleanup, exit 1 when it
    throws and at the deadline, and no handlers in `dev`;
  - the health answers with a working and a failing database check;
  - against a temporary database file: migrations on a new database and the migrators' rows,
    rollback isolation, the settings and owner operations, and the claim: success; a field error
    leaving the token unused; a wrong and an expired token never reaching the hash; a second claim;
    two at once leaving one owner; a failed transaction printing a new token, but not during
    shutdown; a restart reading the claim back; and the gate's decision for each path. Timer tests
    fake the clock.
- **e2e (Playwright, against the built server):** the web server starts with a generated key and a
  temporary database, created only in the runner process and removed once the server has exited.
  Its `wait.stdout` pattern runs from the token line through adapter-bun's "Listening on" and
  replaces the `url` check, because Playwright races the two and the URL could win before the token
  is captured. The global setup claims the instance through the form in a browser, so the smoke and
  language tests run on a claimed instance as before. `setup.test.ts` starts its own fresh servers
  and checks that:
  - a new database file is migrated, and a second start applies nothing;
  - every page sends a fresh instance to `/setup`, and the three health paths still answer;
  - a wrong token is refused, keeping the username and clearing the rest; the right one, typed in
    upper case without dashes, claims; `/setup` and its action then answer 404, also after a
    restart;
  - a cross-site form POST is refused, and a same-origin POST with no `Sec-Fetch-*` headers passes,
    both on `localhost` and on a plain-HTTP host name that isn't loopback (Chromium's
    `--host-resolver-rules="MAP app.test 127.0.0.1"`);
  - the headers are on a page, the health paths, a 404, a refusal and the gate's redirect, and HSTS
    isn't, over plain HTTP;
  - the page's scripts carry the CSP nonce, the policy matches directive for directive, the refusal
    page carries its own policy, and the browser reports no CSP violation;
  - the server refuses to start with an `ORIGIN` holding credentials (`https://u:p@host`) or a path
    (`https://host/app`), a bad `ZONDARR_LOG_DEBUG`, or an unwritable database folder, without
    echoing the value;
  - `SIGHUP` and `SIGTERM` each shut it down with exit code 0;
  - neither the token nor the password appears in a response or a log entry.
  `smoke.test.ts` checks `/healthz`'s new answer instead of `ok`.

## Commands

The ground floor's ([docs/SPEC.md](SPEC.md#commands)), plus `bun run --bun db:generate` (Drizzle Kit
generates a migration from the schema, and Biome formats it). `smoke` also runs `setup.test.ts`.

## Changes to the capability map

Approved with this spec, as obzorarr's own spec moved its rows:
- **The cross-origin check and `ORIGIN` move from `sign-in` (row 4) to `setup` (row 3),** for the
  reason above. `sign-in`'s Module notes keep the browser's address, the address hint, cookies and
  the rest. The bullets on SvelteKit's form check, the cross-origin check, when `ORIGIN` or a proxy
  fix is needed, the accepted risks, its tests and `ORIGIN` move into this spec.
- **The password rules move from `sign-in` to `setup`,** since the claim sets the first password.
  `sign-in` keeps the slowing of failed sign-ins (its lockout).
- **Environment locks move from `setup` to `servers` (row 8),** whose provider overrides are the
  first setting the environment can lock; `sync` and `invitations` reuse them. Nothing in `setup`
  has a setting to lock. obzorarr moved its locks to `plex-connection` for the same reason, so
  `servers` ports them from there once obzorarr has built it.
- **The correlation id and the request log entry move from `setup` to `sign-in`,** which builds
  the error pages the id appears on and the stages a request passes; obzorarr's `setup` built
  neither.
- **The owner's account:** the claim asks for the password once, with a Show control, and the
  username is obzorarr's (1–64 characters, case ignored), replacing zondarr's note that asked for
  the password twice and a 3–32-character lowercase username. D20 wants signing in to work the same
  way in every app, and DESIGN.md already allows revealing a newly typed password.
- **The printed setup address carries no token,** so the note that opening it removes the token
  from the address bar no longer applies: a token in an address would reach the browser's history
  and a proxy's access log.
- **Using up the token and creating the owner are two steps,** not the one atomic step zondarr's
  note asked for: the token is used up before the hash, so a wrong guess costs nothing, and if
  creating the owner then fails, a new token is printed, so nobody is left without one.
- The rest of `setup`'s Module notes moves here.

## Boundaries

- **Always:** startup finishes before the first request; reviewed migrations; named database
  operations and short transactions (D6); redaction before writing; the token only in memory and on
  the console; the cheap checks before the hash; refusals in `handle` returned, never thrown.
- **Ask first:** any dependency beyond the six packages (`@tursodatabase/database`, `drizzle-orm`,
  `drizzle-kit`, `@fontsource-variable/outfit`, `@fontsource/ibm-plex-mono`, `@lucide/svelte`);
  another database engine; a logging library; a second owner or any role (D20).
- **Never:** a token or password in a log entry, response, address or the database (only the hash);
  a stored address; a way to skip a first-run step; a claim after first run; `includeSubDomains`; a
  version in a health answer.

## Docs this module changes when built

- **`docs/SPEC.md`:** the status line and row 3 (built); the tech-stack table (Turso, Drizzle, the
  fonts and Lucide) and the `node_modules` line; the `db:generate` and `smoke` command rows; the
  testing section; "Open decisions": the `setup` line goes; ground-floor choices 1 (Outfit and IBM
  Plex Mono), 3 and 5 close.
- **`docs/decisions.md`:** D15 moves to Decided with the validated pair; D14's logging half moves to
  Decided as the app's own logger and why, and D14 keeps only the job half.
- **README:** the variables above, `ORIGIN` and the proxy fix, the database and backups, first run
  (the token in the console), logs, and stopping.
- **AGENTS.md:** the status and the structure tree. **PRODUCT.md:** the project state.

## Success criteria

1. The tests above pass, with `check`, `lint`, `build`, `smoke` and prek, and CI's `checks`,
   `smoke` and `ci-ok` pass.
2. A fresh built server prints a token, sends every page to `/setup`, and is claimed once over
   plain HTTP from another machine on the network; then the placeholder `/` serves as before, with
   the headers and CSP.
3. D15's validation has passed, with its evidence in the build PR's body.
4. The docs listed above say what was built.
