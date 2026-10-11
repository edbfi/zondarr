"""TOTP two-factor authentication API controller.

Provides endpoints for TOTP verification during login:
- POST /api/auth/totp/verify — Verify TOTP code with challenge token
- POST /api/auth/totp/backup-code — Verify backup code with challenge token

Provides authenticated endpoints for TOTP management:
- POST /api/auth/totp/setup — Initiate TOTP setup
- POST /api/auth/totp/confirm-setup — Confirm TOTP setup with code
- POST /api/auth/totp/disable — Disable TOTP (requires password)
- POST /api/auth/totp/regenerate-backup-codes — Regenerate backup codes
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from litestar import Controller, Request, Response, post
from litestar.datastructures import State
from litestar.security.jwt import Token
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.auth import AdminUser
from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount
from zondarr.repositories.admin import (
    AdminAccountRepository,
    AuthSessionRepository,
    RefreshTokenRepository,
)
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import AuthService
from zondarr.services.password import verify_password
from zondarr.services.totp import TOTPService

from .schemas import (
    AuthSuccessResponse,
    TOTPBackupCodeRequest,
    TOTPBackupCodesResponse,
    TOTPConfirmSetupRequest,
    TOTPConfirmSetupResponse,
    TOTPDisableRequest,
    TOTPRegenerateBackupCodesRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
)
from .session_cookies import start_session_cookies

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# Challenge token lifetime
CHALLENGE_TOKEN_MINUTES = 5


def create_challenge_token(admin_id: str, secret_key: str, nonce: str) -> str:
    """Create a short-lived JWT challenge token for TOTP verification.

    Args:
        admin_id: The admin account UUID as a string.
        secret_key: Application secret key for signing.
        nonce: Single-use nonce to prevent token replay.

    Returns:
        Encoded JWT string with purpose="totp_challenge" and embedded nonce.
    """
    token = Token(
        sub=admin_id,
        exp=datetime.now(UTC) + timedelta(minutes=CHALLENGE_TOKEN_MINUTES),
        iss="zondarr",
        extras={"purpose": "totp_challenge", "nonce": nonce},
    )
    return token.encode(secret=secret_key, algorithm="HS256")


def validate_challenge_token(encoded_token: str, secret_key: str) -> tuple[UUID, str]:
    """Validate a TOTP challenge token and return the admin ID and nonce.

    Args:
        encoded_token: The encoded JWT challenge token.
        secret_key: Application secret key for verification.

    Returns:
        A tuple of (admin account UUID, nonce string).

    Raises:
        AuthenticationError: If the token is invalid, expired, or not a challenge token.
    """
    try:
        token = Token.decode(
            encoded_token=encoded_token,
            secret=secret_key,
            algorithm="HS256",
        )
    except Exception:
        raise AuthenticationError(
            "Invalid challenge token", "INVALID_CHALLENGE_TOKEN"
        ) from None

    # Verify purpose claim
    if token.extras.get("purpose") != "totp_challenge":
        raise AuthenticationError(
            "Invalid challenge token purpose", "INVALID_CHALLENGE_TOKEN"
        )

    # Check expiration
    if token.exp and token.exp < datetime.now(UTC):
        raise AuthenticationError(
            "Challenge token has expired", "CHALLENGE_TOKEN_EXPIRED"
        )

    # Extract nonce
    nonce = token.extras.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        raise AuthenticationError(
            "Invalid challenge token nonce", "INVALID_CHALLENGE_TOKEN"
        )

    try:
        return UUID(token.sub), nonce
    except ValueError, TypeError:
        raise AuthenticationError(
            "Invalid challenge token subject", "INVALID_CHALLENGE_TOKEN"
        ) from None


class TOTPController(Controller):
    """Controller for TOTP verification endpoints during login."""

    path: str = "/api/auth/totp"
    tags: Sequence[str] | None = ["Authentication"]

    def _create_auth_service(self, session: AsyncSession) -> AuthService:
        return AuthService(
            admin_repo=AdminAccountRepository(session),
            session_repo=AuthSessionRepository(session),
            token_repo=RefreshTokenRepository(session),
            app_setting_repo=AppSettingRepository(session),
        )

    @post(
        "/verify",
        status_code=HTTP_200_OK,
        summary="Verify TOTP code during login",
        exclude_from_auth=True,
    )
    async def verify_totp(
        self,
        data: TOTPVerifyRequest,
        request: Request[None, None, State],
        session: AsyncSession,
        settings: Settings,
    ) -> Response[AuthSuccessResponse]:
        """Verify a TOTP code using the challenge token from login."""
        secret_key = settings.secret_key

        # Validate challenge token and extract nonce
        admin_id, nonce = validate_challenge_token(data.challenge_token, secret_key)

        # Load admin and verify code before consuming nonce.
        # This ensures a mistyped code doesn't burn the challenge token.
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(admin_id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )

        # Check rate limit
        totp_service = TOTPService(secret_key=secret_key)
        totp_service.check_rate_limit(admin)

        # Verify TOTP code
        if not totp_service.verify_code(admin, data.code):
            totp_service.record_failed_attempt(admin)
            await session.commit()
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        # Atomically consume the challenge nonce to prevent replay.
        # Only consumed after successful verification so a wrong code
        # doesn't invalidate the token and force a full re-login.
        nonce_consumed = await admin_repo.consume_challenge_nonce(admin_id, nonce)
        if not nonce_consumed:
            raise AuthenticationError(
                "Challenge token already used or invalid", "INVALID_CHALLENGE_TOKEN"
            )

        # Success — reset failed attempts and issue tokens
        totp_service.reset_failed_attempts(admin)
        admin.last_login_at = datetime.now(UTC)

        cookies = await start_session_cookies(
            self._create_auth_service(session),
            admin,
            request=request,
            session=session,
            settings=settings,
        )
        return Response(AuthSuccessResponse(), status_code=HTTP_200_OK, cookies=cookies)

    @post(
        "/backup-code",
        status_code=HTTP_200_OK,
        summary="Verify backup code during login",
        exclude_from_auth=True,
    )
    async def verify_backup_code(
        self,
        data: TOTPBackupCodeRequest,
        request: Request[None, None, State],
        session: AsyncSession,
        settings: Settings,
    ) -> Response[AuthSuccessResponse]:
        """Verify a backup code using the challenge token from login."""
        secret_key = settings.secret_key

        # Validate challenge token and extract nonce
        admin_id, nonce = validate_challenge_token(data.challenge_token, secret_key)

        # Load admin and verify code before consuming nonce.
        # This ensures a wrong backup code doesn't burn the challenge token.
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(admin_id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )

        # Check rate limit
        totp_service = TOTPService(secret_key=secret_key)
        totp_service.check_rate_limit(admin)

        # Verify backup code
        if not totp_service.verify_backup_code(admin, data.code):
            totp_service.record_failed_attempt(admin)
            await session.commit()
            raise AuthenticationError("Invalid backup code", "INVALID_BACKUP_CODE")

        # Atomically consume the challenge nonce to prevent replay.
        # Only consumed after successful verification so a wrong code
        # doesn't invalidate the token and force a full re-login.
        nonce_consumed = await admin_repo.consume_challenge_nonce(admin_id, nonce)
        if not nonce_consumed:
            raise AuthenticationError(
                "Challenge token already used or invalid", "INVALID_CHALLENGE_TOKEN"
            )

        # Success — reset failed attempts and issue tokens
        totp_service.reset_failed_attempts(admin)
        admin.last_login_at = datetime.now(UTC)

        cookies = await start_session_cookies(
            self._create_auth_service(session),
            admin,
            request=request,
            session=session,
            settings=settings,
        )
        return Response(AuthSuccessResponse(), status_code=HTTP_200_OK, cookies=cookies)

    # =========================================================================
    # Authenticated TOTP management endpoints
    # =========================================================================

    async def _get_admin_account(
        self, request: Request[AdminUser, Token, State], session: AsyncSession
    ) -> AdminAccount:
        """Load the full AdminAccount for the authenticated user."""
        user: AdminUser = request.user
        admin_repo = AdminAccountRepository(session)
        admin = await admin_repo.get_by_id(user.id)
        if admin is None or not admin.enabled:
            raise AuthenticationError(
                "Account not found or disabled", "ACCOUNT_DISABLED"
            )
        return admin

    @post(
        "/setup",
        status_code=HTTP_200_OK,
        summary="Initiate TOTP setup",
    )
    async def setup_totp(
        self,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> TOTPSetupResponse:
        """Generate TOTP secret, provisioning URI, QR code, and backup codes."""
        admin = await self._get_admin_account(request, session)
        totp_service = TOTPService(secret_key=settings.secret_key)
        uri, qr_svg, backup_codes = totp_service.generate_setup(admin)

        return TOTPSetupResponse(
            provisioning_uri=uri,
            qr_code_svg=qr_svg,
            backup_codes=backup_codes,
        )

    @post(
        "/confirm-setup",
        status_code=HTTP_200_OK,
        summary="Confirm TOTP setup with authenticator code",
    )
    async def confirm_totp_setup(
        self,
        data: TOTPConfirmSetupRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> TOTPConfirmSetupResponse:
        """Verify a TOTP code to confirm setup and enable 2FA."""
        admin = await self._get_admin_account(request, session)
        totp_service = TOTPService(secret_key=settings.secret_key)

        if not totp_service.confirm_setup(admin, data.code):
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        # Backup codes were generated during setup and are already stored.
        # Regenerate fresh ones so the user can see the plaintext codes.
        backup_codes = totp_service.regenerate_backup_codes(admin)

        return TOTPConfirmSetupResponse(backup_codes=backup_codes)

    @post(
        "/disable",
        status_code=HTTP_200_OK,
        summary="Disable TOTP two-factor authentication",
    )
    async def disable_totp(
        self,
        data: TOTPDisableRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> dict[str, bool]:
        """Disable TOTP after verifying the admin's password."""
        admin = await self._get_admin_account(request, session)

        # Verify password
        if admin.password_hash is None or not verify_password(
            admin.password_hash, data.password
        ):
            raise AuthenticationError("Invalid password", "INVALID_PASSWORD")

        # Verify TOTP code
        totp_service = TOTPService(secret_key=settings.secret_key)
        if not totp_service.verify_code(admin, data.code):
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        totp_service.disable(admin)

        return {"success": True}

    @post(
        "/regenerate-backup-codes",
        status_code=HTTP_200_OK,
        summary="Regenerate TOTP backup codes",
    )
    async def regenerate_backup_codes(
        self,
        data: TOTPRegenerateBackupCodesRequest,
        request: Request[AdminUser, Token, State],
        session: AsyncSession,
        settings: Settings,
    ) -> TOTPBackupCodesResponse:
        """Generate new backup codes after verifying a TOTP code."""
        admin = await self._get_admin_account(request, session)
        totp_service = TOTPService(secret_key=settings.secret_key)

        # Verify the TOTP code first
        if not totp_service.verify_code(admin, data.code):
            raise AuthenticationError("Invalid TOTP code", "INVALID_TOTP_CODE")

        codes = totp_service.regenerate_backup_codes(admin)
        return TOTPBackupCodesResponse(backup_codes=codes)
