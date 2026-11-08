# Implementation plan: `i18n`

## Overview

Build module 2 of the capability map as [docs/SPEC-i18n.md](../docs/SPEC-i18n.md) specifies, ported
from obzorarr, the reference app: the messages Paraglide JS compiles, the message check, choosing
each request's language, the language switcher and the formatters, with D22's validations. Three
tasks, one PR each, each test first. The tasks are in [todo.md](todo.md). Each PR follows obzorarr's
(#297 to #301), adapted to zondarr where the spec names a difference.

## Architecture decisions

- **The riskiest work comes early.** Task 1 wires Paraglide into the build, and runs or cites the
  Weblate round trip, before any product text renders from it, so a surprise in the toolchain or
  the file format changes nothing written in it. Task 2 then runs the middleware through the built
  adapter-bun server, where Paraglide issue
  [#725](https://github.com/opral/paraglide-js/issues/725) would show, and runs or cites the
  concurrency check.
- **The message check lands with the messages.** Task 1 adds `messages.test.ts` (obzorarr's #301),
  so every message from the first one on is checked. Its tests come first: with `checkMessages`
  stubbed to return `[]`, every case that breaks a rule fails.
- **Every PR leaves `main` working.** Task 1 compiles the placeholder's messages, but the page keeps
  its own text until task 2 adds the server's language handle and the browser hook. A hydrated page
  that called `m.*()` without them would let the browser runtime choose a language by itself and
  write the cookie the viewer never asked for (SPEC-i18n.md, "In the browser").
- **The server, the browser and the switcher change together.** Task 2 adds both hooks, because
  each half alone is wrong: the server's choice means nothing if the browser chooses again on
  hydration. The switcher joins them, so `i18n.test.ts` lands whole and closes D16's "browser
  interaction with a real component".
- **Each validation's evidence goes in the body of the PR that runs it:** the pinned versions with
  no Node on `PATH` and the Weblate round trip in task 1's, the concurrency check in task 2's, and
  the full list in task 3's, which closes D22. The round trip and the concurrency check cite
  obzorarr's #297 and #298 only when the PR body shows the match SPEC-i18n.md's "Citing obzorarr
  instead" lists; otherwise they rerun. The temporary messages, route and scripts are never
  committed.
- **Facts change in the task that changes them.** Each task updates SPEC.md's tech stack, setup
  facts, Commands and testing sections, and AGENTS.md's structure, as its files land. Task 3 does
  the rest of the spec's "Docs this module changes when built" list and the end-of-work-stream
  cleanup.
- **Every PR names its sibling apps** (AGENTS.md, Shared groundwork): comradarr, otpravkarr and
  zimuarr port the same module; obzorarr gets any bug fix this port finds.

## Task list

### Phase 1: the toolchain

- [ ] Task 1: Paraglide compiles the messages, and the message check

### Phase 2: each page in the viewer's language

- [ ] Task 2: each request gets the viewer's language, the browser keeps it, and the switcher

### Checkpoint: after task 2

- [ ] `check`, `test`, `lint`, `build`, `smoke` and prek pass; CI's `checks`, `smoke` and `ci-ok`
  pass.
- [ ] The built server serves `/` in Danish to a Danish browser and in English otherwise, the
  switcher changes it, and `/healthz` is unchanged.

### Phase 3: the tools later modules write through

- [ ] Task 3: formatting numbers and dates, and closing `i18n`

### Checkpoint: complete

- [ ] Every success criterion in SPEC-i18n.md is met.
- [ ] The end-of-work-stream cleanup (AGENTS.md, "Cleanup procedures") is done in task 3.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The middleware returns nothing in the adapter-bun build (#725) | High | Task 2's e2e tests run against the built server, before any formatter exists |
| The CLI and the Vite plugin write different layouts into one folder | Medium | `outputStructure: "message-modules"` in the shared config; task 1 runs `check` beside `dev` |
| Weblate writes the files in a shape Biome or the plugin refuses | Medium | Task 1's round trip, or its citation when nothing has moved, before any real message renders |
| Concurrent requests mix languages under Bun's AsyncLocalStorage | High | Task 2's 200-request check against the built server, or its citation |
| A version or file moves after the spec, so obzorarr's evidence no longer applies | Medium | Each PR body compares the list in SPEC-i18n.md's "Citing obzorarr instead" with `7368cff`, and reruns on any difference |
| Generated output trips Biome, Panda or the docs-set hook | Low | The two `.gitignore` lines and Panda's `exclude` land in task 1; prek runs with the output present |
| The agents' Danish reads badly | Low | The owner may spot-check it; Weblate corrects it later (SPEC-i18n.md, "Who writes them") |

## Open questions

None for the build. The owner approves the spec and this plan before task 1 starts; the choices the
port made in their absence are in the spec PR's body under "Decided by council".
