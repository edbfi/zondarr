"""Litestar application factory for Zondarr.

Provides:
- create_app(): Factory function for creating Litestar application instances
- app: Default application instance, served by ``litestar run`` (Granian)

The application factory pattern enables:
- Dependency injection override for testing
- Configuration customization per environment
- Clean separation of concerns

Usage:
    # Production and development (Granian, through GranianPlugin)
    litestar --app zondarr.app:app run

    # Testing
    from zondarr.app import create_app
    app = create_app(settings=test_settings)
"""

import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast
from urllib.parse import quote

import structlog
from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.di import Provide
from litestar.exceptions import HTTPException as LitestarHTTPException
from litestar.middleware import DefineMiddleware
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import ScalarRenderPlugin, SwaggerRenderPlugin
from litestar.openapi.spec import Components, SecurityScheme, Tag
from litestar.plugins.structlog import StructlogConfig, StructlogPlugin
from litestar.types import ControllerRouterHandler
from litestar_granian import GranianPlugin
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from structlog.types import Processor

from zondarr.api.auth import AuthController
from zondarr.api.dashboard import DashboardController
from zondarr.api.errors import (
    authentication_error_handler,
    external_service_error_handler,
    internal_error_handler,
    litestar_http_exception_handler,
    media_server_unreachable_error_handler,
    not_found_handler,
    redemption_error_handler,
    validation_error_handler,
)
from zondarr.api.health import HealthController
from zondarr.api.invitations import InvitationController
from zondarr.api.join import JoinController
from zondarr.api.logs import LogController
from zondarr.api.oauth import OAuthController
from zondarr.api.providers import ProviderController
from zondarr.api.servers import ServerController
from zondarr.api.settings import SettingsController
from zondarr.api.totp import TOTPController
from zondarr.api.users import UserController
from zondarr.api.wizards import WizardController, list_languages
from zondarr.config import Settings, load_settings
from zondarr.core.auth import DevSkipAuthMiddleware, create_jwt_auth
from zondarr.core.csrf import CSRFMiddleware
from zondarr.core.database import db_lifespan, provide_db_session
from zondarr.core.exceptions import (
    AuthenticationError,
    ExternalServiceError,
    MediaServerUnreachableError,
    NotFoundError,
    RedemptionError,
    ValidationError,
)
from zondarr.core.log_buffer import (
    capture_log_processor,
    log_buffer,
    normalize_content_type_processor,
)
from zondarr.core.tasks import background_tasks_lifespan
from zondarr.media.providers import register_all_providers
from zondarr.media.registry import registry
from zondarr.repositories.admin import AdminAccountRepository


def provide_settings(state: State) -> Settings:
    """Extract Settings from app state for DI injection."""
    return state.settings  # pyright: ignore[reportAny]


def _create_openapi_config() -> OpenAPIConfig:
    """Create OpenAPI configuration for the application.

    Generates tags dynamically from registered providers.

    Returns:
        Configured OpenAPIConfig instance.
    """
    # Base tags
    tags = [
        Tag(name="Authentication", description="Admin authentication"),
        Tag(name="Dashboard", description="Dashboard statistics"),
        Tag(name="Health", description="Health check endpoints"),
        Tag(name="Media Servers", description="Media server management"),
        Tag(name="Invitations", description="Invitation management"),
        Tag(name="Join", description="Public invitation redemption"),
        Tag(name="OAuth", description="OAuth authentication flows"),
        Tag(name="Providers", description="Provider metadata"),
        Tag(name="Settings", description="Application settings"),
        Tag(name="Users", description="User and identity management"),
        Tag(name="Wizards", description="Wizard management for onboarding flows"),
    ]

    return OpenAPIConfig(
        title="Zondarr API",
        version="0.1.0",
        description="Unified invitation and user management for media servers",
        path="/docs",
        tags=tags,
        security=[{"BearerToken": []}],
        components=Components(
            security_schemes={
                "BearerToken": SecurityScheme(
                    type="http",
                    scheme="bearer",
                    bearer_format="JWT",
                    description="JWT authentication token",
                ),
            },
        ),
        render_plugins=[
            SwaggerRenderPlugin(path="/swagger"),
            ScalarRenderPlugin(path="/scalar"),
        ],
    )


def _create_structlog_config() -> StructlogConfig:
    """Create structlog configuration for structured logging.

    Inserts ``capture_log_processor`` before the final renderer so that
    enriched event dicts (with timestamp, level, contextvars) are captured
    into the in-memory log buffer for SSE streaming. A small normaliser
    runs first to flatten Litestar's tuple-shaped ``content_type`` to a
    plain mimetype string.

    Configures ``middleware_logging_config`` to:
    - Exclude the SSE log stream endpoint (prevents feedback loop)
    - Slim down logged fields (no body/headers/cookies)

    Returns:
        Configured StructlogConfig instance.
    """
    from litestar.logging.config import StructLoggingConfig as _StructLoggingConfig
    from litestar.middleware.logging import LoggingMiddlewareConfig

    base = _StructLoggingConfig()
    processors: list[Processor] = list(base.processors) if base.processors else []

    # Insert content_type normaliser, then capture processor, before the
    # final renderer so the buffer sees the cleaned value.
    if len(processors) >= 1:
        processors.insert(-1, normalize_content_type_processor)
        processors.insert(-1, capture_log_processor)
    else:
        processors.append(normalize_content_type_processor)
        processors.append(capture_log_processor)

    return StructlogConfig(
        structlog_logging_config=_StructLoggingConfig(
            processors=processors,
            # Prevent Litestar's ExceptionHandlerMiddleware from logging
            # domain exceptions at ERROR level before our custom handlers run.
            # Our handlers already log at the appropriate level (info/warning).
            disable_stack_trace={NotFoundError},
        ),
        middleware_logging_config=LoggingMiddlewareConfig(
            exclude=["/api/v1/logs/stream"],
            request_log_fields=(
                "method",
                "path",
                "content_type",
                "query",
                "path_params",
            ),
            response_log_fields=("status_code",),
        ),
    )


def _create_cors_config(settings: Settings) -> CORSConfig | None:
    """Create CORS configuration if origins are specified.

    Returns:
        CORSConfig if cors_origins is non-empty, None otherwise.
    """
    if not settings.cors_origins:
        return None
    return CORSConfig(
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=True,
        max_age=3600,
    )


@asynccontextmanager
async def _log_stream_lifespan(_app: Litestar):
    """Bind the log buffer to the running event loop on startup."""
    log_buffer.bind_loop(asyncio.get_running_loop())
    try:
        yield
    finally:
        log_buffer.unbind_loop()


def _resolve_token_file_path(settings: Settings) -> Path:
    """Resolve the file path for writing the bootstrap token.

    Priority:
    1. BOOTSTRAP_TOKEN_FILE env var (explicit path)
    2. Derive from DATABASE_URL — if SQLite, write next to the DB file
    3. Fallback: ./.bootstrap_token in CWD
    """
    if settings.bootstrap_token_file:
        return Path(settings.bootstrap_token_file)

    db_url = settings.database_url
    if "sqlite" in db_url:
        # Extract path from sqlite URL like "sqlite+aiosqlite:///./data/zondarr.db"
        db_path_str = db_url.split("///", 1)[-1] if "///" in db_url else ""
        if db_path_str:
            return Path(db_path_str).parent / ".bootstrap_token"

    return Path(".bootstrap_token")


@asynccontextmanager
async def _bootstrap_token_lifespan(app: Litestar):
    """Auto-generate a bootstrap token on startup if needed, and write it to file.

    When no BOOTSTRAP_TOKEN env var is set and no admin account exists,
    generates a one-time token and logs it for the operator to use during
    initial setup. The token is written to a file so the frontend SSR can
    read it directly from disk.
    """
    settings = cast(Settings, app.state.settings)
    bootstrap_logger: structlog.stdlib.BoundLogger = structlog.get_logger(  # pyright: ignore[reportAny]
        "zondarr.bootstrap"
    )
    token: str | None = settings.bootstrap_token

    # Check admin count — needed for both auto-generation and URL display
    session_factory: async_sessionmaker[AsyncSession] = (  # pyright: ignore[reportAny]
        app.state.session_factory
    )
    async with session_factory() as session:
        repo = AdminAccountRepository(session)
        admin_count = await repo.count()

    # Auto-generate token when none configured and no admin exists
    if token is None and admin_count == 0:
        token = secrets.token_urlsafe(32)
        app.state.generated_bootstrap_token = token
        bootstrap_logger.info(
            "bootstrap_token_generated",
            message=(
                "No BOOTSTRAP_TOKEN set and no admin exists. "
                "Use this token for initial setup."
            ),
        )

    # Write token to file for frontend SSR to read
    if token is not None:
        token_path = _resolve_token_file_path(settings)
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(
                str(token_path),
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            )
            try:
                os.fchmod(fd, 0o600)
                _ = os.write(fd, token.encode())
            finally:
                os.close(fd)
            bootstrap_logger.info(
                "bootstrap_token_written",
                path=str(token_path),
            )
        except OSError:
            bootstrap_logger.warning(
                "bootstrap_token_write_failed",
                path=str(token_path),
                message="Could not write bootstrap token file.",
            )

    # Print setup URL when setup is still needed (regardless of token source)
    if token is not None and admin_count == 0:
        setup_url = f"/setup?token={quote(token, safe='')}"
        bootstrap_logger.info(
            "setup_url_available",
            setup_url=setup_url,
        )
        print(
            f"\n{'=' * 60}"
            + f"\n  BOOTSTRAP TOKEN: {token}"
            + f"\n  SETUP URL:       {setup_url}"
            + f"\n{'=' * 60}\n"
        )

    yield


def create_app(settings: Settings | None = None) -> Litestar:
    """Application factory for creating Litestar app instances.

    Creates a fully configured Litestar application with:
    - Database connection pool management via lifespan
    - Dependency injection for database sessions
    - Media client registry initialization
    - OpenAPI documentation with Swagger and Scalar
    - Structured logging with structlog
    - Exception handlers for domain errors

    Args:
        settings: Optional Settings instance. If not provided, settings
            are loaded from environment variables via load_settings().

    Returns:
        Configured Litestar application instance.

    Example:
        # Production usage (settings from environment)
        app = create_app()

        # Testing with custom settings
        test_settings = Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            secret_key="test-secret-key-at-least-32-chars",
        )
        app = create_app(settings=test_settings)
    """
    # Register all providers before loading settings
    # (settings loading reads env vars from provider metadata)
    register_all_providers()

    if settings is None:
        settings = load_settings()

    registry.set_settings(settings)

    # Collect route handlers dynamically from providers
    route_handlers: list[ControllerRouterHandler] = [
        AuthController,
        DashboardController,
        HealthController,
        InvitationController,
        JoinController,
        LogController,
        OAuthController,
        ProviderController,
        ServerController,
        SettingsController,
        TOTPController,
        UserController,
        WizardController,
        list_languages,
    ]

    for desc in registry.get_all_descriptors():
        if desc.route_handlers:
            route_handlers.extend(desc.route_handlers)

    # Auth: skip-auth dev middleware or JWT cookie auth
    app_logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]
    if settings.skip_auth:
        app_logger.warning("Authentication disabled — DEV_SKIP_AUTH is active")
        on_app_init = []
        middleware = [
            DefineMiddleware(CSRFMiddleware),
            DefineMiddleware(DevSkipAuthMiddleware),
        ]
    else:
        jwt_auth = create_jwt_auth(settings)
        on_app_init = [jwt_auth.on_app_init]
        middleware = [DefineMiddleware(CSRFMiddleware)]

    return Litestar(
        route_handlers=route_handlers,
        lifespan=[
            db_lifespan,
            _bootstrap_token_lifespan,
            _log_stream_lifespan,
            background_tasks_lifespan,
        ],
        state=State({"settings": settings}),
        dependencies={
            "session": Provide(provide_db_session),
            "settings": Provide(provide_settings, sync_to_thread=False),
        },
        on_app_init=on_app_init,
        middleware=middleware,
        cors_config=_create_cors_config(settings),
        openapi_config=_create_openapi_config(),
        plugins=[
            StructlogPlugin(config=_create_structlog_config()),
            GranianPlugin(),
        ],
        exception_handlers={
            AuthenticationError: authentication_error_handler,
            RedemptionError: redemption_error_handler,
            ValidationError: validation_error_handler,
            NotFoundError: not_found_handler,
            ExternalServiceError: external_service_error_handler,
            MediaServerUnreachableError: media_server_unreachable_error_handler,
            LitestarHTTPException: litestar_http_exception_handler,
            Exception: internal_error_handler,
        },
        debug=settings.debug,
    )


# Default application instance, served by ``litestar run`` (GranianPlugin)
# Usage: litestar --app zondarr.app:app run
app = create_app()
