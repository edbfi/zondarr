"""Property-based tests for service layer.

Feature: zondarr-foundation
Properties: 10, 11
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.conftest import KNOWN_SERVER_TYPES, TestDB, create_test_engine
from zondarr.core.exceptions import NotFoundError, ValidationError
from zondarr.media.registry import ClientRegistry
from zondarr.media.types import ServerInfo
from zondarr.models import Invitation
from zondarr.repositories.invitation import InvitationRepository
from zondarr.repositories.media_server import MediaServerRepository
from zondarr.services.invitation import (
    InvitationService,
    InvitationValidationFailure,
)
from zondarr.services.media_server import MediaServerService

# Custom strategies for model fields
name_strategy = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda x: x.strip())
url_strategy = st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,}", fullmatch=True)
server_type_strategy = st.sampled_from(KNOWN_SERVER_TYPES)
# Use UUIDs for codes to ensure uniqueness across Hypothesis examples
code_strategy = st.uuids().map(lambda u: str(u).replace("-", "")[:12].upper())


@pytest.fixture(autouse=True)
def _bypass_url_validation() -> Iterator[None]:
    """Patch validate_url_host as a no-op for property tests.

    Property tests use Hypothesis-generated URLs with mock clients,
    so real DNS resolution would fail.
    """
    with patch(
        "zondarr.services.media_server.validate_url_host",
        new_callable=AsyncMock,
    ):
        yield


class TestServiceValidatesBeforePersisting:
    """Property 10: Service Validates Before Persisting."""

    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_add_server_fails_when_connection_test_fails(
        self,
        db: TestDB,
        name: str,
        server_type: str,
        url: str,
        api_key: str,
    ) -> None:
        """MediaServerService.add raises ValidationError when connection test fails."""
        await db.clean()
        async with db.session_factory() as session:
            repo = MediaServerRepository(session)

            mock_registry = MagicMock(spec=ClientRegistry)
            mock_registry.registered_types = MagicMock(
                return_value=frozenset({"plex", "jellyfin"})
            )
            mock_client = AsyncMock()
            mock_client.test_connection = AsyncMock(return_value=False)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_registry.create_client = MagicMock(return_value=mock_client)

            service = MediaServerService(repo, registry=mock_registry)

            with pytest.raises(ValidationError) as exc_info:
                _ = await service.add(
                    name=name,
                    server_type=server_type,
                    url=url,
                    api_key=api_key,
                )

            assert exc_info.value.error_code == "VALIDATION_ERROR"
            assert "url" in exc_info.value.field_errors
            assert "api_key" in exc_info.value.field_errors

            all_servers = await repo.get_all()
            assert len(all_servers) == 0

    @given(
        name=name_strategy,
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_add_server_succeeds_when_connection_test_passes(
        self,
        db: TestDB,
        name: str,
        server_type: str,
        url: str,
        api_key: str,
    ) -> None:
        """MediaServerService.add persists server when connection test passes."""
        await db.clean()
        async with db.session_factory() as session:
            repo = MediaServerRepository(session)

            mock_registry = MagicMock(spec=ClientRegistry)
            mock_registry.registered_types = MagicMock(
                return_value=frozenset({"plex", "jellyfin"})
            )
            mock_client = AsyncMock()
            mock_client.test_connection = AsyncMock(return_value=True)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_registry.create_client = MagicMock(return_value=mock_client)

            service = MediaServerService(repo, registry=mock_registry)

            created = await service.add(
                name=name,
                server_type=server_type,
                url=url,
                api_key=api_key,
            )
            await session.commit()

            assert created.id is not None
            assert created.name == name
            assert created.server_type == server_type

            retrieved = await repo.get_by_id(created.id)
            assert retrieved is not None
            assert retrieved.name == name


class TestDetectAndTestBehavior:
    """Tests for MediaServerService.detect_and_test (explicit type, auto-detect, timeouts, metadata)."""

    def _make_mock_registry(
        self,
        *,
        test_result: bool = True,
        info: ServerInfo | None = None,
        info_raises: bool = False,
    ) -> tuple[MagicMock, AsyncMock]:
        """Build a mock registry + client with configurable behavior."""
        mock_registry = MagicMock(spec=ClientRegistry)
        mock_registry.registered_types = MagicMock(
            return_value=frozenset({"plex", "jellyfin"})
        )

        mock_client = AsyncMock()
        mock_client.test_connection = AsyncMock(return_value=test_result)

        if info_raises:
            mock_client.get_server_info = AsyncMock(
                side_effect=RuntimeError("metadata failed")
            )
        else:
            mock_client.get_server_info = AsyncMock(return_value=info)

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_registry.create_client = MagicMock(return_value=mock_client)
        return mock_registry, mock_client

    def _make_service(self, mock_registry: MagicMock) -> MediaServerService:
        """Create a MediaServerService with a mock repository (unused by detect_and_test)."""
        mock_repo = MagicMock(spec=MediaServerRepository)
        return MediaServerService(mock_repo, registry=mock_registry)

    @given(
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_explicit_type_success(
        self, server_type: str, url: str, api_key: str
    ) -> None:
        """detect_and_test with explicit server_type returns success + info."""
        info = ServerInfo(server_name="TestServer", version="1.0")
        mock_registry, _ = self._make_mock_registry(test_result=True, info=info)
        service = self._make_service(mock_registry)

        success, detected, server_info = await service.detect_and_test(
            url=url, api_key=api_key, server_type=server_type
        )
        assert success is True
        assert detected == server_type
        assert server_info is not None
        assert server_info.server_name == "TestServer"

    @given(
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_explicit_type_connection_failure(
        self, server_type: str, url: str, api_key: str
    ) -> None:
        """detect_and_test with explicit server_type returns failure when test_connection fails."""
        mock_registry, _ = self._make_mock_registry(test_result=False)
        service = self._make_service(mock_registry)

        success, detected, server_info = await service.detect_and_test(
            url=url, api_key=api_key, server_type=server_type
        )
        assert success is False
        assert detected == server_type
        assert server_info is None

    @given(url=url_strategy, api_key=name_strategy)
    @pytest.mark.asyncio
    async def test_auto_detect_returns_first_success(
        self, url: str, api_key: str
    ) -> None:
        """detect_and_test without server_type tries all types and returns the first success."""
        info = ServerInfo(server_name="Detected", version="2.0")
        mock_registry, _ = self._make_mock_registry(test_result=True, info=info)
        service = self._make_service(mock_registry)

        success, detected, server_info = await service.detect_and_test(
            url=url, api_key=api_key
        )
        assert success is True
        assert detected in {"plex", "jellyfin"}
        assert server_info is not None

    @given(url=url_strategy, api_key=name_strategy)
    @pytest.mark.asyncio
    async def test_auto_detect_all_fail(self, url: str, api_key: str) -> None:
        """detect_and_test without server_type returns failure when all types fail."""
        mock_registry, _ = self._make_mock_registry(test_result=False)
        service = self._make_service(mock_registry)

        success, detected, server_info = await service.detect_and_test(
            url=url, api_key=api_key
        )
        assert success is False
        assert detected is None
        assert server_info is None

    @given(
        server_type=server_type_strategy,
        url=url_strategy,
        api_key=name_strategy,
    )
    @pytest.mark.asyncio
    async def test_metadata_failure_is_best_effort(
        self, server_type: str, url: str, api_key: str
    ) -> None:
        """detect_and_test still succeeds when get_server_info() raises."""
        mock_registry, _ = self._make_mock_registry(test_result=True, info_raises=True)
        service = self._make_service(mock_registry)

        success, detected, server_info = await service.detect_and_test(
            url=url, api_key=api_key, server_type=server_type
        )
        assert success is True
        assert detected == server_type
        assert server_info is None


class TestInvitationValidationChecksAllConditions:
    """Property 11: Invitation Validation Checks All Conditions."""

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_fails_for_disabled_invitation(
        self, db: TestDB, code: str
    ) -> None:
        """InvitationService.redeem fails with DISABLED for disabled invitations."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            service = InvitationService(repo)

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = False
            invitation.expires_at = None
            invitation.max_uses = None
            invitation.use_count = 0
            _ = await repo.create(invitation)
            await session.commit()

            with pytest.raises(ValidationError) as exc_info:
                _ = await service.redeem(code)

            assert "disabled" in exc_info.value.message.lower()
            assert "code" in exc_info.value.field_errors

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_fails_for_expired_invitation(
        self, db: TestDB, code: str
    ) -> None:
        """InvitationService.redeem fails with EXPIRED for expired invitations."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            service = InvitationService(repo)

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = True
            invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
            invitation.max_uses = None
            invitation.use_count = 0
            _ = await repo.create(invitation)
            await session.commit()

            with pytest.raises(ValidationError) as exc_info:
                _ = await service.redeem(code)

            assert "expired" in exc_info.value.message.lower()
            assert "code" in exc_info.value.field_errors

    @given(
        code=code_strategy,
        max_uses=st.integers(min_value=1, max_value=100),
    )
    @pytest.mark.asyncio
    async def test_redeem_fails_for_exhausted_invitation(
        self, db: TestDB, code: str, max_uses: int
    ) -> None:
        """InvitationService.redeem fails with MAX_USES_REACHED for exhausted invitations."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            service = InvitationService(repo)

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = True
            invitation.expires_at = None
            invitation.max_uses = max_uses
            invitation.use_count = max_uses
            _ = await repo.create(invitation)
            await session.commit()

            with pytest.raises(ValidationError) as exc_info:
                _ = await service.redeem(code)

            assert "max" in exc_info.value.message.lower()
            assert "code" in exc_info.value.field_errors

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_fails_for_nonexistent_invitation(
        self, db: TestDB, code: str
    ) -> None:
        """InvitationService.redeem fails with NOT_FOUND for nonexistent invitations."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            service = InvitationService(repo)

            with pytest.raises(NotFoundError) as exc_info:
                _ = await service.redeem(code)

            assert exc_info.value.error_code == "NOT_FOUND"
            assert exc_info.value.context["resource_type"] == "Invitation"

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_redeem_succeeds_for_valid_invitation(
        self, db: TestDB, code: str
    ) -> None:
        """InvitationService.redeem succeeds and increments use_count for valid invitations."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            service = InvitationService(repo)

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = True
            invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
            invitation.max_uses = 10
            invitation.use_count = 0
            _ = await repo.create(invitation)
            await session.commit()

            redeemed = await service.redeem(code)
            await session.commit()

            assert redeemed.use_count == 1
            assert redeemed.code == code

            retrieved = await repo.get_by_code(code)
            assert retrieved is not None
            assert retrieved.use_count == 1

    @given(code=code_strategy)
    @pytest.mark.asyncio
    async def test_validate_returns_correct_failure_reason(
        self, db: TestDB, code: str
    ) -> None:
        """InvitationService.validate returns specific failure reasons."""
        await db.clean()
        async with db.session_factory() as session:
            repo = InvitationRepository(session)
            service = InvitationService(repo)

            is_valid, reason = await service.validate(code)
            assert is_valid is False
            assert reason == InvitationValidationFailure.NOT_FOUND

            invitation = Invitation()
            invitation.code = code
            invitation.enabled = False
            invitation.expires_at = None
            invitation.max_uses = None
            invitation.use_count = 0
            _ = await repo.create(invitation)
            await session.commit()

            is_valid, reason = await service.validate(code)
            assert is_valid is False
            assert reason == InvitationValidationFailure.DISABLED


class TestGeneratedCodesAreValid:
    """Property 8: Generated Codes Are Valid."""

    @pytest.mark.asyncio
    async def test_generated_code_has_correct_length(self) -> None:
        """Generated invitation codes are exactly 12 characters long."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = await service.create()
                await session.commit()

                assert len(invitation.code) == 12
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_generated_code_contains_only_valid_characters(self) -> None:
        """Generated codes contain only uppercase letters and digits."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = await service.create()
                await session.commit()

                for char in invitation.code:
                    assert char.isupper() or char.isdigit()
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_generated_code_excludes_ambiguous_characters(self) -> None:
        """Generated codes exclude ambiguous characters (0, O, I, L)."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                invitation = await service.create()
                await session.commit()

                ambiguous_chars = {"0", "O", "I", "L"}
                for char in invitation.code:
                    assert char not in ambiguous_chars
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_generated_codes_are_unique(self) -> None:
        """Multiple generated codes are unique."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                codes: set[str] = set()
                num_invitations = 5

                for _ in range(num_invitations):
                    invitation = await service.create()
                    codes.add(invitation.code)
                    await session.commit()

                assert len(codes) == num_invitations
        finally:
            await engine.dispose()


class TestDuplicateCodeReturnsValidationError:
    """Creating an invitation with a duplicate code returns a ValidationError."""

    @pytest.mark.asyncio
    async def test_duplicate_code_raises_validation_error(self) -> None:
        """InvitationService.create raises ValidationError for duplicate codes."""
        engine = await create_test_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                repo = InvitationRepository(session)
                service = InvitationService(repo)

                _ = await service.create(code="DUPECODE1234")
                await session.commit()

                with pytest.raises(ValidationError) as exc_info:
                    _ = await service.create(code="DUPECODE1234")

                assert "already exists" in exc_info.value.message
                assert "code" in exc_info.value.field_errors
        finally:
            await engine.dispose()
