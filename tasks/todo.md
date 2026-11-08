# Tasks: `i18n`

The spec is [docs/SPEC-i18n.md](../docs/SPEC-i18n.md), and the plan is [plan.md](plan.md). Each
task is one PR and writes its tests first. Each one adds its files to AGENTS.md's structure, ticks
off its items in `tasks/`, names the sibling apps in its PR body (AGENTS.md, Shared groundwork), and
runs `bun run --bun check`, `bun run --bun test`, `bun run --bun lint` and
`prek run --all-files --hook-stage manual` before every commit. Each PR goes through `file-pr`,
Pullfrog's review and the council until all three delegates are satisfied, with the council table in
its body. Paths under `src/lib/` are shortened to `lib/`.

## Task 1: Paraglide compiles the messages, and the message check

**Description:** obzorarr's #297 and #301's `messages.test.ts`. Add the two packages and the inlang
project, and compile the messages in `prepare`, `check`, dev, build and Vitest. The message files
hold the placeholder page's text in English and Danish, which the page starts using in task 2. Add
the message check. Run the Weblate round trip.

**Acceptance criteria:**
- [x] `@inlang/paraglide-js` and `@inlang/plugin-i18next` are exact-pinned dev dependencies at their
  newest stable releases (D26; SPEC-i18n.md, "Versions"). `project.inlang/settings.json` and
  `project.inlang/paraglide.config.ts` are as the spec gives them, and the Vite plugin is added
  with nothing else.
- [x] `prepare` and `check` compile the messages after `svelte-kit sync` and before Panda's
  codegen, calling the CLI as `bun --bun <bin>`, so a fresh clone's `bun ci` compiles them, and
  `check` then type-checks `project.inlang/*.ts`. Everything passes with no Node on `PATH` (CI's
  shims). Running `check` while `dev` is up doesn't rewrite the output under the dev server.
- [x] A call to a message that doesn't exist fails `check`, shown with a probe that isn't
  committed, its output in the PR body.
- [x] `src/lib/paraglide/` and `project.inlang/cache/` are gitignored, Panda's `exclude` skips the
  output, and `lint` and prek pass with it present.
- [x] The message files are flat and Biome-formatted, their names fit the spec's rule, and the name
  Zondarr inside a message stays "Zondarr" in both languages. The page's text stays as it is until
  task 2.
- [x] **Test first:** once the toolchain compiles, `messages.test.ts` is written with
  `checkMessages` stubbed to return `[]`, and every case that breaks a rule fails (the real files
  and the valid pair pass), as in #301; the output is in the PR body.
- [x] The check passes on `messages/*.json`. Every rule in the spec's list, each clause on its own,
  has an in-memory file that breaks only it and is reported with the exact list of problems; a file
  with several problems reports them all; plain angle brackets in prose pass. Each rule, switched
  off in turn, fails exactly its own cases, shown in the PR body.
- [x] The Weblate round trip passes all four of the spec's conditions, with the script and its
  output in the PR body. It can't cite #297: this task's hooks don't match `7368cff`'s yet
  (SPEC-i18n.md, "Citing obzorarr instead"). Neither the script nor its temporary message is
  committed.

**Verification:** `bun run --bun test`, `check`, `lint`, `build`, `smoke`, prek.

**Dependencies:** none; the spec and this task list were approved by the owner (2026-11-08).

**Files:** `package.json`, `bun.lock`, `project.inlang/settings.json`,
`project.inlang/paraglide.config.ts`, `messages/en.json`, `messages/da.json`, `vite.config.ts`,
`tsconfig.json`, `panda.config.ts` (`exclude`), `.gitignore`, `lib/shared/i18n/messages.test.ts`,
`AGENTS.md`, `docs/SPEC.md` (the tech-stack table, the setup fact, the Commands rows for `bun ci`
and `check`, and the testing section).

**Size:** M.

## Task 2: each request gets the viewer's language, the browser keeps it, and the switcher

**Description:** obzorarr's #298 and #299. Run every request through `paraglideMiddleware` in
`handle`, write the language into `<html lang>`, and keep the page's language in the browser. The
placeholder page renders its text from the messages. `LanguageSwitcher.svelte` as the spec
describes it, on the placeholder `/`, with the global focus rule.

**Acceptance criteria:**
- [x] `tests/e2e/i18n.test.ts`, against the built server, written first: a `da-DK` browser gets `/`
  in Danish with `<html lang="da">` and `Vary: Cookie, Accept-Language`, and "Dansk" is current,
  with `lang="da"`; pressing "English" reloads `/` in English and writes `PARAGLIDE_LOCALE=en` with
  path `/`, `SameSite=Lax` and without `Secure` over plain HTTP, and the next visit stays in
  English; a browser whose header says `fr-FR` and whose `navigator.languages` an init script sets
  to `fr-FR`, `da-DK` gets English, the switcher marks English as current after hydration, no
  cookie is written, and pressing "English" there does nothing (no reload, no cookie); none logs a
  console error.
  `smoke.test.ts` and `secret-key.test.ts` pass unchanged.
- [x] The placeholder renders its messages as text, never with `{@html}`, keeps its layout and
  `<title>Zondarr</title>`, adds no wordmark, and shows the switcher above the heading. No
  `.impeccable/surfaces/*.md` file changes.
- [x] `app.html` has `<html lang="%lang%" class="dark">` with the Biome suppression just above it,
  which doesn't contain the token. `hooks.server.ts` and `hooks.client.ts` are as the spec's Code
  style gives them, and the `init` hook is unchanged.
- [x] The switcher is a labelled group of native buttons, the label a message, each button naming
  its language in that language with `lang` set, from `Intl.DisplayNames` with the first letter
  upper-cased in that language ("English", "Dansk"), through a helper private to the component,
  never a message or a literal. The current language's button has `aria-current="true"` and does
  nothing when pressed; another calls `setLocale`. It is styled only with tokens.
- [x] Keyboard focus is the global `:focus-visible` rule in `panda.config.ts`'s `globalCss`:
  DESIGN.md's 2px `secondary` ring with a 2px offset.
- [x] The concurrency check passes: 200 concurrent requests in both languages against the built
  server, through a temporary route that awaits a random delay in its `load`, each render in their
  own language. The script and its output are in the PR body, or the body shows the match that lets
  it cite #298. Neither the script nor the route is committed.
- [x] D16 no longer lists browser interaction with a real component.

**Verification:** `bun run --bun test`, `check`, `lint`, `build`, `smoke`, prek. Manual check: in
`dev`, a browser set to Danish sees the placeholder in Danish; at 360, 390, 768 and 1440 px, at
200% zoom and with reduced motion, both buttons are reachable by keyboard, focus is visible, and
pressing the current language does nothing.

**Dependencies:** task 1.

**Files:** `src/app.html`, `src/hooks.server.ts`, `src/hooks.client.ts`,
`src/routes/(public)/+page.svelte`, `lib/components/layout/LanguageSwitcher.svelte`,
`messages/en.json`, `messages/da.json`, `panda.config.ts` (`globalCss`), `tests/e2e/i18n.test.ts`,
`docs/decisions.md` (D16), `AGENTS.md`, `docs/SPEC.md` (the testing section, the `smoke` Commands
row and the Design tokens note on focus).

**Size:** M.

## Checkpoint: after task 2

- [x] Everything passes locally and in CI (`checks`, `smoke`, `ci-ok`), and the built server serves
  and switches both languages.

## Task 3: formatting numbers and dates, and closing `i18n`

**Description:** obzorarr's #300 and the close of #301. `formatNumber` and `formatDateTime` in
`lib/shared/i18n/format.ts`, browser-safe, in the current language, with the time zone required.
This task also closes the work stream.

**Acceptance criteria:**
- [ ] `format.test.ts`, written first, runs both inside `paraglideMiddleware` with a request for
  each language: `da` formats as `da`, and `en` as `en-GB`, with the day first and a 24-hour clock.
- [ ] `formatDateTime` follows the zone it is given, not the machine's, and its type refuses a call
  without `timeZone`.
- [ ] Nothing ported from obzorarr's `format.ts`, its tests or its spec cites an instance zone or
  obzorarr's D24 (zondarr's D24 is "Other software"): the zone rule is SPEC-i18n.md's "Which zone".
- [ ] The PR body lists every validation in the spec with its evidence or the PR that holds it.
- [ ] The end-of-work-stream cleanup is done:
  - the rest of the spec's "Docs this module changes when built" list;
  - "locale" becomes "language" at `docs/decisions.md:226` (D21) and `docs/SPEC.md:36` and `:41`
    (line numbers as of `8ea8f56`);
  - row 2 of the capability map is marked **Built.**;
  - the `i18n` line goes from "Open decisions each module closes";
  - D22's "Still to validate in the `i18n` module" paragraph is deleted;
  - the status lines in SPEC.md, AGENTS.md and PRODUCT.md (`:46`) are updated;
  - `tasks/` is deleted;
  - SPEC-i18n.md is cut the way #301 cut obzorarr's, keeping what code and tests can't say, the
    differences from obzorarr included;
  - the PR body maps every removed requirement to a test, a spec or an owner-approved removal, in
    the same preservation gate table as #301's.

**Verification:** `bun run --bun test`, `check`, `lint`, `build`, `smoke`, prek.

**Dependencies:** tasks 1 and 2.

**Files:** `lib/shared/i18n/format.ts`, `format.test.ts`, `docs/SPEC.md`, `docs/SPEC-i18n.md`,
`docs/decisions.md`, `PRODUCT.md`, `AGENTS.md`, `tasks/`.

**Size:** M.
