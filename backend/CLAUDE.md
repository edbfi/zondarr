# CLAUDE.md — backend

Run everything below from `backend/`. pytest's config (`testpaths`, `pythonpath`, `-n auto`) lives in `pyproject.toml`, and tests import `tests.conftest`, so running pytest from the repo root finds neither.

| Task | Command |
| --- | --- |
| All tests | `uv run pytest` (xdist `-n auto`; CI and pre-push pin `-n 4`) |
| One file | `uv run pytest tests/test_totp.py -n0` |
| One case | `uv run pytest "tests/test_totp.py::TestTOTPEncryption::test_encrypt_decrypt_roundtrip" -n0` |
| Typecheck | `uv run basedpyright` (`recommended` mode, `migrations/` excluded) |
| Lint / format | `uv run --frozen ruff check --fix . && uv run --frozen ruff format .` |
| New migration | `uv run alembic revision --autogenerate -m "..."` |

`uv sync` without `--extra dev` (or `--all-extras`) leaves out pytest, ruff and basedpyright. The dev tools are in `[project.optional-dependencies].dev`, not in a dependency group.

## Layout and invariants

- Code is layered as `api/` (Litestar controllers, plus msgspec request/response Structs in `api/schemas.py`) → `services/` → `repositories/` (subclasses of `repositories/base.py::Repository[T]`) → `models/`. Controllers build their repositories and services with per-controller `Provide(...)` functions. `api/invitations.py` is the canonical example. There is no Advanced Alchemy and no `SQLAlchemyPlugin`.
- Serialization uses msgspec only. Pydantic appears only as a transitive dependency of `jellyfin-sdk`, and `pyproject.toml` filters its warning.
- The DI `session` (`core/database.py::provide_db_session`) commits after the handler returns and **rolls back if it raises**. Repositories `flush()` and never commit. When state must persist even though the handler then raises (failed TOTP attempts, challenge nonces), call `await session.commit()` before raising, as `api/totp.py` and `api/auth.py` do.
- Domain errors are exceptions from `core/exceptions.py`, mapped to HTTP responses by the `exception_handlers` dict in `app.py::create_app`. A new exception class that doesn't subclass a mapped one falls through to `internal_error_handler` and returns 500.
- Every route requires JWT auth by default. Public handlers opt out with `exclude_from_auth=True` on the decorator. CSRF exemptions are a separate hard-coded set, `_CSRF_EXCLUDE_PATHS_BASE` in `core/csrf.py`.
- `zondarr/app.py` runs `app = create_app()` at import, and that needs `SECRET_KEY` in the environment. Tests must not import `zondarr.app`. Build a minimal `Litestar(route_handlers=[XController], dependencies={"session": ...}, exception_handlers={...})` instead, as `tests/test_settings_controller.py::_make_test_app` does.
- `Settings` (`config.py`) is filled only by the explicit env-to-field dict in `load_settings()`. Adding a field to the Struct alone never reads the environment. Add the env lookup there, and document the variable in `/.env.example`.
- Tests create the schema with `Base.metadata.create_all` and never run Alembic, so a missing migration still passes pytest. It fails only in CI's integration smoke (`.github/scripts/smoke.py`) or at runtime.

## Workflows

**New endpoint / controller**
1. Add request/response Structs to `src/zondarr/api/schemas.py` (`msgspec.Struct, kw_only=True`, plus `forbid_unknown_fields=True` on request bodies).
2. Add a controller in `src/zondarr/api/<name>.py`, and export it from `api/__init__.py`.
3. Add it to the hand-written `route_handlers` list in `app.py::create_app`. Nothing discovers controllers automatically, so until then it is unreachable.
4. Test it with a minimal-app `TestClient` (see above).
5. Regenerate the frontend types and add a wrapper in `frontend/src/lib/api/client.ts` (see `frontend/CLAUDE.md`).

**New table or column**
1. Change or add the model in `src/zondarr/models/`, and export any new model from `models/__init__.py`. `migrations/env.py` and `tests/conftest.py` only see what that module imports.
2. `uv run alembic revision --autogenerate -m "..."`, then review the generated file in `migrations/versions/`.
3. For a new table, add its name to `_TRUNCATE_ORDER` in `tests/conftest.py`, children before parents. Otherwise `TestDB.clean()` leaves its rows behind between Hypothesis examples.

**New media server provider**
1. Create `src/zondarr/media/providers/<name>/` with a `MediaClient` implementation (`media/protocol.py`) and a `ProviderDescriptor` (`media/provider.py`) that may carry its own `route_handlers`. Mirror `providers/jellyfin/__init__.py`.
2. Register it in `media/providers/__init__.py::register_all_providers()`. Nothing discovers providers automatically.
3. Add the type to `KNOWN_SERVER_TYPES` in `tests/conftest.py`, and its capabilities to `BUILT_IN_PROVIDER_CAPABILITIES` in `frontend/src/lib/stores/providers.svelte.ts`.

**New wizard interaction type**
1. Add a member to `InteractionType` in `models/wizard.py`. The column is `String(20)`, so no migration is needed.
2. Add a handler in `services/interactions/handlers.py` and a `case` in `services/interactions/registry.py::_create_handler`. `assert_never` there makes basedpyright flag a missing case.
3. Frontend: add a zod config schema in `src/lib/schemas/wizard.ts`, the interaction component and config editor in `src/lib/components/wizard/interactions/`, and a `registerInteractionType(...)` call in `register-defaults.ts`.

## Where `.agents/rules/python-3_14-litestar-api.md` disagrees with this repo

| Rule file says | This repo does (follow this) |
| --- | --- |
| Advanced Alchemy repositories/services, `SQLAlchemyPlugin` | Own `Repository[T]` base plus a DI session from `core/database.py` |
| `litestar run` with `GranianPlugin` | Plain `granian zondarr.app:app --interface asgi` (dev_cli), or the `zondarr` entry point (`cli.py`) |
| Dev tools in `[dependency-groups]` | `[project.optional-dependencies].dev`, installed with `--extra dev` / `--all-extras` |

Inline `# pyright: ignore[reportAny]` on the offending line is the local way to handle `Any` leaking from third-party code. Don't loosen `typeCheckingMode`.
