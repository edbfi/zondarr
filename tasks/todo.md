# Tasks: `secrets`

The spec is [docs/SPEC-secrets.md](../docs/SPEC-secrets.md), and the plan is [plan.md](plan.md).
All tasks land in one PR. Renames everywhere: `OBZORARR` → `ZONDARR`, `Obzorarr` → `Zondarr`,
`obzorarr` → `zondarr`.

- [ ] **Copy** the 14 paths from obzorarr `b9b4737` with exactly those renames:
  `playwright.config.ts`, `src/env.ts`, `src/hooks.server.ts`,
  `src/lib/server/config/secret-key{,.test}.ts`,
  `src/lib/server/security/secrets/{key-text,keyring,secret,cipher}{,.test}.ts`,
  `tests/e2e/secret-key.test.ts`. `keyring-test-` stays as is. If a leak test fails only because a
  renamed temp-folder prefix (`zondarr-secret-key-`, `zondarr-e2e-`) shares 6 characters with what
  it checks, use a prefix without the app name and declare it.
- [ ] **Prove the copy.** For each path,
  `diff <(git -C <obzorarr> show b9b4737:$f | sed '<renames>') $f` prints nothing beyond the
  declared exceptions, and `git diff --stat origin/main -- src tests playwright.config.ts` lists
  only the 14 paths. The command and its output go in the PR body.
- [ ] **Close the stream** as obzorarr #283's last commit did:
  - `README.md`: obzorarr's "Master key" section with zondarr's names and backups (D16).
  - `AGENTS.md` repo section: status and structure.
  - `docs/SPEC.md`: `secrets` built.
  - `docs/SPEC-secrets.md`: cut to what code and tests can't say, as obzorarr's `b9b4737` copy is,
    keeping zondarr's stored secrets, database and backups; its Status points to zondarr's pre-cut
    commit. The PR body carries the preservation table (cleanup procedure 4), reusing #283's rows.
  - `docs/decisions.md`: fold durable outcomes only if the cut leaves one without a home.
  - Delete `tasks/`. `docs/product/legacy-spec.md` isn't touched: the owner retires it whole later.
- [ ] **Gates.** Before each commit: `check`, `test`, `lint` and
  `prek run --all-files --hook-stage manual`; before pushing: a keyless `build` and `smoke`. By
  hand: the built server with no key exits 1 before listening and prints the fix naming Zondarr.
- [ ] **PR body:** the reference and its commit, the copy proof, the declared exceptions, the
  preservation table, the checks and the review outcome.
- [ ] **Review:** shepherd the PR until it is ready, answering each finding (a finding that
  re-opens a point obzorarr settled is REJECTED, citing the obzorarr PR), then squash-merge and
  clean up.
