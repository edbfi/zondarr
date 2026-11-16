# Implementation plan: `setup`

Source spec: [docs/SPEC-setup.md](../docs/SPEC-setup.md), approved by the owner on 2026-11-16.

## Overview

Build module 3 of the capability map as SPEC-setup.md specifies: startup checks, the database and
its migrations, logging with redaction, health, the security headers and CSP, the cross-origin
check, and first run, which ends at the claim. Nine tasks, one PR each, each test first, then a
docs PR that ends the work stream. The tasks are in [todo.md](todo.md).

`setup` is a port: obzorarr is the reference (AGENTS.md, Shared groundwork), and each task starts
from the matching obzorarr PR (#325–#332, with the follow-ups #337–#342 folded in) and its code and
tests at `b59b909`, rebuilt for zondarr's names, decisions and design. The split is obzorarr's
#324, with two tasks added: health (zondarr's ground-floor choice 5) and the owner's addition of
`handleError`, which goes with the logger.

## Architecture decisions

- **The riskiest part lands first.** Task 1 is D15's validation: the Drizzle and Turso pair, the
  bundled migrations and Turso's native binding beside `build/`. obzorarr found the binding can't
  be bundled and the record migrator works, so task 1 confirms both on zondarr's pins rather than
  discovering them.
- **The startup service grows task by task.** Task 1 creates `services/setup/startup.ts` with the
  spec's steps 1–3: the key, the configuration and the database. `ZONDARR_LOG_DEBUG` (task 2) and
  `ORIGIN` (task 5) join step 2, so they are checked before the database is opened; shutdown (task
  3) and first run's state and token (tasks 7 and 8, step 4) follow. `hooks.server.ts` only calls
  it, because hooks never touch `db/` (Code structure).
- **Startup failures are thrown first and logged later.** Until task 2 brings the logger, a failed
  step throws from `init` exactly as the key error does now; task 2 adds "logged, then thrown".
- **`handleError` comes with the logger.** Task 2 adds the hook, so from then on no unexpected
  error reaches SvelteKit's unredacted `console.error`. Its entry is built in
  `logging/unexpected-error.ts`, which the hook only calls, so it is unit-tested without a server.
- **Health before the request checks.** Task 4 replaces `/healthz` with the three answers right
  after the database exists, so every later task's headers, cross-origin and gate tests cover the
  three paths from the start. The container's `/healthz/live` never touches the database.
- **The request checks come before any form.** SvelteKit's own form check compares `Origin` with
  an `event.url` that adapter-bun builds as `https`, so it would refuse the claim over plain HTTP.
  Task 6 switches it off and puts the cross-origin check in its place in one PR, so `main` never
  has neither; its e2e posts to `/`, which passes the check and gets SvelteKit's 405.
- **The gate comes last.** Task 8 makes the claim work at `/setup` with every other page still
  served, so the smoke and language tests keep running unchanged. Task 9 adds the gate, together
  with the Playwright global setup that claims the instance for those tests, so no PR leaves the
  e2e suite on an unclaimable instance.
- **The first surface brings its fonts and icons.** Task 8 adds the Outfit and IBM Plex Mono
  packages and `@lucide/svelte`, with the font tokens naming them ahead of their fallbacks, because
  the claim page is the first to show them; nothing merges unused.
- **Named operations join with their first caller.** Task 1 writes both tables into the first
  migration (with the owner's update time); each operation in `db/owner.ts` and `db/settings.ts`
  lands with the task that first calls it.
- **The migrator** is Drizzle's record migrator for Turso (`drizzle-orm/tursodatabase/wasm-migrator`
  in rc.5), fed by `import.meta.glob("/drizzle/*/migration.sql", { query: "?raw" })` with the
  folder names as keys. Task 1 compares its rows with Drizzle Kit's file migrator's and records the
  empty `hash` in D15.
- **The handle-built refusal page is unstyled.** Its fixed policy allows no stylesheet or font, and
  Panda's colours are semantic tokens with no value outside its stylesheet, so the page sets only
  `color-scheme: dark` and holds no raw values (D10), until `sign-in` builds the error pages.
- **Signal handlers only in the built server.** `init` runs in `dev` too, and a `SIGINT` listener
  there would stop Ctrl+C from ending it, so task 3 installs them only when `dev` is false.
- **Generated migrations are formatted.** Drizzle Kit writes `snapshot.json` with spaces, so
  `db:generate` runs `biome format --write drizzle` after it; the shared `biome.json` stays
  unchanged.
- **Code is rebuilt, not copied blind.** Each task reads the obzorarr module and its tests, writes
  zondarr's tests first (failing), then the code. `security/cross-origin.ts` and the common-password
  list are the exceptions the spec names: copied as they are.
- **Facts change in the task that changes them.** Each task updates the README, SPEC.md (status,
  tech stack, Commands, the testing section), decisions.md, PRODUCT.md's project state and
  AGENTS.md's status and structure where it changes them, and ticks off its items here. Task 10
  reduces the spec and deletes `tasks/`.

## Task list

### Phase 1: the foundations

- [x] Task 1: the database (D15)
- [x] Task 2: logging with redaction, and `handleError`
- [x] Task 3: shutdown
- [x] Task 4: health

### Checkpoint: after task 4

- [x] `check`, `test`, `lint`, `build`, `smoke` and prek pass; CI's `checks`, `smoke` and `ci-ok`
  pass.
- [x] The built server migrates a new database, logs JSON lines, refuses a bad configuration with
  one line, answers the three health paths, and exits 0 on `SIGTERM` and `SIGHUP`.

### Phase 2: the request checks

- [x] Task 5: `ORIGIN`, the security headers and the CSP
- [ ] Task 6: the cross-origin check

### Checkpoint: after task 6

- [ ] Every page and the health paths carry the headers; pages carry the nonce CSP with no
  violation.
- [ ] A cross-site POST gets the "Access denied" page, in the viewer's language.

### Phase 3: first run

- [ ] Task 7: the bootstrap token
- [ ] Task 8: the claim at `/setup`
- [ ] Task 9: the setup gate

### Checkpoint: complete

- [ ] Every success criterion in SPEC-setup.md is met.

### Phase 4: closing

- [ ] Task 10: close the work stream (cleanup procedure 2)

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| A newer Turso or Drizzle `rc` than obzorarr's pins behaves differently (bundling, the migrator, rollback) | High | Task 1 validates whatever D5 and D26 allow when it starts; the rollback test fails on rc.4 |
| Turso's native binding missing beside `build/` | High | Task 1 runs the built server with `--no-install`; the README and SPEC.md say the platform package ships beside `build/` |
| A rollback undoes an unrelated write on the shared connection (D5's rc.4 bug) | High | Task 1's rollback-isolation test, against a file, under Bun |
| An unexpected error reaches the output unredacted | High | Task 2's `handleError`, with a unit test that a token in an error's message and stack is redacted |
| A crafted URL or name stalls the logger | Medium | Task 2 ports obzorarr's linear-time growth test (#341, #342), which fails a quadratic scan |
| The container restarts in a loop on a database fault | Medium | Task 4: `/healthz/live` doesn't touch the database; the README tells the image to probe it |
| SvelteKit adds a nonce to `style-src`, which turns off `'unsafe-inline'` | Medium | Task 5's e2e listens for CSP violations on a page with style attributes |
| The token or a password reaches a log entry or a response | High | Tasks 7 and 8's e2e search the server's output and every response; task 2's redaction tests |
| Playwright's URL check wins the race against the token line | Medium | Task 9's `wait.stdout` pattern spans the token line through "Listening on" and replaces `url` |
| Startup forgets a completed first run after a restart | High | Task 8 loads the step pointer at startup and restarts the built server on a claimed file |
| Timer-based unit tests flake under load | Low | Tasks 7 and 8 fake the clock from the start (obzorarr's #341) |
| No `node` sneaks into the validation | Low | Task 1 runs the gates with failing `node`, `npm` and `npx` shims on `PATH`, as CI does |

## Porting

Each task's PR body says which obzorarr PRs it ports and names any bug found in obzorarr's `setup`
for the final report ("For obzorarr"), never fixed there. Sibling apps need nothing from these
tasks, except where a task finds such a bug.

## Open questions

None. The owner approved the spec, its map changes and its six packages on 2026-11-16. As with
obzorarr's #324, this task list is approved by the orchestrating session after the council's
review, and merged once its review loop ends.
