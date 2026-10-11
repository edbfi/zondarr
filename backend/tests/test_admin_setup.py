"""Tests for admin setup race condition fix and bootstrap token protection.

Tests:
- AdminAccountRepository.create_first_admin (atomic INSERT ... WHERE NOT EXISTS)
- AuthService.setup_admin (lock + atomic DB call)
- Concurrent setup attempts (only one wins)
- Bootstrap token validation on setup endpoint
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.api.auth import AuthController
from zondarr.api.errors import authentication_error_handler
from zondarr.config import Settings
from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount
from zondarr.repositories.admin import (
    AdminAccountRepository,
    AuthSessionRepository,
    RefreshTokenRepository,
)
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import AuthService

# =============================================================================
# Repository: create_first_admin
# =============================================================================


class TestCreateFirstAdmin:
    """Tests for AdminAccountRepository.create_first_admin."""

    @pytest.mark.asyncio
    async def test_creates_admin_when_table_empty(self) -> None:
        """Returns an AdminAccount with correct fields when table is empty."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                admin = await repo.create_first_admin(
                    username="admin",
                    password_hash="hashed_pw",
                    email="admin@example.com",
                    auth_method="local",
                )
                await session.commit()

                assert admin is not None
                assert admin.username == "admin"
                assert admin.password_hash == "hashed_pw"  # noqa: S105
                assert admin.email == "admin@example.com"
                assert admin.auth_method == "local"
                assert admin.enabled is True
                assert admin.id is not None
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_returns_none_when_admin_exists(self) -> None:
        """Returns None on second call; DB still has exactly 1 admin."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                first = await repo.create_first_admin(
                    username="admin1",
                    password_hash="hash1",
                    email=None,
                    auth_method="local",
                )
                await session.commit()
                assert first is not None

            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                second = await repo.create_first_admin(
                    username="admin2",
                    password_hash="hash2",
                    email=None,
                    auth_method="local",
                )
                await session.commit()
                assert second is None

                # Verify only one admin exists
                count = await _count_admins(session)
                assert count == 1
        finally:
            await engine.dispose()


# =============================================================================
# Service: setup_admin
# =============================================================================


class TestSetupAdmin:
    """Tests for AuthService.setup_admin."""

    @pytest.mark.asyncio
    async def test_setup_admin_succeeds(self) -> None:
        """First call returns an admin with correct username."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                service = _make_service(session)
                admin = await service.setup_admin("myadmin", "strong_password")
                await session.commit()

                assert admin.username == "myadmin"
                assert admin.auth_method == "local"
                assert admin.password_hash is not None
                assert admin.password_hash != "strong_password"  # noqa: S105
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_admin_rejects_second_call(self) -> None:
        """Second call raises AuthenticationError with SETUP_NOT_REQUIRED."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                service = _make_service(session)
                _ = await service.setup_admin("admin1", "password1")
                await session.commit()

            async with session_factory() as session:
                service = _make_service(session)
                with pytest.raises(
                    AuthenticationError, match="Setup already completed"
                ):
                    _ = await service.setup_admin("admin2", "password2")
        finally:
            await engine.dispose()


# =============================================================================
# Concurrency: only one setup wins
# =============================================================================


class TestConcurrentSetup:
    """Tests for concurrent setup_admin calls."""

    @pytest.mark.asyncio
    async def test_concurrent_setup_only_one_wins(self) -> None:
        """N concurrent setup_admin calls: exactly 1 succeeds, rest fail."""
        engine = await create_test_engine()
        n = 5
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async def attempt_setup(idx: int) -> AdminAccount | None:
                async with session_factory() as session:
                    service = _make_service(session)
                    try:
                        admin = await service.setup_admin(
                            f"admin{idx}", f"password{idx}"
                        )
                        await session.commit()
                        return admin
                    except AuthenticationError:
                        return None

            results = await asyncio.gather(*[attempt_setup(i) for i in range(n)])

            successes = [r for r in results if r is not None]
            failures = [r for r in results if r is None]

            assert len(successes) == 1
            assert len(failures) == n - 1

            # Verify exactly 1 admin in DB
            async with session_factory() as session:
                count = await _count_admins(session)
                assert count == 1
        finally:
            await engine.dispose()


# =============================================================================
# Service: authenticate_external blocked during setup
# =============================================================================


class TestAuthenticateExternalBlockedDuringSetup:
    """Defense-in-depth: authenticate_external raises SETUP_REQUIRED when no admin exists."""

    @pytest.mark.asyncio
    async def test_authenticate_external_blocked_when_setup_required(self) -> None:
        """authenticate_external raises AuthenticationError with SETUP_REQUIRED."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                service = _make_service(session)
                with pytest.raises(
                    AuthenticationError, match="Initial setup must be completed first"
                ):
                    _ = await service.authenticate_external(
                        "plex",
                        {"auth_token": "fake"},
                        settings=Settings(secret_key="a" * 32),
                    )
        finally:
            await engine.dispose()


# =============================================================================
# Helpers
# =============================================================================


def _make_service(session: AsyncSession) -> AuthService:
    return AuthService(
        admin_repo=AdminAccountRepository(session),
        session_repo=AuthSessionRepository(session),
        token_repo=RefreshTokenRepository(session),
        app_setting_repo=AppSettingRepository(session),
    )


async def _count_admins(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(AdminAccount))
    return result.scalar_one()


# =============================================================================
# Bootstrap Token Endpoint Tests
# =============================================================================

VALID_SETUP_PAYLOAD = {
    "username": "admin",
    "password": "a_very_strong_password_15",
}


def _make_setup_app(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    generated_token: str | None = None,
) -> Litestar:
    """Create a minimal Litestar app with only the AuthController for testing."""

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def provide_settings_fn(state: State) -> Settings:
        return state.settings  # pyright: ignore[reportAny]

    state_dict: dict[str, object] = {"settings": settings}
    if generated_token is not None:
        state_dict["generated_bootstrap_token"] = generated_token

    return Litestar(
        route_handlers=[AuthController],
        state=State(state_dict),
        dependencies={
            "session": Provide(provide_session),
            "settings": Provide(provide_settings_fn, sync_to_thread=False),
        },
        exception_handlers={AuthenticationError: authentication_error_handler},
    )


class TestBootstrapTokenValidation:
    """Tests for bootstrap token validation on the setup endpoint.

    bootstrap_token is always required in the request body. The server
    always validates it against the configured or auto-generated token.
    """

    @pytest.mark.asyncio
    async def test_setup_rejects_when_no_token_configured(self) -> None:
        """Setup returns 401 when no token is configured on the server."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32)
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/setup",
                    json={**VALID_SETUP_PAYLOAD, "bootstrap_token": "any-token"},
                )
                assert response.status_code == 401
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["error_code"] == "INVALID_BOOTSTRAP_TOKEN"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_succeeds_with_valid_env_token(self) -> None:
        """Setup succeeds when correct bootstrap token is provided (env var)."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="my-secret-token")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/setup",
                    json={**VALID_SETUP_PAYLOAD, "bootstrap_token": "my-secret-token"},
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_rejects_invalid_token(self) -> None:
        """Setup returns 401 when wrong bootstrap token is provided."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="correct-token")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/setup",
                    json={**VALID_SETUP_PAYLOAD, "bootstrap_token": "wrong-token"},
                )
                assert response.status_code == 401
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["error_code"] == "INVALID_BOOTSTRAP_TOKEN"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_rejects_missing_token_field(self) -> None:
        """Setup returns 400 when bootstrap_token field is omitted (now required)."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="required-token")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                # Omit bootstrap_token entirely — should fail validation (400)
                response = client.post("/api/auth/setup", json=VALID_SETUP_PAYLOAD)
                assert response.status_code == 400
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_validates_auto_generated_token(self) -> None:
        """Setup validates against auto-generated token stored in app state."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32)
            app = _make_setup_app(
                session_factory, settings, generated_token="auto-gen-token"
            )

            with TestClient(app) as client:
                # Wrong token — rejected
                response = client.post(
                    "/api/auth/setup",
                    json={**VALID_SETUP_PAYLOAD, "bootstrap_token": "wrong-token"},
                )
                assert response.status_code == 401

                # With correct auto-generated token — accepted
                response = client.post(
                    "/api/auth/setup",
                    json={
                        **VALID_SETUP_PAYLOAD,
                        "bootstrap_token": "auto-gen-token",
                    },
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_env_token_takes_precedence_over_generated(self) -> None:
        """When both env var and generated token exist, env var is used."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="env-token")
            app = _make_setup_app(
                session_factory, settings, generated_token="generated-token"
            )

            with TestClient(app) as client:
                # Generated token should be rejected — env token takes priority
                response = client.post(
                    "/api/auth/setup",
                    json={
                        **VALID_SETUP_PAYLOAD,
                        "bootstrap_token": "generated-token",
                    },
                )
                assert response.status_code == 401

                # Env token should be accepted
                response = client.post(
                    "/api/auth/setup",
                    json={
                        **VALID_SETUP_PAYLOAD,
                        "username": "admin2",
                        "bootstrap_token": "env-token",
                    },
                )
                assert response.status_code == 201
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_setup_token_endpoint_removed(self) -> None:
        """GET /api/auth/setup-token returns 404 (endpoint removed)."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="some-token")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.get("/api/auth/setup-token")
                assert response.status_code == 404
        finally:
            await engine.dispose()


# =============================================================================
# Login blocked during setup
# =============================================================================


class TestLoginBlockedDuringSetup:
    """Login endpoints must return SETUP_REQUIRED when no admin exists."""

    @pytest.mark.asyncio
    async def test_local_login_blocked_when_setup_required(self) -> None:
        """POST /api/auth/login returns 401 SETUP_REQUIRED with no admins."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="tok")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login",
                    json={"username": "admin", "password": "password"},
                )
                assert response.status_code == 401
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["error_code"] == "SETUP_REQUIRED"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_external_login_blocked_when_setup_required(self) -> None:
        """POST /api/auth/login/{method} returns 401 SETUP_REQUIRED with no admins."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="tok")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                response = client.post(
                    "/api/auth/login/plex",
                    json={"credentials": {"auth_token": "fake-token"}},
                )
                assert response.status_code == 401
                data: dict[str, object] = response.json()  # pyright: ignore[reportAny]
                assert data["error_code"] == "SETUP_REQUIRED"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_local_login_works_after_setup(self) -> None:
        """POST /api/auth/login succeeds (with valid creds) after admin exists."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="tok")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                # Complete setup first
                setup_resp = client.post(
                    "/api/auth/setup",
                    json={
                        "username": "admin",
                        "password": "a_very_strong_password_15",
                        "bootstrap_token": "tok",
                    },
                )
                assert setup_resp.status_code == 201

                # Now login should not return SETUP_REQUIRED
                # (it should either succeed or fail with INVALID_CREDENTIALS)
                login_resp = client.post(
                    "/api/auth/login",
                    json={
                        "username": "admin",
                        "password": "a_very_strong_password_15",
                    },
                )
                assert login_resp.status_code == 200
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_external_login_not_setup_required_after_setup(self) -> None:
        """POST /api/auth/login/{method} does not return SETUP_REQUIRED after admin exists."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            settings = Settings(secret_key="a" * 32, bootstrap_token="tok")
            app = _make_setup_app(session_factory, settings)

            with TestClient(app) as client:
                # Complete setup first
                setup_resp = client.post(
                    "/api/auth/setup",
                    json={
                        "username": "admin",
                        "password": "a_very_strong_password_15",
                        "bootstrap_token": "tok",
                    },
                )
                assert setup_resp.status_code == 201

                # External login should fail with a different error
                # (not SETUP_REQUIRED)
                login_resp = client.post(
                    "/api/auth/login/plex",
                    json={"credentials": {"auth_token": "fake-token"}},
                )
                # May be 401 for other reasons, but NOT SETUP_REQUIRED
                data: dict[str, object] = login_resp.json()  # pyright: ignore[reportAny]
                assert data.get("error_code") != "SETUP_REQUIRED"
        finally:
            await engine.dispose()
