# CI and dependency maintenance

All pull requests and default-branch pushes run Python, frontend, production
integration and hygiene checks. `ci / required` requires exactly those jobs and the
dispatch guard. Missing, skipped, failed or cancelled jobs block merging. Renovate updates merge
unattended only after all six current-head checks in `.github/merge-policy.json`
pass. Other changes retain review of the exact head/base, full diff, authors/DCO,
all expected CI and relevant artifacts before merging through ghmerge. GitHub branch protections and rulesets are not
configured. Validation is read-only, bounded by timeouts and concurrency, uses
full version tags, and rejects tracked-file mutation.

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
handoff over loopback. Both processes and all temporary data are cleaned up.

## Renovate and remaining limits

The shared default/mixed presets handle Python/uv, Bun, actions, hooks and Biome
schema/package versions, grouping non-major updates by ecosystem. The versioned
default, mixed and automerge presets make all update types eligible, including
majors and shared-policy updates, without dashboard approval. Svelte checks remain
required to test TypeScript compatibility. The checked merge preserves genuine
sign-offs and dispatches full CI for the exact merged commit.

Biome repair installs from the frontend package directory and migrates both configs.
It computes with read-only permissions; a separate publisher writes allowlisted
frontend changes. Only the final non-force branch update uses the installed
`edbfi-renovate-repair` App, scoped to this repository with Contents write. The App
credential is unavailable to dependency installation and repair computation. The
publisher revokes its temporary installation token when the job ends.

The caller supplies `RENOVATE_REPAIR_APP_CLIENT_ID` and the
`RENOVATE_REPAIR_APP_PRIVATE_KEY` Actions secret. Missing credentials fail closed.
App publication starts normal PR CI; a guarded dispatch also runs complete CI for
the exact repaired SHA. Newest-run validation, all required jobs, current head and
base, review/label restrictions, and a genuine Renovate request still govern merging.
The recovery path deduplicates and bounds dispatches; it never approves workflows
or treats `action_required` as successful validation. Renovate owns branch rebases
and lockfile regeneration; only the existing repair-bot author is ignored.
CI helper changes and repairs beyond shared size limits need manual handling.
Shared releases reach consumers through Renovate PRs using immutable full tags.

Tests use SQLite and fixture media clients, not live Plex/Jellyfin or PostgreSQL.
Browser visual/accessibility coverage is limited to component tests and server smoke;
there is no real-browser E2E suite here. The dev launcher retains its existing
all-interface backend listener. Backend tests expose an existing coroutine cleanup
warning in a mocked probe; it is visible in CI logs. External container packaging
and deployments remain separate from these development gates.
