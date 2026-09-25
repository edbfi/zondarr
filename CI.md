# CI and dependency maintenance

All pull requests and default-branch pushes run Python, frontend, production
integration and hygiene checks. `ci / required` directly requires every job;
missing, skipped, failed or cancelled jobs fail the aggregate.
The separate `policy / ci / policy` check validates Conventional Commit titles,
author-matching DCO, Renovate provenance, outstanding review requests, objections
and hold labels. Label and review events refresh policy independently of app CI.
After a pass, policy re-runs the other event's older failed verdict for the same
head, which needs `actions: write`.
Require the actual emitted aggregate and policy contexts from GitHub Actions,
current branches and native review rules before enabling dependency automerge.

The legacy checked merger and `/merge` commands are retired. Renovate is the only
merger: the shared v4 `automerge.json` preset arms GitHub auto-merge with rebase
merges, so GitHub merges once every required check passes. Complete current-head
CI and policy checks, up-to-date branches, release ages, reviews and holds remain
required. Validation is read-only, bounded by timeouts, uses immutable
full-version references and rejects tracked-file mutations. This repository has
no helper-dispatched deployment workflow; normal default-branch CI remains on push.

## Local commands and coverage

Use Python 3.14, latest stable uv and Bun 1.4.2. CI logs the resolved versions;
separate runs can resolve different uv releases. Frozen installs and `uv lock --check` validate the
committed resolution. `bash .github/scripts/check-python.sh` runs locked Ruff across
backend, migrations, the development launcher and CI helpers; recommended
basedpyright across backend and launcher; all backend tests with four workers; the
launcher's 39 tests; and Python wheel/source builds. The same locked Ruff drives
prek, removing the separate hook-version mismatch. Launcher security-lint exceptions
identify existing developer-PATH subprocesses, internal assertions and synthetic
test credentials at their narrow source/file scope.

`bun install --cwd frontend --frozen-lockfile` prepares SvelteKit types. Run
`bun run --cwd frontend check:biome`, `check`, and `test`; Vitest is bounded to four
workers. Biome is pinned exactly and upgraded together with its lockfile and schema. The full root-aware check also covers the API-check helper. Existing
custom ARIA groups/radios/checkboxes, drag containers and dismiss overlay have
localized explanations for keeping their established controls/layout. Log selection
now uses a real button with keyboard activation and a selected-state announcement;
its component test exercises Enter and Space. Standalone SVGs have accessible titles.
One pre-existing unused snippet parameter warning and four style advisories remain
visible; Svelte/TypeScript and Python types must have zero errors and warnings.

Integration builds the frontend once, runs `bun .github/scripts/check-api.ts`, then
`python .github/scripts/smoke.py`. The API check generates declarations from the
actual backend OpenAPI schema and compares parsed declarations without comments,
because Litestar's illustrative example dates vary. It never rewrites tracked API
types. The smoke applies real Alembic migrations to a temporary database, starts
Granian via the repaired installed `zondarr` entry point and the built Bun server,
and verifies database readiness, API proxy parity, setup SSR and bootstrap-token
handoff over loopback. A required Chromium test then loads the production setup
page, fills the account form, observes the hydrated Svelte password-strength state and verifies mismatched
password validation without creating an account. Unhandled page errors fail the
check. Both processes and all temporary database/token data are cleaned up.

Install the locked browser with `bun run --cwd frontend smoke:install` locally
(CI adds `--with-deps`), then run the existing Python smoke entry point. The
browser test has a 30-second deadline, no retries and a 90-second subprocess cap.
Failed browser traces/screenshots are retained under `frontend/test-results` and
uploaded by CI for seven days. Root tooling and frontend have independent frozen
Bun locks; the frontend reusable job explicitly selects `install-directory: frontend`.

## Renovate and remaining limits

The v4 default/mixed presets handle Python/uv, Bun, actions, hooks and Biome
schema/package versions, grouping non-major updates by ecosystem. `automerge.json`
has no wildcard rule, so the shared manual rule for automation configuration
updates still wins. The existing Ruff group and ignored repair-bot author are
retained.
Svelte checks remain mandatory and the TypeScript 7 hold remains in place.
Normal PR rebase merges retain genuine commit sign-offs. Source policy checks cannot atomically bind a label change to a
merge, so native review enforcement and hosted metadata-event checks are also
required before opt-in.

Biome repair resolves the frontend standalone text Bun lock and migrates both
configs using only the exact isolated official formatter; it does not install the
application dependency tree. It computes with read-only permissions; a separate
publisher writes allowlisted frontend changes. Only the final non-force branch
update uses the installed
`edbfi-renovate-repair` App, scoped to this repository with Contents write. The App
credential is unavailable to dependency installation and repair computation. The
publisher revokes its temporary installation token when the job ends.

The caller supplies `RENOVATE_REPAIR_APP_CLIENT_ID` and the
`RENOVATE_REPAIR_APP_PRIVATE_KEY` Actions secret. Missing credentials fail closed.
App publication starts the normal `pull_request` CI and policy runs on the repaired
commit; nothing is dispatched. All required CI and policy contexts must succeed for
the current head and base.
Legacy workflow-token updates that suppress policy events remain blocked until a
supported Renovate/App update triggers complete PR CI and policy.
Renovate owns branch rebases and lockfile regeneration; only the existing repair-bot
author is ignored.
CI helper changes and repairs beyond shared size limits need manual handling.
Shared releases reach consumers through Renovate PRs using immutable full tags.

Tests use SQLite and fixture media clients, not live Plex/Jellyfin or PostgreSQL.
Chromium coverage is a bounded production setup startup/hydration test; it does
not establish complete browser workflows, visual/accessibility coverage or
Firefox/WebKit behavior. The dev launcher retains its existing
all-interface backend listener. Backend tests expose an existing coroutine cleanup
warning in a mocked probe; it is visible in CI logs. External container packaging
and deployments remain separate from these development gates.
