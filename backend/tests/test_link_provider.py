"""Tests for provider linking and NO_LINKED_ACCOUNT rejection.

Tests:
- Plex auth rejects unlinked account (NO_LINKED_ACCOUNT)
- Jellyfin auth rejects unlinked account (NO_LINKED_ACCOUNT)
- Plex auth succeeds with pre-linked account
- Jellyfin auth succeeds with pre-linked account
- Link provider succeeds for authenticated admin
- Link provider rejects duplicate external_id
- AuthService.link_external_provider unit tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import create_test_engine
from zondarr.config import Settings
from zondarr.core.exceptions import AuthenticationError
from zondarr.media.providers.jellyfin.auth import JellyfinAdminAuth
from zondarr.media.providers.plex.auth import PlexAdminAuth
from zondarr.models.admin import AdminAccount
from zondarr.repositories.admin import (
    AdminAccountRepository,
    AuthSessionRepository,
    RefreshTokenRepository,
)
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import AuthService

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


async def _create_admin(
    session: AsyncSession,
    *,
    username: str = "admin",
    auth_method: str = "local",
    external_id: str | None = None,
    email: str | None = None,
) -> AdminAccount:
    """Create an admin account directly in the DB."""
    repo = AdminAccountRepository(session)
    admin = AdminAccount(
        username=username,
        password_hash="fake_hash",
        email=email,
        auth_method=auth_method,
        external_id=external_id,
        enabled=True,
    )
    return await repo.create(admin)


def _plex_settings() -> Settings:
    """Settings with Plex configured."""
    return Settings(
        secret_key="a" * 32,
        provider_credentials={"plex": {"api_key": "configured-plex-token"}},
    )


def _jellyfin_settings() -> Settings:
    """Settings with Jellyfin configured."""
    return Settings(
        secret_key="a" * 32,
        provider_credentials={"jellyfin": {"url": "http://jellyfin:8096"}},
    )


# =============================================================================
# Plex: NO_LINKED_ACCOUNT rejection
# =============================================================================


class TestPlexNoLinkedAccount:
    """Plex auth rejects unlinked accounts with NO_LINKED_ACCOUNT."""

    @pytest.mark.asyncio
    async def test_plex_rejects_unlinked_account(self) -> None:
        """Plex authenticate raises NO_LINKED_ACCOUNT when no admin is linked."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = AdminAccountRepository(session)

                plex_auth = PlexAdminAuth()
                settings = _plex_settings()

                # Mock verify to return valid Plex identity
                with patch.object(
                    plex_auth,
                    "verify",
                    new_callable=AsyncMock,
                    return_value=("owner@plex.tv", "plexowner", "owner@plex.tv"),
                ):
                    with pytest.raises(AuthenticationError) as exc_info:
                        _ = await plex_auth.authenticate(
                            {"auth_token": "valid-token"},
                            settings=settings,
                            admin_repo=repo,
                        )
                    assert exc_info.value.error_code == "NO_LINKED_ACCOUNT"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_plex_succeeds_with_prelinked_account(self) -> None:
        """Plex authenticate succeeds when admin is pre-linked."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                # Pre-link an admin with Plex external ID
                _ = await _create_admin(
                    session,
                    username="plexadmin",
                    auth_method="plex",
                    external_id="owner@plex.tv",
                )
                await session.commit()

            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                plex_auth = PlexAdminAuth()
                settings = _plex_settings()

                with patch.object(
                    plex_auth,
                    "verify",
                    new_callable=AsyncMock,
                    return_value=("owner@plex.tv", "plexowner", "owner@plex.tv"),
                ):
                    result = await plex_auth.authenticate(
                        {"auth_token": "valid-token"},
                        settings=settings,
                        admin_repo=repo,
                    )
                    assert result.username == "plexadmin"
                    assert result.auth_method == "plex"
                    assert result.last_login_at is not None
        finally:
            await engine.dispose()


# =============================================================================
# Jellyfin: NO_LINKED_ACCOUNT rejection
# =============================================================================


class TestJellyfinNoLinkedAccount:
    """Jellyfin auth rejects unlinked accounts with NO_LINKED_ACCOUNT."""

    @pytest.mark.asyncio
    async def test_jellyfin_rejects_unlinked_account(self) -> None:
        """Jellyfin authenticate raises NO_LINKED_ACCOUNT when no admin is linked."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = AdminAccountRepository(session)

                jf_auth = JellyfinAdminAuth()
                settings = _jellyfin_settings()

                with patch.object(
                    jf_auth,
                    "verify",
                    new_callable=AsyncMock,
                    return_value=("jf-user-id-123", "jfadmin", None),
                ):
                    with pytest.raises(AuthenticationError) as exc_info:
                        _ = await jf_auth.authenticate(
                            {"username": "admin", "password": "pass"},
                            settings=settings,
                            admin_repo=repo,
                        )
                    assert exc_info.value.error_code == "NO_LINKED_ACCOUNT"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_jellyfin_succeeds_with_prelinked_account(self) -> None:
        """Jellyfin authenticate succeeds when admin is pre-linked."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                _ = await _create_admin(
                    session,
                    username="jfadmin",
                    auth_method="jellyfin",
                    external_id="jf-user-id-123",
                )
                await session.commit()

            async with session_factory() as session:
                repo = AdminAccountRepository(session)
                jf_auth = JellyfinAdminAuth()
                settings = _jellyfin_settings()

                with patch.object(
                    jf_auth,
                    "verify",
                    new_callable=AsyncMock,
                    return_value=("jf-user-id-123", "jfadmin", None),
                ):
                    result = await jf_auth.authenticate(
                        {"username": "admin", "password": "pass"},
                        settings=settings,
                        admin_repo=repo,
                    )
                    assert result.username == "jfadmin"
                    assert result.auth_method == "jellyfin"
                    assert result.last_login_at is not None
        finally:
            await engine.dispose()


# =============================================================================
# AuthService.link_external_provider
# =============================================================================


class TestLinkExternalProvider:
    """Tests for AuthService.link_external_provider."""

    @pytest.mark.asyncio
    async def test_link_provider_succeeds(self) -> None:
        """link_external_provider updates admin with external link."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            # Create a local admin first
            async with session_factory() as session:
                admin = await _create_admin(session, username="localadmin")
                await session.commit()
                admin_id = admin.id

            # Mock the registry and provider
            mock_provider = MagicMock()
            mock_provider.is_configured.return_value = True  # pyright: ignore[reportAny]
            mock_provider.verify = AsyncMock(
                return_value=(
                    "owner@plex.tv",
                    "plexowner",
                    "owner@plex.tv",
                )
            )

            async with session_factory() as session:
                service = _make_service(session)
                with patch(
                    "zondarr.services.auth.registry.get_admin_auth_provider",
                    return_value=mock_provider,
                ):
                    result = await service.link_external_provider(
                        admin_id,
                        "plex",
                        {"auth_token": "valid-token"},
                        settings=_plex_settings(),
                    )
                    await session.commit()

                    assert result.auth_method == "plex"
                    assert result.external_id == "owner@plex.tv"
                    assert result.email == "owner@plex.tv"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_link_provider_rejects_duplicate_external_id(self) -> None:
        """link_external_provider rejects when external_id is already taken."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            # Create two admins, one already linked
            async with session_factory() as session:
                _existing = await _create_admin(
                    session,
                    username="existing",
                    auth_method="plex",
                    external_id="owner@plex.tv",
                )
                new_admin = await _create_admin(session, username="newadmin")
                await session.commit()
                new_admin_id = new_admin.id

            mock_provider = MagicMock()
            mock_provider.is_configured.return_value = True  # pyright: ignore[reportAny]
            mock_provider.verify = AsyncMock(
                return_value=(
                    "owner@plex.tv",
                    "plexowner",
                    "owner@plex.tv",
                )
            )

            async with session_factory() as session:
                service = _make_service(session)
                with patch(
                    "zondarr.services.auth.registry.get_admin_auth_provider",
                    return_value=mock_provider,
                ):
                    with pytest.raises(AuthenticationError) as exc_info:
                        _ = await service.link_external_provider(
                            new_admin_id,
                            "plex",
                            {"auth_token": "valid-token"},
                            settings=_plex_settings(),
                        )
                    assert exc_info.value.error_code == "EXTERNAL_ID_TAKEN"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_link_provider_rejects_unknown_method(self) -> None:
        """link_external_provider rejects unknown auth method."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                admin = await _create_admin(session, username="admin")
                await session.commit()
                admin_id = admin.id

            async with session_factory() as session:
                service = _make_service(session)
                with patch(
                    "zondarr.services.auth.registry.get_admin_auth_provider",
                    return_value=None,
                ):
                    with pytest.raises(AuthenticationError) as exc_info:
                        _ = await service.link_external_provider(
                            admin_id,
                            "unknown_method",
                            {},
                            settings=Settings(secret_key="a" * 32),
                        )
                    assert exc_info.value.error_code == "UNKNOWN_AUTH_METHOD"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_link_provider_preserves_existing_email(self) -> None:
        """link_external_provider does not overwrite existing email."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                admin = await _create_admin(
                    session,
                    username="admin",
                    email="original@example.com",
                )
                await session.commit()
                admin_id = admin.id

            mock_provider = MagicMock()
            mock_provider.is_configured.return_value = True  # pyright: ignore[reportAny]
            mock_provider.verify = AsyncMock(
                return_value=(
                    "owner@plex.tv",
                    "plexowner",
                    "owner@plex.tv",
                )
            )

            async with session_factory() as session:
                service = _make_service(session)
                with patch(
                    "zondarr.services.auth.registry.get_admin_auth_provider",
                    return_value=mock_provider,
                ):
                    result = await service.link_external_provider(
                        admin_id,
                        "plex",
                        {"auth_token": "valid-token"},
                        settings=_plex_settings(),
                    )
                    # Email should NOT be overwritten
                    assert result.email == "original@example.com"
        finally:
            await engine.dispose()


# =============================================================================
# Plex verify() method
# =============================================================================


class TestPlexVerify:
    """Tests for PlexAdminAuth.verify() method."""

    @pytest.mark.asyncio
    async def test_verify_returns_identity_tuple(self) -> None:
        """verify() returns (external_id, display_name, email) tuple."""
        plex_auth = PlexAdminAuth()
        settings = _plex_settings()

        # Mock MyPlexAccount for both user and owner calls
        with patch(
            "zondarr.media.providers.plex.auth.asyncio.to_thread"
        ) as mock_to_thread:
            mock_account = AsyncMock()
            mock_account.email = "owner@plex.tv"
            mock_account.username = "PlexOwner"

            # Both calls (user token + owner token) return same account
            mock_to_thread.return_value = mock_account

            result = await plex_auth.verify(
                {"auth_token": "valid-token"}, settings=settings
            )

            assert result == ("owner@plex.tv", "PlexOwner", "owner@plex.tv")

    @pytest.mark.asyncio
    async def test_verify_rejects_missing_token(self) -> None:
        """verify() raises MISSING_AUTH_TOKEN when no token provided."""
        plex_auth = PlexAdminAuth()
        settings = _plex_settings()

        with pytest.raises(AuthenticationError) as exc_info:
            _ = await plex_auth.verify({}, settings=settings)
        assert exc_info.value.error_code == "MISSING_AUTH_TOKEN"

    @pytest.mark.asyncio
    async def test_verify_rejects_non_owner(self) -> None:
        """verify() raises NOT_SERVER_OWNER for non-owner accounts."""
        plex_auth = PlexAdminAuth()
        settings = _plex_settings()

        call_count = 0

        def mock_to_thread_fn(*_args: object, **_kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            mock = AsyncMock()
            if call_count == 1:
                mock.email = "user@example.com"
                mock.username = "SomeUser"
            else:
                mock.email = "owner@plex.tv"
                mock.username = "Owner"
            return mock

        with patch(
            "zondarr.media.providers.plex.auth.asyncio.to_thread",
            side_effect=mock_to_thread_fn,
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                _ = await plex_auth.verify(
                    {"auth_token": "user-token"}, settings=settings
                )
            assert exc_info.value.error_code == "NOT_SERVER_OWNER"


# =============================================================================
# Jellyfin verify() method
# =============================================================================


class TestJellyfinVerify:
    """Tests for JellyfinAdminAuth.verify() method."""

    @pytest.mark.asyncio
    async def test_verify_returns_identity_tuple(self) -> None:
        """verify() returns (external_id, display_name, None) tuple."""
        jf_auth = JellyfinAdminAuth()
        settings = _jellyfin_settings()

        # httpx response.json() is sync, so use MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {  # pyright: ignore[reportAny]
            "User": {
                "Id": "jf-user-123",
                "Policy": {"IsAdministrator": True},
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response  # pyright: ignore[reportAny]
            mock_client_cls.return_value = mock_client

            result = await jf_auth.verify(
                {"username": "admin", "password": "pass"}, settings=settings
            )

            assert result == ("jf-user-123", "admin", None)

    @pytest.mark.asyncio
    async def test_verify_rejects_non_admin(self) -> None:
        """verify() raises NOT_ADMIN for non-admin Jellyfin users."""
        jf_auth = JellyfinAdminAuth()
        settings = _jellyfin_settings()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {  # pyright: ignore[reportAny]
            "User": {
                "Id": "jf-user-456",
                "Policy": {"IsAdministrator": False},
            },
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response  # pyright: ignore[reportAny]
            mock_client_cls.return_value = mock_client

            with pytest.raises(AuthenticationError) as exc_info:
                _ = await jf_auth.verify(
                    {"username": "user", "password": "pass"}, settings=settings
                )
            assert exc_info.value.error_code == "NOT_ADMIN"

    @pytest.mark.asyncio
    async def test_verify_rejects_missing_credentials(self) -> None:
        """verify() raises MISSING_CREDENTIALS when username/password missing."""
        jf_auth = JellyfinAdminAuth()
        settings = _jellyfin_settings()

        with pytest.raises(AuthenticationError) as exc_info:
            _ = await jf_auth.verify({}, settings=settings)
        assert exc_info.value.error_code == "MISSING_CREDENTIALS"
