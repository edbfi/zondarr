# Tasks: `setup`

The spec is [docs/SPEC-setup.md](../docs/SPEC-setup.md), and the plan is [plan.md](plan.md). Each
task is one PR, starts from the obzorarr PR it names, and writes its tests first. Each one updates
AGENTS.md's status and structure, ticks off its items in `tasks/`, gets a council review, and runs
`bun run --bun check`, `test`, `lint`, `build`, `smoke` and `prek run --all-files --hook-stage
manual` before every commit. Paths under `src/lib/server/` are shortened to `server/`.

## Task 1: the database (D15)

**Ports** obzorarr #325.

**Description:** Add the Drizzle and Turso pair, open and migrate the database at startup, and run
D15's validation. Startup moves into `server/services/setup/startup.ts`: the key, the
configuration (`ZONDARR_DATABASE_PATH` for now), then the database, opened and migrated. Both
tables go into the first migration; no operations yet.

**Acceptance criteria:**
- [x] `server/config/database-path.test.ts` first fails, then passes: the default `data/zondarr.db`
  against the working directory, an empty variable counting as unset, a folder that is created, and
  a folder that can't be created or written refused with one line naming the variable and never
  echoing the path (a regular file as the parent, so it holds as root).
- [x] `server/db/migrate.test.ts`, against a temporary file: the bundled migrations apply to a new
  database, both tables exist, a second run applies nothing, and the rows match Drizzle Kit's file
  migrator's but for the empty `hash`. `server/db/client.test.ts` holds D5's rollback-isolation
  check and fails on `drizzle-orm@1.0.0-rc.4`.
- [x] `startup.test.ts`: a path that names a folder or a non-database file stops startup with
  Turso's reason and without the path. `server/config/error-code.ts` holds the system-error-code
  helper, and `config/secret-key.ts` uses it in place of its private `codeOf`.
- [x] `@tursodatabase/database`, `drizzle-orm` and `drizzle-kit` are exact-pinned dev dependencies
  at the newest D5 and D26 allow; `db:generate` runs Drizzle Kit, then Biome; the first migration
  holds `settings` (key, value, update time) and `owner` (fixed id checked to be 1, username,
  password hash, creation and update times), reviewed and committed.
- [x] `tests/e2e/setup.test.ts`: the built server migrates a new file, starts again on it applying
  nothing, and refuses a folder it can't create (a regular file as its parent, so it holds as root)
  and a path naming a folder without echoing either; the `chmod` "can't be written" case is
  unit-only and skips as root.
  `playwright.config.ts` gives each run a temporary database, created and removed only in the
  runner process.
- [x] D15's validation passes with its evidence in the PR body: migrations, `check`,
  `bun --no-install ./build` with the platform package beside `build/` on Linux arm64 and x64
  (CI), rollback isolation, and all of it with failing `node`, `npm` and `npx` on `PATH`.

**Verification:** the gates; a folder holding only `build/` and the platform package serves
`/healthz` and creates its database under `bun --no-install ./build`, then exits on `SIGTERM`.

**Dependencies:** none.

**Files:** `package.json`, `bun.lock`, `drizzle.config.ts`, `drizzle/`, `.gitignore`, `src/env.ts`,
`src/hooks.server.ts`, `server/config/{config-error,error-code,database-path,secret-key}.ts`
(+ tests), `server/db/{client,migrate}.ts` (+ tests), `server/db/{settings,owner}.ts`,
`server/services/setup/startup.ts` (+ test), `tests/e2e/setup.test.ts`, `playwright.config.ts`,
`README.md` (the database, backups, the platform package), `docs/SPEC.md` (status, tech stack,
`db:generate` and `smoke`, the testing section, the `node_modules` line), `docs/decisions.md`
(D15 to Decided), `AGENTS.md`, `PRODUCT.md` (project state).

**Size:** L. One coherent unit: D15's validation needs the client, the migrator and startup
together in the built server.

## Task 2: logging with redaction, and `handleError`

**Ports** obzorarr #326, with #339, #340 and #342's redaction, and the owner's `handleError`.

**Description:** The app's own logger: four levels, one JSON line per entry on standard output,
redacted before it is written, with debug behind `ZONDARR_LOG_DEBUG`. A failed startup step is
logged, then thrown. `handleError` writes every unexpected error through the logger.

**Acceptance criteria:**
- [ ] `server/logging/redact.test.ts` first fails, then passes: one case for each of the spec's
  rules and each nested; the allowlist (`keyId`, `authError`, exact match, values still cleaned);
  encoded nested URLs up to three times, including a bare decoded query (`u=token%3Dabc`); and the
  linear-time growth check, including a long run of capitals in a name.
- [ ] `server/logging/logger.test.ts`: the entry's shape and one line per entry, even for a message
  holding a newline, and debug dropped unless enabled. `server/config/log-debug.test.ts`: `true`,
  `false`, empty as unset, anything else refused without echoing it. `startup.test.ts`: a bad value
  stops startup before the database folder exists (`stat`, never `Bun.file().exists()`, which is
  false for every folder).
- [ ] `server/logging/unexpected-error.test.ts`: an unexpected error becomes one redacted `error`
  entry (a token in its message, stack and cause removed); a 404 and an expected error write
  nothing; what the hook returns is SvelteKit's generic message, never the error's text.
  `hooks.server.ts` exports `handleError`, which only calls it.
- [ ] A startup failure is one log entry and the thrown error; `setup.test.ts` checks a bad
  `ZONDARR_LOG_DEBUG` prints one JSON line, and `secret-key.test.ts` still passes.

**Verification:** the gates; in `preview`, a thrown error in a temporary route (not committed)
prints one redacted JSON line and no stack from SvelteKit, and the page and its `__data.json` show
only "Internal Error".

**Dependencies:** task 1.

**Files:** `server/logging/{logger,redact,unexpected-error}.ts` (+ tests),
`server/config/log-debug.ts` (+ test), `src/env.ts`, `src/hooks.server.ts`,
`server/services/setup/startup.ts` (+ test), `tests/e2e/{setup,secret-key}.test.ts`,
`README.md` (logs), `docs/decisions.md` (D11, and D14's logging half to Decided), `docs/SPEC.md`,
`AGENTS.md`.

**Size:** M.

## Task 3: shutdown

**Ports** obzorarr #327.

**Description:** On `SIGTERM`, `SIGINT` and `SIGHUP` (passed on to adapter-bun as `SIGTERM`), stop
the jobs and timers (none yet) while the adapter drains; on `sveltekit:shutdown`, close the
database, flush the logs and exit 0, or exit non-zero after the 5-second deadline. Handlers only in
the built server, installed a turn after `init` resolves.

**Acceptance criteria:**
- [ ] `server/services/setup/startup.test.ts` first fails, then passes, against a stand-in
  process: `SIGHUP` passed on, exit 0 only after the cleanup, the close before the flush, a failed
  close logged and still exit 0, exit 1 when the cleanup throws and at the deadline (its own entry
  flushed for at most 250 ms), exit 1 once the deadline has fired even if the cleanup then finishes,
  and no handler in `dev`. `logger.test.ts`: `flushLogs()` waits for every entry's own write,
  through a real shell pipe whose reader is slow.
- [ ] `setup.test.ts`: `SIGHUP` and `SIGTERM` each shut the built server down with exit code 0.
- [ ] The README lists adapter-bun's `SHUTDOWN_TIMEOUT`, `CONNECTION_IDLE_TIMEOUT` and
  `BODY_SIZE_LIMIT`, and says the container's stop timeout must exceed `SHUTDOWN_TIMEOUT` plus
  5 seconds.

**Verification:** the gates; Ctrl+C still stops `bun run --bun dev`.

**Dependencies:** task 2.

**Files:** `server/services/setup/startup.ts` (+ test), `server/logging/logger.ts` (+ test),
`src/hooks.server.ts`, `tests/e2e/setup.test.ts`, `README.md`, `AGENTS.md`.

**Size:** M.

## Task 4: health

**Ports** nothing: zondarr's ground-floor choice 5, shaped after the legacy app's `/health`.

**Description:** `/healthz` reports the database check, and `/healthz/live` and `/healthz/ready`
join it, as the spec's table says: JSON, `no-store`, no version, no error text.

**Acceptance criteria:**
- [ ] `server/services/health.test.ts` first fails, then passes: each answer with a working and a
  failing (and a slow, time-limited) database check, and a failure logged.
- [ ] Each route test (`server.test.ts` beside each `+server.ts`) checks its status, body and
  `cache-control`.
- [ ] `smoke.test.ts` and `setup.test.ts` read the new answers; the README says the container
  probes `/healthz/live`.

**Verification:** the gates.

**Dependencies:** task 2 (the logger), which follows task 1 (the database); after task 3 in order.

**Files:** `server/services/health.ts` (+ test), `server/db/client.ts` (the health query),
`src/routes/healthz/{,live/,ready/}+server.ts` (+ tests), `tests/e2e/{smoke,setup}.test.ts`,
`README.md`, `docs/SPEC.md` (ground-floor choice 5 closes, the testing section), `AGENTS.md`.

**Size:** M.

## Checkpoint: after task 4

- [ ] As in [plan.md](plan.md#checkpoint-after-task-4).

## Task 5: `ORIGIN`, the security headers and the CSP

**Ports** obzorarr #328.

**Description:** `config/origin.ts` reads and checks `ORIGIN` at startup. `handle` gains the
headers stage after the language; SvelteKit's `csp` option sets the nonce policy on every page.
Ground-floor choice 3 closes.

**Acceptance criteria:**
- [ ] `server/config/origin.test.ts` first fails, then passes: every accepted form; an empty value,
  a path (also `/..` and `/%2e`), query, fragment or credentials refused without echoing it; checked
  before the database file is created (`startup.test.ts`).
- [ ] `server/security/headers.test.ts`: the spec's headers for HTTPS through `ORIGIN`, HTTPS
  through `Sec-Fetch-Site`, plain HTTP, `localhost`, `*.localhost` and loopback hosts, never
  `includeSubDomains`, and an immutable response copied first.
- [ ] `setup.test.ts`: the headers on a page, the health paths and a 404, no HSTS over plain HTTP;
  the policy directive for directive, the nonce on every script, no CSP violation; the server
  refuses `ORIGIN=https://u:p@host` and `https://host/app` without echoing either.

**Verification:** the gates; `preview`'s headers checked by hand at `/` in English and Danish.

**Dependencies:** task 4.

**Files:** `server/config/origin.ts` (+ test), `server/security/headers.ts` (+ test), `src/env.ts`,
`src/hooks.server.ts`, `server/services/setup/startup.ts` (+ test), `vite.config.ts`,
`tests/e2e/setup.test.ts`, `README.md` (`ORIGIN`), `docs/SPEC.md` (ground-floor choice 3 closes),
`AGENTS.md`.

**Size:** M.

## Task 6: the cross-origin check

**Ports** obzorarr #329; `security/cross-origin.ts` is copied as it is.

**Description:** The check after the language and the headers, on every method but GET, HEAD and
OPTIONS; SvelteKit's own form check goes off in the same PR. A refusal is the "Access denied"
page with its own policy and `<html lang>`, or `{ message }` for JSON callers.

**Acceptance criteria:**
- [ ] `server/security/cross-origin.test.ts` first fails, then passes: the spec's matrix, with
  repaired, `null`, malformed and repeated `Origin`s on every branch, default ports, IPv6,
  subrequests, and requests with neither header refused (zondarr has no machine routes).
- [ ] `vite.config.test.ts` (in Vitest's `include`) asserts the exported options trust every origin
  and leave remote functions off. `server/security/access-denied.test.ts`: the page and the JSON
  error in both languages, with the page's policy.
- [ ] `setup.test.ts`: a cross-site form POST gets the 403 page with the headers, its policy and
  Danish for a Danish browser; a same-origin POST without `Sec-Fetch-*` passes (SvelteKit's 405)
  on `localhost` and on `app.test` through `--host-resolver-rules`, read with `headerValue()`.

**Verification:** the gates.

**Dependencies:** task 5.

**Files:** `server/security/{cross-origin,access-denied}.ts` (+ tests), `src/hooks.server.ts`,
`vite.config.ts`, `vite.config.test.ts`, `messages/{en,da}.json`, `tests/e2e/setup.test.ts`,
`README.md` (when `ORIGIN` or the proxy fix is needed), `docs/SPEC.md`, `AGENTS.md`.

**Size:** M.

## Checkpoint: after task 6

- [ ] As in [plan.md](plan.md#checkpoint-after-task-6).

## Task 7: the bootstrap token

**Ports** obzorarr #330, with #341's fake clock.

**Description:** While no owner exists, startup prints the token line to standard output, outside
the logs, and a new one every 15 minutes; shutdown stops the timer; first run's state loads into
memory at startup.

**Acceptance criteria:**
- [ ] `server/security/bootstrap-token.test.ts` first fails, then passes: the format and alphabet,
  biased bytes drawn again (a mocked byte stream), display, accepted and refused entries, constant
  time comparison, and the 15-minute boundary.
- [ ] `server/services/setup/first-run.test.ts`, with a faked clock: a token and a new one at
  expiry (none at 59 ms of a 60 ms life, one at 60 ms); the full address with `ORIGIN`; none after
  stopping or once an owner exists. `db/owner.ts` gains `ownerExists`; `owner.test.ts` checks it
  and the schema's one-row limit.
- [ ] `startup.test.ts`: `SIGTERM` and `SIGINT` stop first run's timer (`stopWork`).
- [ ] `setup.test.ts`: the token line before "Listening on"; neither form of the token in a log
  entry or a response.

**Verification:** the gates.

**Dependencies:** task 6.

**Files:** `server/security/bootstrap-token.ts` (+ test), `server/services/setup/first-run.ts`
(+ test), `server/services/setup/startup.ts` (+ test), `server/db/owner.ts` (+ test),
`tests/e2e/setup.test.ts`, `AGENTS.md`.

**Size:** M.

## Task 8: the claim at `/setup`

**Ports** obzorarr #331 with #337 and #342's password fixes; the common-password list is copied.

**Description:** The claim form and its action, in the spec's order: the fields, the token, the
hash, then one transaction that creates the owner and moves the step pointer. It completes first
run and sends the browser to `/`; then `/setup` and its action answer "not found". No gate yet. The
page is zondarr's first surface, so it brings the fonts and icons.

**Acceptance criteria:**
- [ ] `server/security/password.test.ts` first fails, then passes: the rules at their limits, NFC
  and case, the patterns (`ΣΣΣ…`, `İabc…` included), "zondarr" and the username (its 4-character
  floor counted as written, before lower-casing: `İab`), the list, and an argon2id round trip.
  `server/services/setup/claim.test.ts`: success; a field error leaving the token unused; wrong and
  expired tokens never reaching the hash (the expired case with `Date.now` frozen past 15 minutes,
  so a renewal can't make it pass); a second claim; two at once; a failed transaction printing a new
  token, but not during shutdown. `first-run.test.ts`: a restart reads the claim back, and the
  renewal waits while a claim is in progress (`withClaimInProgress`, which lands here with its first
  caller).
- [ ] `settings.test.ts` and `owner.test.ts`: `readSetting`, `writeSetting` and `insertOwner`, a
  second insert refused, and the creation and update times stored and read back in UTC.
- [ ] `setup.test.ts`: a wrong token refused with the spec's message, the username kept and the
  rest cleared; the right one, in upper case without dashes, claims and lands on `/`; `/setup` and
  its action then answer 404, also after a restart; neither the token nor the password in a
  response (every body awaited) or a log entry. On `/setup`, Outfit and IBM Plex Mono load
  (`document.fonts`) with no CSP violation. `src/routes/setup/token-format.test.ts` covers the
  dashes.
- [ ] The page follows `route-setup.md` through `/impeccable`, every string a `setup_…` message in
  both languages, with the Outfit, IBM Plex Mono and `@lucide/svelte` packages added and the font
  tokens naming them. Checked at 360, 390, 768 and 1440 px, 200% zoom, the keyboard, reduced
  motion, without JavaScript, and every state the brief names, in English and Danish, with
  screenshots in the PR body.

**Verification:** the gates; a claim by hand in `preview` over plain HTTP from a LAN address.

**Dependencies:** task 7.

**Files:** `server/security/{password.ts,common-passwords.txt}` (+ test),
`server/services/setup/{claim,first-run}.ts` (+ tests), `server/db/{owner,settings}.ts` (+ tests),
`src/routes/setup/{+page.svelte,+page.server.ts,token-format.ts}` (+ test),
`src/routes/+layout.svelte`, `panda.config.ts`, `package.json`, `bun.lock`,
`messages/{en,da}.json`, `tests/e2e/setup.test.ts`, `.impeccable/surfaces/route-setup.md` (its
status, through Impeccable), `docs/SPEC.md` (tech stack, ground-floor choice 1), `AGENTS.md`.

**Size:** L. One coherent unit: the credential rules have no caller before the claim, and the page
is what the fonts and icons are for.

## Task 9: the setup gate

**Ports** obzorarr #332.

**Description:** The gate is the last stage in `handle`: until first run is complete, every request
except `/setup` and the three health paths gets a 303 to `/setup`. Playwright's global setup claims
the instance through the form, so the smoke and language tests run on a claimed instance.

**Acceptance criteria:**
- [ ] `first-run.test.ts` gains the gate's decision for each path (`/`, an unknown page, `/setup`,
  `/setup/more`, the three health paths and `/healthz/more`), before and after the claim and after
  a restart.
- [ ] `setup.test.ts`: every page sends a fresh instance to `/setup`, while the health paths
  answer; the gate's redirect carries the headers; a same-origin POST gets the 303 while unclaimed
  and the 405 once claimed; after a restart on a claimed file, `/` is served. The earlier cases
  that need a claimed server claim it first through a `claim(server)` helper that posts with
  `Origin` set to the server's address and `Accept: text/html` (SvelteKit answers a form action to
  `*/*` in JSON), without following the 303 to `/`: the headers on a 404 and
  the same-origin POST on `app.test`; the CSP check reads `/setup`.
- [ ] `playwright.config.ts`: `wait.stdout` from the token line through "Listening on" replaces the
  `url` check, its named group putting the token in `ZONDARR_E2E_SETUP_TOKEN`;
  `tests/e2e/global-setup.ts` claims through the form; `smoke.test.ts` and `i18n.test.ts` pass
  unchanged. The README's first run is written.

**Verification:** the gates; success criterion 2 by hand from another machine on the network.

**Dependencies:** task 8.

**Files:** `server/services/setup/first-run.ts` (+ test), `src/hooks.server.ts`,
`tests/e2e/global-setup.ts`, `tests/e2e/setup.test.ts`, `playwright.config.ts`, `README.md`,
`docs/SPEC.md`, `AGENTS.md`.

**Size:** M.

## Checkpoint: complete

- [ ] As in [plan.md](plan.md#checkpoint-complete).

## Task 10: close the work stream

**Description:** Cleanup procedure 2: mark `setup` built in SPEC.md (status, row 3, "Open
decisions"), reduce SPEC-setup.md to what code and tests can't say, update AGENTS.md and
PRODUCT.md, and delete `tasks/`. The PR body maps every removed requirement to a test or a
remaining doc (the preservation gate).

**Acceptance criteria:**
- [ ] Every item in SPEC-setup.md's "Docs this module changes when built" is done.
- [ ] Nothing in SPEC-setup.md is cut without a test or doc named for it in the PR body.

**Verification:** prek (the `docs-set` hook) and CI.

**Dependencies:** task 9.

**Files:** `docs/SPEC.md`, `docs/SPEC-setup.md`, `AGENTS.md`, `PRODUCT.md`, `tasks/` (deleted).

**Size:** S.
