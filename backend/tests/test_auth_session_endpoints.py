"""Auth session endpoints: login, refresh, logout and access-token checks.

Runs the AuthController behind the production JWT cookie auth and
``provide_db_session`` on a file-backed SQLite database built like
production (see ``tests/auth_db.py``).
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.security.jwt import Token
from litestar.testing import AsyncTestClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.auth_db import production_engine
from zondarr.api.auth import AuthController
from zondarr.api.errors import authentication_error_handler
from zondarr.api.session_cookies import ACCESS_COOKIE, REFRESH_COOKIE
from zondarr.config import Settings
from zondarr.core.auth import create_jwt_auth
from zondarr.core.database import provide_db_session
from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount, AuthSession
from zondarr.services.password import hash_password

SECRET_KEY = "test-secret-key-for-auth-sessions-at-least-32-chars"  # noqa: S105
PASSWORD = "correct horse battery staple"  # noqa: S105

type Factory = async_sessionmaker[AsyncSession]
type Client = AsyncTestClient[Litestar]


def _provide_settings(state: State) -> Settings:
    return state.settings  # pyright: ignore[reportAny]


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncGenerator[Factory]:
    async with production_engine("sqlite", tmp_path) as engine:
        yield async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(factory: Factory) -> AsyncGenerator[Client]:
    settings = Settings(secret_key=SECRET_KEY)
    app = Litestar(
        route_handlers=[AuthController],
        state=State({"settings": settings, "session_factory": factory}),
        dependencies={
            "session": Provide(provide_db_session),
            "settings": Provide(_provide_settings, sync_to_thread=False),
        },
        exception_handlers={AuthenticationError: authentication_error_handler},
        on_app_init=[create_jwt_auth(settings).on_app_init],
    )
    async with AsyncTestClient(app=app) as test_client:
        yield test_client


async def _create_admin(factory: Factory, username: str = "admin") -> UUID:
    async with factory() as session:
        admin = AdminAccount(
            username=username,
            password_hash=hash_password(PASSWORD),
            auth_method="local",
            enabled=True,
        )
        session.add(admin)
        await session.commit()
        return admin.id


async def _login(client: Client, username: str = "admin") -> None:
    response = await client.post(
        "/api/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


def _sid(client: Client) -> UUID:
    encoded = client.cookies.get(ACCESS_COOKIE)
    assert encoded is not None
    token = Token.decode(encoded_token=encoded, secret=SECRET_KEY, algorithm="HS256")
    sid: object = token.extras.get("sid")
    assert isinstance(sid, str)
    return UUID(sid)


async def _auth_session(factory: Factory, session_id: UUID) -> AuthSession:
    async with factory() as session:
        found = await session.get(AuthSession, session_id)
        assert found is not None
        return found


class TestLoginAndAccess:
    async def test_login_starts_a_session_named_by_the_access_token(
        self, client: Client, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        await _login(client)

        auth_session = await _auth_session(factory, _sid(client))
        assert auth_session.admin_account_id == admin_id
        assert client.cookies.get(REFRESH_COOKIE)
        me = await client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "admin"

    async def test_access_token_without_sid_is_refused(
        self, client: Client, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        legacy = Token(
            sub=str(admin_id),
            exp=datetime.now(UTC) + timedelta(minutes=15),
            iss="zondarr",
        ).encode(secret=SECRET_KEY, algorithm="HS256")
        client.cookies.set(ACCESS_COOKIE, legacy)

        assert (await client.get("/api/auth/me")).status_code == 401

    async def test_access_token_of_a_revoked_session_is_refused(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory)
        await _login(client)
        async with factory() as session:
            _ = await session.execute(
                update(AuthSession)
                .where(AuthSession.id == _sid(client))
                .values(revoked_at=datetime.now(UTC), revoked_reason="admin")
            )
            await session.commit()

        assert (await client.get("/api/auth/me")).status_code == 401

    async def test_access_token_of_an_expired_session_is_refused(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory)
        await _login(client)
        async with factory() as session:
            _ = await session.execute(
                update(AuthSession)
                .where(AuthSession.id == _sid(client))
                .values(absolute_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await session.commit()

        assert (await client.get("/api/auth/me")).status_code == 401

    async def test_sid_of_another_admin_is_refused(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory, "admin")
        other_id = await _create_admin(factory, "other")
        await _login(client, "admin")
        forged = Token(
            sub=str(other_id),
            exp=datetime.now(UTC) + timedelta(minutes=15),
            iss="zondarr",
            extras={"sid": str(_sid(client))},
        ).encode(secret=SECRET_KEY, algorithm="HS256")
        client.cookies.set(ACCESS_COOKIE, forged)

        assert (await client.get("/api/auth/me")).status_code == 401


class TestRefreshAndLogout:
    async def test_refresh_rotates_within_the_session(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory)
        await _login(client)
        session_id = _sid(client)
        old_refresh = client.cookies.get(REFRESH_COOKIE)

        response = await client.post("/api/auth/refresh")

        assert response.status_code == 200
        assert _sid(client) == session_id
        assert client.cookies.get(REFRESH_COOKIE) != old_refresh
        assert (await _auth_session(factory, session_id)).current_generation == 1
        assert (await client.get("/api/auth/me")).status_code == 200

    async def test_refresh_refuses_a_disabled_admin(
        self, client: Client, factory: Factory
    ) -> None:
        admin_id = await _create_admin(factory)
        await _login(client)
        async with factory() as session:
            _ = await session.execute(
                update(AdminAccount)
                .where(AdminAccount.id == admin_id)
                .values(enabled=False)
            )
            await session.commit()

        response = await client.post("/api/auth/refresh")

        assert response.status_code == 401
        assert response.json()["error_code"] == "ACCOUNT_DISABLED"
        # The refused rotation was rolled back.
        assert (await _auth_session(factory, _sid(client))).current_generation == 0

    async def test_logout_ends_the_session_and_its_access_token(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory)
        await _login(client)
        session_id = _sid(client)
        access = client.cookies.get(ACCESS_COOKIE)
        refresh = client.cookies.get(REFRESH_COOKIE)
        assert access is not None
        assert refresh is not None

        response = await client.post("/api/auth/logout")

        assert response.status_code == 200
        ended = await _auth_session(factory, session_id)
        assert ended.revoked_reason == "logout"
        # The old cookies no longer work.
        client.cookies.set(ACCESS_COOKIE, access)
        assert (await client.get("/api/auth/me")).status_code == 401
        client.cookies.set(REFRESH_COOKIE, refresh)
        replay = await client.post("/api/auth/refresh")
        assert replay.status_code == 401
        assert replay.json()["error_code"] == "TOKEN_REVOKED"

    async def test_logout_without_refresh_cookie_uses_the_access_token(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory)
        await _login(client)
        session_id = _sid(client)
        client.cookies.delete(REFRESH_COOKIE)

        assert (await client.post("/api/auth/logout")).status_code == 200

        assert (await _auth_session(factory, session_id)).revoked_reason == "logout"

    async def test_logout_leaves_other_sessions_alone(
        self, client: Client, factory: Factory
    ) -> None:
        _ = await _create_admin(factory)
        await _login(client)
        first = _sid(client)
        first_cookies = dict(client.cookies)
        client.cookies.clear()
        await _login(client)
        second = _sid(client)

        assert (await client.post("/api/auth/logout")).status_code == 200

        assert (await _auth_session(factory, second)).revoked_at is not None
        assert (await _auth_session(factory, first)).revoked_at is None
        client.cookies.clear()
        for name, value in first_cookies.items():
            client.cookies.set(name, value)
        assert (await client.get("/api/auth/me")).status_code == 200
