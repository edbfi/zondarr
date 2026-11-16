# Spec: `setup`

**Status:** built (2026-11-16), module 3 of the capability map ([docs/SPEC.md](SPEC.md)); D11, D15
and D20 hold the decisions, and it closed ground-floor choices 3 and 5 and the Outfit and IBM Plex
Mono half of choice 1. obzorarr is the reference app for `setup`
([Shared groundwork](../AGENTS.md#shared-groundwork)): this module ports obzorarr's spec and its
code and tests at `b59b909`. This file keeps what the code and tests can't say. The full text
before this cut is `d56ec4d:docs/SPEC-setup.md`. **What differs from obzorarr:**
- the names: `ZONDARR_` variables, the `data/zondarr.db` default, "zondarr" as the app name the
  password may not contain, and Zondarr in the printed line and the page;
- the decision numbers;
- the health (ground-floor choice 5): `/healthz` reports a database check, and `/healthz/live` and
  `/healthz/ready` join it, where obzorarr keeps its one-word `/healthz`; the setup gate lets all
  three through;
- the owner table also has an update time, from zondarr's rule for records;
- the redaction allowlist keeps `keyId` and `authError` and drops Plex's item ids and `maxTokens`:
  zondarr manages no media items and makes no AI requests;
- a `handleError` hook that logs unexpected errors (obzorarr's `sign-in` adds its own);
- the claim page: zondarr's own brief, design tokens and bundled fonts;
- zondarr's own rules for later modules, marked "(zondarr)".

**Reading the marks.** A bullet or clause marked "(zondarr)" is this app's own; the rest is the
shared wording. A "(zondarr)" mark inside a bullet covers the rest of that bullet, and "(zondarr:
…)" only its own parentheses. Decision numbers are zondarr's.

## Objective

A fresh install starts safely and is claimed by its one owner (D20): the configuration is checked
and the database opened and migrated before any request is served; entries are logged as redacted
JSON; every state-changing request passes the cross-origin check, and every rendered response
carries the security headers and a nonce-based CSP; the health paths report the database; and until
the claim, every page sends the visitor to `/setup`, where the bootstrap token printed to the
console creates the owner account.

**Left out on purpose:** signing the owner in at the claim, sessions, the browser's address, rate
limits, cookies and the error pages (`sign-in`); the two-factor offer (`two-factor`); every later
first-run step, such as the first server (`servers`). Until `sign-in` is built, a claimed instance
has no way to sign in, and first run ends at the claim ("Before `sign-in`", below).

## Configuration and startup checks

Each of the app's own variables is read once, at startup, by its own file in `config/`, and
`src/env.ts` declares it (SvelteKit 3 exposes only declared variables). An empty variable counts as
unset (D25's rule; `ORIGIN` differs, below), and a failed check stops startup with one line naming
the variable and what is wrong, never echoing the value.

**adapter-bun's own variables** (`SHUTDOWN_TIMEOUT`, `CONNECTION_IDLE_TIMEOUT`, `BODY_SIZE_LIMIT`)
are read and checked by the adapter, with its own defaults and messages, which may echo a malformed
value; the app adds no code for them, and the README lists them. The container's stop timeout must
exceed `SHUTDOWN_TIMEOUT` plus the app's 5-second cleanup, so the image's Compose templates set
`stop_grace_period` (Docker's default is 10 seconds). The adapter already exempts event streams from
`CONNECTION_IDLE_TIMEOUT`, which `logs`' live stream needs. (zondarr: the app takes no uploads, so
`BODY_SIZE_LIMIT` needs no change.)

**`ORIGIN`** is optional and never required. It is plain `ORIGIN`, not an app-prefixed name: an app
prefix would mean setting adapter-bun's `envPrefix`, which would then reject the master key's
variable. It is checked twice:
- **adapter-bun** reads it when the server module loads, before `init`, and uses it to correct
  SvelteKit's `event.url`. An empty or unparseable value stops it with the adapter's own message,
  which includes the value, so the container image's entrypoint unsets an empty `ORIGIN` and its
  templates leave it out (the image's work, not this repo's).
- **The app** then refuses what the adapter accepts and quietly trims: a path, query, fragment or
  credentials.

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

**Startup** runs once, in SvelteKit's `init` hook, before any request is served: the master key,
the configuration, the database (D5: the app is its one migration owner), then each module's
startup work in a fixed order, then the jobs. (zondarr: later modules add clearing expired sign-in
attempts, `redemption`.) A job that fails to start is logged, not fatal. A failure before the jobs
is logged and thrown from `init`: the built server exits non-zero before it listens, and the dev
server stays up with every request failing.

**Shutdown.** adapter-bun drains open requests for `SHUTDOWN_TIMEOUT`, exits at once on a second
signal, and emits `sveltekit:shutdown` without waiting for its listeners. So the app stops the jobs
and timers and closes open streams on the signal, so browsers reconnect, while the adapter drains;
on `sveltekit:shutdown` it waits for those jobs, closes the database, flushes the logs and exits 0
(a failed close is logged, and the exit is still 0); and it exits non-zero anyway 5 seconds after
`sveltekit:shutdown`, even with an upstream call still outstanding. `SIGHUP` counts as a stop.
(zondarr) Jobs get up to ten seconds to finish: `sign-in`, which brings the first job and its
lifecycle (D14), adds their ten seconds to this deadline, and the container's stop timeout grows
with it.

## The database

D5, D6 and D15 hold the engine, the access rules and the validated versions.

**Tables:**
- **`settings`:** one value per key. `setup` stores first run's step pointer here; later modules
  add their own keys.
- **`owner`:** one row at most, enforced by the schema. `two-factor`, `oidc-sign-in` and
  `owner-plex-sign-in` add their fields.

**Records** (zondarr) have random ids and created and updated times, stored and returned in UTC; a
time given without a zone is UTC. Nothing is soft-deleted: disabling is the only reversible way to
switch something off. The owner row is the exception to random ids: its fixed id is what keeps it to
one row, and it never appears in an address. Settings are keyed by name and keep only an update
time, since a key's first write says nothing a later one doesn't.

**Backups:** a tested restore procedure stays open in D16; the README says how to copy the database
folder meanwhile.

## Logging

D11 holds the decision and why the app has its own logger. Four levels, debug dropped unless
`ZONDARR_LOG_DEBUG` is on. Each entry is one JSON line on standard output with a level, a message,
a source, structured metadata and a millisecond timestamp. `logs` adds the in-memory buffer when it
comes.

**Redaction** runs before an entry is written:
- credentials in URLs, and token-like query parameters, also inside a parameter's value once
  percent-decoded (up to three times), as in Plex's transcoder `url`; such a value is redacted
  whole;
- token, authorisation and cookie fields in payloads and headers;
- at any depth, any metadata key that looks like a token, secret, password, cookie, session or key,
  except the few names `redact.ts` lists as holding no credential, whose values are still cleaned
  like any other (zondarr: `keyId`, the `secrets` key ID, and `authError`, not Plex's item ids
  or `maxTokens`; a module adds a name only when no value it can hold is a credential);
- a `Secret` (`secrets`) is already `[redacted]`.

**Unexpected errors** thrown by a load, a form action, an endpoint or a hook reach SvelteKit's
`handleError` hook, which writes them through the logger as one redacted `error` entry, never with
SvelteKit's default `console.error`, which is neither redacted nor a JSON line. Expected errors and
404s for unknown paths aren't logged as errors. The browser keeps SvelteKit's generic message
until `sign-in` builds the error pages.

Console output meant for whoever runs the server, such as the bootstrap token, is never a log
entry. It still reaches the container's output, which is why the console is trusted (below).

## The request checks

`handle` runs the language (`i18n`), the security headers, the cross-origin check, then the setup
gate; `sign-in` later adds its stages between the cross-origin check and the gate. Every refusal is
returned, never thrown ([SPEC-i18n.md](SPEC-i18n.md#choosing-the-language)), so it keeps the
language and the headers.

### The cross-origin check

SvelteKit's own form check compares the browser's `Origin` with `event.url`, which adapter-bun
builds as `https` unless `ORIGIN` or a protocol header says otherwise, so it would refuse the claim
over plain HTTP. So that check is off, remote functions stay off (they would need `ORIGIN` too), and
the app's own check replaces it. It asks the browser, through `Sec-Fetch-Site` and `Origin` (the
rules and their order are in `cross-origin.ts` and its test matrix), so the app needs no address of
its own and stores none.

What later modules must keep:
- **Requests from no browser,** with neither `Origin` nor `Sec-Fetch-Site`, pass only on an explicit
  list of machine routes, each with the credentials the app's approved docs require for it, such as
  the API-key endpoints (zondarr: none, so every such request is refused). The session cookie is
  never honoured on one: such a request carrying only a session cookie gets a 403.
- **The refusal** is the app's own "Access denied" page, or a JSON `{ message }` for JSON callers;
  `sign-in`'s error pages reuse its messages.

**When `ORIGIN` or a proxy fix is still needed:** behind a proxy that rewrites `Host`, over plain
HTTP for every browser, and over HTTPS only for browsers without `Sec-Fetch-Site` (Safari before
16.4, Firefox before 90, Chrome before 76). The README gives the fix.

**Accepted residual risks.** Over plain HTTP, the `Origin` and `Host` comparison can't tell `http`
from `https`, which is harmless on a port that speaks only HTTP; over HTTPS it affects only
browsers without `Sec-Fetch-Site`, and only against a network attacker, and HSTS or `ORIGIN`
closes it. DNS rebinding reaches only actions that need no sign-in, because cookies don't follow a
rebind, and those are gated by a console token or rate-limited (zondarr: the join flow's actions
also need a valid invitation code).

`security/cross-origin.ts` is one pure module, copied from obzorarr's as D20 shares the opening
modules.

### Security headers and CSP

The headers go on every response that passes through `handle`, and the policy on every page,
through SvelteKit's `csp` option in nonce mode. No page is prerendered (`i18n` already forbids it),
so every page gets its own nonce. The choices the code can't explain:
- **`Referrer-Policy: same-origin`,** never `no-referrer`, which makes browsers send `Origin: null`
  on the app's own form posts. (zondarr) On the join page this replaces the legacy app's suppressed
  referrer and still keeps the invitation code from other sites, which get no referrer at all.
- **Strict transport** only over HTTPS, known when `ORIGIN` is `https`, or, when `ORIGIN` is unset,
  from `Sec-Fetch-Site` sent to a host that isn't `localhost`, `*.localhost` or loopback, since
  browsers send it only to HTTPS and those hosts. Forwarded headers never change this decision.
  Never `includeSubDomains`: other apps may share the domain. An accepted risk: HSTS covers every
  port of the host name, so another app on the same host over plain HTTP becomes unreachable from
  that browser until it moves to HTTPS.
- **`style-src 'unsafe-inline'`:** `src/app.html` and server-rendered pages carry style
  attributes, which a nonce can't cover, and styles can't run code.
- (zondarr) A later module widens a directive only for what it names in its own spec, such as
  `wizards`' content images, which may come from other hosts.
- **A page a `handle` stage builds itself,** such as the refusal, never passes through SvelteKit's
  renderer, so the stage sets its own fixed, stricter policy and `<html lang>`.

**A limit:** responses produced before `handle` carry none of these headers: the built files, which
adapter-bun serves itself, and the adapter's own 400 and 413 answers. None is a document, so
framing and the CSP don't apply to them, and Bun sends each file with its real content type.

## Health

(zondarr) Ground-floor choice 5. `/healthz` (overall), `/healthz/live` and `/healthz/ready` are
public and unauthenticated, and never show a version (D24) or an error's text. Liveness never
touches the database, so the container's health check uses it, and a database fault shows as
degraded rather than restarting the container in a loop. The paths come from the legacy app's
`/health`, `/health/live` and `/health/ready`, under the ground floor's `/healthz`.

## First run

**The setup gate** is the last `setup` stage in `handle`. Until first run is complete, every request
except the current first-run step, the three health paths and the responses produced before
`handle` gets a 303 to that step. Sign-in and first run's own helpers join the exceptions when their
modules add them. It reads first run's state from memory, which startup loads and the claim updates
(one process, D17). SvelteKit removes the `__data.json` suffix before `handle` and turns a redirect
from `handle` into the redirect its router follows, so client-side navigation is gated too.

**The step pointer.** The server keeps one current-step pointer in `settings`. The browser can't
skip ahead: each step's action checks that it is the current step, a step that offers Previous only
moves the pointer back, and only the last step's action completes first run. Every step after the
claim needs the owner's session, which `sign-in` brings. (zondarr) First run is the claim, the
two-factor offer (`two-factor`) and the optional first server (`servers`), each later step
skippable; after an interruption it resumes at the current step.

**The bootstrap token** (D20) is held only in memory, printed to standard output with the path
`/setup`, and the full address when `ORIGIN` is set, since the server doesn't otherwise know its
address. The printed address never carries the token, which would reach the browser's history and a
proxy's access log. A new one is printed every 15 minutes until the claim, and none after it.
(zondarr) The legacy app's ten-minute, single-use, same-site-strict browser authorisation from its
setup link is not kept: the token is checked when the claim is submitted.

**The claim** checks the fields, then checks and uses up the token with no `await` between the
two, then hashes the password, then creates the owner and moves the step pointer in one
transaction. The cheap checks come first so a wrong guess never costs a hash, and a field error
leaves the token unused. The claim stores no address, and nothing but the owner row and the
pointer. After it, the claim no longer exists: `/setup` answers "not found" once first run is
complete (D20), and the claim action answers it whenever the instance is claimed.

**Owner credentials,** in `security/password.ts`, which `sign-in`'s password change and recovery
reuse:
- **The username** is stored with its case kept, and `sign-in` compares it after `toLowerCase()`,
  so case doesn't matter.
- **The password** needs 15 characters because that is NIST SP 800-63B-4's minimum for a password
  that is the only factor, which it is until two-factor is turned on. NIST also requires a
  blocklist, and length alone accepts the long passwords such lists hold, so the bundled list of
  common passwords is checked too (the owner chose the list, 2026-11-12). `password.ts` names
  its source and how to rebuild it. The list holds only some patterns, so the password also may not
  be, as a whole, one unit of up to 4 characters repeated or one straight run up or down (the
  owner added this, 2026-11-16). There are no composition rules.
- **The hash** is of the NFC form, so `sign-in` verifies what was hashed. The password is never
  logged or returned.
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

## Boundaries

- **Always:** startup finishes before the first request; reviewed migrations; named database
  operations and short transactions (D6); redaction before writing; the token only in memory and on
  the console; the cheap checks before the hash; refusals in `handle` returned, never thrown.
- **Ask first:** another database engine; a logging library; a second owner or any role (D20).
- **Never:** a token or password in a log entry, response, address or the database (only the hash);
  a stored address; a way to skip a first-run step; a claim after first run; `includeSubDomains`; a
  version in a health answer.
