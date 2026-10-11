"""Session cookies: the access token, the refresh token and their settings.

Every endpoint that signs an admin in (setup, local and external login, TOTP
and backup-code completion) and the refresh endpoint issue their cookies
through this module, so the access token always names its auth session
(``sid``) and both cookies share one set of attributes.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from litestar import Request
from litestar.datastructures import Cookie, State
from litestar.security.jwt import Token
from sqlalchemy.ext.asyncio import AsyncSession

from zondarr.config import Settings
from zondarr.core.auth import session_id_claim
from zondarr.models.admin import AdminAccount
from zondarr.repositories.app_setting import AppSettingRepository
from zondarr.services.auth import REFRESH_TOKEN_EXPIRY_DAYS, AuthService
from zondarr.services.settings import SettingsService

ACCESS_COOKIE = "zondarr_access_token"
REFRESH_COOKIE = "zondarr_refresh_token"

# Access token lifetime
ACCESS_TOKEN_MINUTES = 15


async def resolve_secure_cookies(session: AsyncSession, settings: Settings) -> bool:
    """Resolve the effective secure_cookies value.

    If the SECURE_COOKIES env var is set, use the Settings value (which came
    from the env var). Otherwise, check the database.
    """
    if os.environ.get("SECURE_COOKIES") is not None:
        return settings.secure_cookies
    service = SettingsService(AppSettingRepository(session))
    value, _ = await service.get_secure_cookies()
    return value


def create_access_token(admin_id: UUID, session_id: UUID, secret_key: str) -> str:
    """Encode a JWT access token for one auth session."""
    token = Token(
        sub=str(admin_id),
        exp=datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        iss="zondarr",
        extras={"sid": str(session_id)},
    )
    return token.encode(secret=secret_key, algorithm="HS256")


def session_id_from_access_token(encoded: str | None, secret_key: str) -> UUID | None:
    """Return the ``sid`` of a validly signed access token, expired or not.

    Used by logout when the refresh cookie is missing: ending the session the
    token names only takes access away, so an expired token still counts.
    """
    if not encoded:
        return None
    try:
        token = Token.decode(
            encoded_token=encoded,
            secret=secret_key,
            algorithm="HS256",
            verify_exp=False,
        )
    except Exception:
        return None
    return session_id_claim(token)


def session_cookies(
    *,
    admin_id: UUID,
    session_id: UUID,
    raw_refresh: str,
    secret_key: str,
    secure: bool,
) -> list[Cookie]:
    """The access and refresh cookies for one auth session."""
    access = Cookie(
        key=ACCESS_COOKIE,
        value=create_access_token(admin_id, session_id, secret_key),
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=ACCESS_TOKEN_MINUTES * 60,
        path="/",
    )
    refresh = Cookie(
        key=REFRESH_COOKIE,
        value=raw_refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRY_DAYS * 86400,
        path="/",
    )
    return [access, refresh]


def cleared_session_cookies(*, secure: bool) -> list[Cookie]:
    """Cookies that delete both session cookies."""
    return [
        Cookie(
            key=key,
            value="",
            httponly=True,
            secure=secure,
            samesite="lax",
            max_age=0,
            path="/",
        )
        for key in (ACCESS_COOKIE, REFRESH_COOKIE)
    ]


async def start_session_cookies(
    service: AuthService,
    admin: AdminAccount,
    *,
    request: Request[None, None, State],
    session: AsyncSession,
    settings: Settings,
) -> list[Cookie]:
    """Start an auth session for a completed sign-in and return its cookies."""
    client = request.client
    session_id, raw_refresh = await service.start_session(
        admin,
        user_agent=request.headers.get("user-agent"),
        ip=client.host if client is not None else None,
    )
    secure = await resolve_secure_cookies(session, settings)
    return session_cookies(
        admin_id=admin.id,
        session_id=session_id,
        raw_refresh=raw_refresh,
        secret_key=settings.secret_key,
        secure=secure,
    )
