# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Zondarr: invitation and user management for Plex/Jellyfin. `backend/` is Python 3.14 (Litestar, msgspec, async SQLAlchemy, Granian, uv). `frontend/` is SvelteKit 2 + Svelte 5 runes on Bun 1.4.2 with UnoCSS. `dev_cli/` launches both for local development. `backend/` and `frontend/` each have their own `CLAUDE.md`, loaded when you work there.

## Commands

| Task | Command (run from the repo root) |
| --- | --- |
| Run both dev servers (`:8000` / `:5173`) | `uv run dev_cli` (stop with `uv run dev_cli stop`) |
| Backend tests | `cd backend && uv run pytest` |
| Frontend tests | `bun run --cwd frontend test` |
| dev_cli tests | `backend/.venv/bin/pytest -q dev_cli/tests` |
| Everything CI's `python` job runs | `bash .github/scripts/check-python.sh` |
| Everything CI's `frontend` job runs | `cd frontend && bun run check:biome && bun run check && bun run test` |
| Generated API types still match the backend | `bun .github/scripts/check-api.ts` (needs `backend/.venv` and `frontend/node_modules`) |
| All prek hooks | `bun run lint` (= `prek run --all-files`) |

The scoped files list single-file and single-case commands.

`uv run dev_cli` installs missing deps (`uv sync --extra dev`, `bun install`), applies Alembic migrations, and keeps a generated `SECRET_KEY` in `backend/data/.secret_key`. It also sets `DEBUG`, `CORS_ORIGINS`, `PUBLIC_API_URL` and `BOOTSTRAP_TOKEN_FILE`. `--skip-auth` sets `DEV_SKIP_AUTH`, which the backend honours only when `DEBUG` is also true.

## Repo-wide gotchas

- Commits to `main` are blocked by prek's `no-commit-to-branch` hook once the hooks are installed. Running `bun install` at the root installs them via `prepare`. Work on a branch.
- prek's pre-push stage runs basedpyright, svelte-check, backend pytest, dev_cli pytest and vitest. When `git push` fails locally, it is usually these hooks and not the remote. Commit messages must be Conventional Commits (a `commit-msg` hook checks them).
- Ruff is pinned (`ruff==0.16.8` in `backend/pyproject.toml`), and prek and CI both run it through the backend project: `uv run --project backend --frozen ruff check --fix <paths>`. `dev_cli/` and `.github/scripts/` inherit the backend Ruff config through `extend`.
- Changing the backend's OpenAPI surface also means regenerating `frontend/src/lib/api/types.d.ts`. CI's integration job fails on any drift. See `frontend/CLAUDE.md`.
- Backend and frontend reach each other two ways. In production, the browser calls same-origin `/api/*`, which `frontend/src/routes/api/[...path]/+server.ts` proxies to `INTERNAL_API_URL`. In dev, `dev_cli` sets `PUBLIC_API_URL`, so the browser calls `:8000` directly and relies on `CORS_ORIGINS`. The proxy forwards `Origin`/`Referer` because `backend/src/zondarr/core/csrf.py` validates them. Don't strip those headers.
- Tests use SQLite and fake media clients. Nothing talks to real Plex/Jellyfin or PostgreSQL.

## Reference files

- `.agents/rules/python-3_14-litestar-api.md` covers general Litestar, msgspec and Granian guidance. It is generic: where it disagrees with this repo, follow the repo (see the table in `backend/CLAUDE.md`). Read it before writing unfamiliar Litestar or msgspec code.
- `.agents/rules/svelte5-sveltekit-app.md` covers general Svelte 5 runes, SvelteKit, UnoCSS and shadcn-svelte guidance. It is generic: where it disagrees with this repo, follow the repo (see the table in `frontend/CLAUDE.md`). Read it before writing new components.
- `.env.example` lists every environment variable with its default and how dev_cli and Docker handle it. Read it before touching config, auth or deployment wiring.
