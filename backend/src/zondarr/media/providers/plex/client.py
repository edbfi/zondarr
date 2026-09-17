"""Plex media server client.

Provides the PlexClient class that implements the MediaClient protocol
for communicating with Plex media servers.

Uses python-plexapi (PlexAPI v4.18+) for server communication.
PlexAPI is synchronous, so operations use asyncio.to_thread() to avoid
blocking the event loop.

Uses Python 3.14 features:
- Deferred annotations (no forward reference quotes needed)
- Self type for proper return type in context manager
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Self, cast, final

import structlog

if TYPE_CHECKING:
    from plexapi.myplex import MyPlexAccount
    from plexapi.server import PlexServer

from zondarr.core.exceptions import ExternalServiceError
from zondarr.media.exceptions import MediaClientError
from zondarr.media.types import Capability, ExternalUser, LibraryInfo, ServerInfo

log: structlog.stdlib.BoundLogger = structlog.get_logger()  # pyright: ignore[reportAny]

# Strong references to fire-and-forget background tasks so they are
# not garbage-collected before completion.
_background_tasks: set[asyncio.Task[None]] = set()


async def _auto_accept_plex_invite(
    auth_token: str,
    admin_token: str,
    admin_username: str,
    machine_id: str,
    email: str,
    plex_user_id: str,
) -> None:
    """Background task: accept a pending Plex invite on behalf of the user.

    Creates its own MyPlexAccount from the auth_token so it is independent
    of the original PlexClient context (which may already be closed).

    After a successful accept it also cancels stale pending invites sent
    by the admin to this email for the same server.
    """

    def _accept() -> bool:
        from plexapi.myplex import MyPlexAccount

        user_account: MyPlexAccount = MyPlexAccount(token=auth_token)

        v2_base = "https://clients.plex.tv"
        v2_params: dict[str, str] = {
            "X-Plex-Token": auth_token,
            "X-Plex-Product": "Zondarr",
            "X-Plex-Version": "1.0",
            "X-Plex-Client-Identifier": str(user_account.uuid),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            "X-Plex-Platform": "Web",
            "X-Plex-Platform-Version": "1.0",
            "X-Plex-Device": "Web",
            "X-Plex-Device-Name": "Zondarr",
        }
        v2_headers: dict[str, str] = {"Accept": "application/json"}

        for attempt in range(1, 4):
            try:
                # Step 1: List pending received invites
                list_url = f"{v2_base}/api/v2/shared_servers/invites/received/pending"
                list_resp = user_account._session.get(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                    list_url,
                    params=v2_params,
                    headers=v2_headers,
                    timeout=30,
                )
                _ = list_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                invites: list[dict[str, object]] = list_resp.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                log.info(
                    "plex_auto_accept_pending_invites",
                    attempt=attempt,
                    pending_count=len(invites),  # pyright: ignore[reportUnknownArgumentType]
                )

                # Step 2: Find invite from the admin for this server
                matched_invite: dict[str, object] | None = None
                for inv in invites:  # pyright: ignore[reportUnknownVariableType]
                    owner: dict[str, object] = inv.get("owner", {}) or {}  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAssignmentType]
                    owner_values = (
                        owner.get("username", ""),
                        owner.get("email", ""),
                        owner.get("title", ""),
                        owner.get("friendlyName", ""),
                    )
                    if not (admin_username and admin_username in owner_values):
                        continue
                    inv_servers = cast(
                        list[dict[str, object]],
                        inv.get("sharedServers") or [],  # pyright: ignore[reportUnknownMemberType]
                    )
                    for srv in inv_servers:
                        if str(srv.get("machineIdentifier", "")) == machine_id:
                            matched_invite = inv  # pyright: ignore[reportUnknownVariableType]
                            break
                    if matched_invite is not None:
                        break

                if matched_invite is None:
                    log.info(
                        "plex_auto_accept_no_matching_invite",
                        attempt=attempt,
                        admin_username=admin_username,
                    )
                    if attempt < 3:
                        time.sleep(1)
                    continue

                # Step 3: Accept the invite for the matching server
                shared_servers = cast(
                    list[dict[str, object]],
                    matched_invite.get("sharedServers") or [],  # pyright: ignore[reportUnknownMemberType]
                )
                matched_server: dict[str, object] | None = None
                for srv in shared_servers:
                    if str(srv.get("machineIdentifier", "")) == machine_id:
                        matched_server = srv
                        break
                if matched_server is None:
                    log.info(
                        "plex_auto_accept_no_matching_server",
                        attempt=attempt,
                        machine_id=machine_id,
                    )
                    if attempt < 3:
                        time.sleep(1)
                    continue

                invite_id = matched_server.get("id", "")
                accept_url = f"{v2_base}/api/v2/shared_servers/{invite_id}/accept"
                accept_resp = user_account._session.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                    accept_url,
                    params=v2_params,
                    headers=v2_headers,
                    timeout=30,
                )
                _ = accept_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                log.info(
                    "plex_auto_accept_invite_accepted",
                    invite_id=invite_id,
                    attempt=attempt,
                )
                return True
            except Exception as exc:
                log.warning(
                    "plex_auto_accept_invite_failed",
                    attempt=attempt,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                if attempt < 3:
                    time.sleep(1)
        return False

    def _cancel_stale_invites() -> int:
        """Cancel admin-sent pending invites for email on this server."""
        from plexapi.myplex import MyPlexAccount

        admin_account: MyPlexAccount = MyPlexAccount(token=admin_token)
        pending = admin_account.pendingInvites(  # pyright: ignore[reportUnknownVariableType]
            includeSent=True,
            includeReceived=False,
        )
        cancelled = 0
        for invite in pending:  # pyright: ignore[reportUnknownVariableType]
            invite_email: str = getattr(invite, "email", "") or ""  # pyright: ignore[reportUnknownArgumentType]
            if invite_email.lower() != email.lower():
                continue
            invite_servers: list[object] = getattr(invite, "servers", []) or []  # pyright: ignore[reportUnknownArgumentType]
            for server_share in invite_servers:
                if getattr(server_share, "machineIdentifier", "") == machine_id:
                    _ = admin_account.cancelInvite(invite)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
                    cancelled += 1
                    break
        return cancelled

    log.info(
        "plex_auto_accept_started",
        email=email,
        plex_user_id=plex_user_id,
        machine_id=machine_id,
    )
    try:
        accepted = await asyncio.to_thread(_accept)
        if accepted:
            log.info(
                "plex_auto_accept_completed",
                email=email,
                plex_user_id=plex_user_id,
            )
            # Cancel stale admin-sent pending invites now that the user
            # has accepted.  Best-effort — failures are logged but ignored.
            try:
                count = await asyncio.to_thread(_cancel_stale_invites)
                if count > 0:
                    log.info(
                        "plex_pending_invites_cancelled",
                        email=email,
                        count=count,
                    )
            except Exception as exc:
                log.warning(
                    "plex_cancel_pending_invites_failed",
                    email=email,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
        else:
            log.warning(
                "plex_auto_accept_exhausted",
                email=email,
                plex_user_id=plex_user_id,
            )
    except Exception as exc:
        log.error(
            "plex_auto_accept_failed",
            email=email,
            plex_user_id=plex_user_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )


# Error code constants for Plex API errors
# These map Plex-specific error patterns to standardized error codes
@final
class PlexErrorCode:
    """Error codes for Plex API operations.

    These codes provide standardized error identification across
    all PlexClient operations, enabling consistent error handling
    and logging throughout the application.
    """

    # User-related errors
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    USERNAME_TAKEN = "USERNAME_TAKEN"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    EMAIL_REQUIRED = "EMAIL_REQUIRED"

    # Connection errors
    CONNECTION_ERROR = "CONNECTION_ERROR"
    INVALID_TOKEN = "INVALID_TOKEN"  # noqa: S105
    SERVER_UNREACHABLE = "SERVER_UNREACHABLE"
    TIMEOUT = "TIMEOUT"

    # Client state errors
    CLIENT_NOT_INITIALIZED = "CLIENT_NOT_INITIALIZED"

    # API errors
    API_ERROR = "API_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    PERMISSION_DENIED = "PERMISSION_DENIED"

    # Library errors
    LIBRARY_NOT_FOUND = "LIBRARY_NOT_FOUND"
    INVALID_LIBRARY_ID = "INVALID_LIBRARY_ID"


def _map_plex_error_to_code(error: Exception) -> str:
    """Map a Plex API exception to a standardized error code.

    Analyzes the exception message to determine the appropriate
    error code for consistent error handling.

    Args:
        error: The exception raised by the Plex API.

    Returns:
        A standardized error code string.
    """
    error_str = str(error).lower()

    # User-related errors
    if "already" in error_str and ("shar" in error_str or "friend" in error_str):
        return PlexErrorCode.USER_ALREADY_EXISTS
    if "taken" in error_str or ("exists" in error_str and "user" in error_str):
        return PlexErrorCode.USERNAME_TAKEN
    if "not found" in error_str or "does not exist" in error_str:
        return PlexErrorCode.USER_NOT_FOUND

    # Connection errors
    if "unauthorized" in error_str or "401" in error_str:
        return PlexErrorCode.INVALID_TOKEN
    if "timeout" in error_str or "timed out" in error_str:
        return PlexErrorCode.TIMEOUT
    if (
        "connection" in error_str
        or "unreachable" in error_str
        or "refused" in error_str
    ):
        return PlexErrorCode.CONNECTION_ERROR

    # Rate limiting
    if "rate" in error_str and "limit" in error_str:
        return PlexErrorCode.RATE_LIMITED

    # Permission errors
    if "permission" in error_str or "forbidden" in error_str or "403" in error_str:
        return PlexErrorCode.PERMISSION_DENIED

    # Default to generic API error
    return PlexErrorCode.API_ERROR


def _is_external_service_error(error: Exception) -> bool:
    """Determine if an error is an external service error.

    External service errors are connection failures, timeouts, and
    server-side API errors that indicate the Plex server is unavailable
    or malfunctioning.

    Args:
        error: The exception to check.

    Returns:
        True if the error is an external service error, False otherwise.
    """
    error_code = _map_plex_error_to_code(error)
    return error_code in {
        PlexErrorCode.CONNECTION_ERROR,
        PlexErrorCode.TIMEOUT,
        PlexErrorCode.SERVER_UNREACHABLE,
        PlexErrorCode.RATE_LIMITED,
        PlexErrorCode.API_ERROR,
        PlexErrorCode.INVALID_TOKEN,
    }


def _create_media_client_error(
    message: str,
    *,
    operation: str,
    server_url: str,
    cause: str,
    error_code: str | None = None,
    original_error: Exception | None = None,
) -> MediaClientError:
    """Create a MediaClientError with consistent structure.

    Ensures all MediaClientError instances have the required fields:
    operation, server_url, and cause.

    Args:
        message: Human-readable error description.
        operation: The operation that failed (e.g., "create_user").
        server_url: The Plex server URL.
        cause: Description of what caused the failure.
        error_code: Optional specific error code.
        original_error: Optional original exception for error code mapping.

    Returns:
        A properly structured MediaClientError.
    """
    # Determine error code from original error if not provided
    if error_code is None and original_error is not None:
        error_code = _map_plex_error_to_code(original_error)

    return MediaClientError(
        message,
        operation=operation,
        server_url=server_url,
        cause=cause,
        error_code=error_code,
    )


def _create_external_service_error(
    message: str,
    *,
    server_url: str,
    original_error: Exception | None = None,
) -> ExternalServiceError:
    """Create an ExternalServiceError for Plex server failures.

    Used when the Plex server is unreachable, times out, or returns
    an API error indicating the service is unavailable.

    Args:
        message: Human-readable error description.
        server_url: The Plex server URL (used as service_name).
        original_error: The original exception that caused this error.

    Returns:
        An ExternalServiceError with the server URL as service name.
    """
    return ExternalServiceError(
        f"Plex ({server_url})",
        message,
        original=original_error,
    )


class PlexClient:
    """Plex media server client.

    Implements the MediaClient protocol for Plex servers.
    Uses python-plexapi for server communication.

    PlexAPI is synchronous, so all operations use asyncio.to_thread()
    to run without blocking the event loop.

    Attributes:
        url: The Plex server URL.
        api_key: The API key (X-Plex-Token) for authentication.
        timeout_seconds: Timeout for Plex API requests in seconds.
    """

    url: str
    api_key: str
    timeout_seconds: int
    _server: PlexServer | None
    _account: MyPlexAccount | None

    def __init__(self, *, url: str, api_key: str, timeout_seconds: int = 30) -> None:
        """Initialize a PlexClient.

        Args:
            url: The Plex server URL (keyword-only).
            api_key: The API key (X-Plex-Token) for authentication (keyword-only).
            timeout_seconds: Timeout for Plex API requests (keyword-only).
        """
        self.url = url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._server = None
        self._account = None

    @classmethod
    def capabilities(cls) -> set[Capability]:
        """Return the set of capabilities this client supports.

        Plex supports user creation, deletion, and library access
        configuration. Note that Plex does not support enable/disable
        user functionality directly.

        Returns:
            A set of Capability enum values indicating supported features.
        """
        return {
            Capability.CREATE_USER,
            Capability.DELETE_USER,
            Capability.LIBRARY_ACCESS,
            Capability.REMOVE_SHARED_ACCESS,
        }

    @classmethod
    def supported_permissions(cls) -> frozenset[str]:
        return frozenset({"can_download"})

    async def _run_with_timeout[T](
        self,
        func: Callable[[], T],
        *,
        operation: str,
    ) -> T:
        """Run a synchronous function in a thread with an asyncio timeout safety net.

        Args:
            func: The synchronous callable to run.
            operation: Name of the operation (for logging on timeout).

        Returns:
            The result of the callable.

        Raises:
            TimeoutError: Re-raised after logging when the operation exceeds
                the configured timeout.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(func),
                timeout=self.timeout_seconds,
            )
        except TimeoutError as exc:
            log.error(
                "plex_api_timeout",
                operation=operation,
                timeout_seconds=self.timeout_seconds,
                url=self.url,
            )
            msg = f"Plex API operation '{operation}' timed out after {self.timeout_seconds}s"
            raise TimeoutError(msg) from exc

    async def __aenter__(self) -> Self:
        """Enter async context, establishing connection.

        Initializes the PlexServer and MyPlexAccount connections using
        asyncio.to_thread() since python-plexapi is synchronous.
        Configures a requests.Session with a default timeout so that
        all plexapi HTTP calls respect the configured limit.

        Returns:
            Self for use in async with statements.

        Raises:
            ExternalServiceError: If connection to the Plex server fails.
        """
        import requests
        from plexapi.server import PlexServer

        def _connect() -> tuple[PlexServer, MyPlexAccount]:
            session = requests.Session()
            # Set a default timeout on all requests made through this session
            # by monkey-patching session.request to inject the timeout kwarg.
            _original_request = session.request

            def _request_with_timeout(
                *args: Any,  # pyright: ignore[reportExplicitAny, reportAny]  # wrapper must match Session.request
                **kwargs: Any,  # pyright: ignore[reportExplicitAny, reportAny]  # wrapper must match Session.request
            ) -> requests.Response:
                kwargs.setdefault("timeout", self.timeout_seconds)
                return _original_request(*args, **kwargs)  # pyright: ignore[reportAny]

            session.request = _request_with_timeout  # type: ignore[assignment]
            server = PlexServer(
                self.url,
                self.api_key,
                session=session,
                timeout=self.timeout_seconds,
            )
            # plexapi lacks type stubs, myPlexAccount returns MyPlexAccount
            account: MyPlexAccount = server.myPlexAccount()
            return server, account

        log.info("plex_client_connecting", url=self.url)
        try:
            self._server, self._account = await self._run_with_timeout(
                _connect, operation="connect"
            )
        except TimeoutError as exc:
            raise _create_external_service_error(
                f"Timed out connecting to Plex server after {self.timeout_seconds}s",
                server_url=self.url,
                original_error=exc,
            ) from exc
        except Exception as exc:
            log.error(
                "plex_client_connection_failed",
                url=self.url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise _create_external_service_error(
                f"Failed to connect to Plex server: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc
        log.info("plex_client_connected", url=self.url)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit async context, cleaning up resources.

        Releases the PlexServer and MyPlexAccount instances.

        Args:
            exc_type: The exception type if an exception was raised, None otherwise.
            exc_val: The exception instance if an exception was raised, None otherwise.
            exc_tb: The traceback if an exception was raised, None otherwise.
        """
        log.info("plex_client_disconnecting", url=self.url)
        self._server = None
        self._account = None

    async def test_connection(self) -> bool:
        """Test connectivity to the Plex server.

        Verifies that the server is reachable and the API key is valid
        by querying server information via python-plexapi.

        Returns:
            True if the connection is successful and authenticated,
            False otherwise. Never raises exceptions for connection failures.
        """
        if self._server is None:
            return False

        try:

            def _query_server_info() -> str:
                # Access server friendlyName to verify connectivity
                # This requires a valid connection and token
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, friendlyName is str
                name: str = self._server.friendlyName  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                return name  # pyright: ignore[reportUnknownVariableType]

            server_name = await self._run_with_timeout(
                _query_server_info, operation="test_connection"
            )
            log.info("plex_connection_test_success", url=self.url, server=server_name)
            return True
        except Exception as exc:
            log.warning("plex_connection_test_failed", url=self.url, error=str(exc))
            return False

    async def get_server_info(self) -> ServerInfo:
        """Return server name and version metadata.

        Accesses plexapi's friendlyName and version attributes.
        Uses asyncio.to_thread() since plexapi is synchronous.

        Returns:
            A ServerInfo object with the server's name and version.

        Raises:
            MediaClientError: If the client is not initialized.
        """
        if self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="get_server_info",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        def _get_info() -> ServerInfo:
            assert self._server is not None  # noqa: S101
            name: str = self._server.friendlyName  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            version: str = self._server.version  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            return ServerInfo(server_name=name, version=version)  # pyright: ignore[reportUnknownArgumentType]

        return await self._run_with_timeout(_get_info, operation="get_server_info")

    async def get_libraries(self) -> Sequence[LibraryInfo]:
        """Retrieve all libraries (sections) from the Plex server.

        Fetches the list of content libraries (movies, TV shows, music, etc.)
        available on the server via python-plexapi's library.sections().

        Maps Plex section attributes to LibraryInfo:
        - key -> external_id
        - title -> name
        - type -> library_type (movie, show, artist, photo, etc.)

        Returns:
            A sequence of LibraryInfo objects describing each library.

        Raises:
            MediaClientError: If the client is not initialized (use async context manager).
            MediaClientError: If library retrieval fails due to connection or API errors.
        """
        if self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="get_libraries",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _get_sections() -> list[LibraryInfo]:
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, sections() returns list of LibrarySection
                sections = self._server.library.sections()  # pyright: ignore[reportUnknownVariableType]
                return [
                    LibraryInfo(
                        external_id=str(section.key),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                        name=section.title,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                        library_type=section.type,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                    )
                    for section in sections  # pyright: ignore[reportUnknownVariableType]
                ]

            libraries = await self._run_with_timeout(
                _get_sections, operation="get_libraries"
            )
            log.info(
                "plex_libraries_retrieved",
                url=self.url,
                count=len(libraries),
            )
            return libraries

        except MediaClientError:
            raise
        except Exception as exc:
            log.error(
                "plex_get_libraries_failed",
                url=self.url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to retrieve libraries from Plex server: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to retrieve libraries from Plex server: {exc}",
                operation="get_libraries",
                server_url=self.url,
                cause=str(exc),
                original_error=exc,
            ) from exc

    async def _share_library_direct(
        self,
        email: str,
        auth_token: str,
        *,
        library_section_ids: list[int] | None = None,
    ) -> ExternalUser:
        """Share server libraries directly using the user's Plex auth token.

        Uses the shared_servers API with the user's numeric Plex ID (obtained
        from their OAuth token) to grant library access directly. This avoids
        creating a friend relationship and requires no manual acceptance.

        Args:
            email: The email address of the Plex user.
            auth_token: The user's Plex OAuth auth token.
            library_section_ids: Optional list of integer Plex library section
                IDs to restrict access to. Empty list or None means all libraries.

        Returns:
            An ExternalUser with the numeric Plex user ID and username.

        Raises:
            MediaClientError: If direct sharing fails.
            ExternalServiceError: If the Plex API is unreachable or returns a server error.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="share_library_direct",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:
            from plexapi.myplex import MyPlexAccount

            def _share_direct() -> tuple[ExternalUser, str, str]:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                # Get the user's Plex account info from their auth token
                user_account: MyPlexAccount = MyPlexAccount(token=auth_token)
                plex_user_id: str = str(user_account.id)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                username: str = user_account.username or email  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Pre-cleanup: remove any residual friend/sharing relationships
                # and shared_server entries from prior invitation cycles.
                # Best-effort — don't fail if nothing to clean up.
                try:
                    _ = self._remove_friend_and_sharing_sync(
                        plex_user_id, best_effort=True
                    )
                    log.info(
                        "plex_share_direct_pre_cleanup_friend_sharing",
                        url=self.url,
                        plex_user_id=plex_user_id,
                    )
                except Exception as exc:
                    log.debug(
                        "plex_share_direct_pre_cleanup_friend_sharing_skipped",
                        url=self.url,
                        plex_user_id=plex_user_id,
                        error=str(exc),
                    )

                try:
                    _ = self._remove_shared_server_access_sync(plex_user_id)
                    log.info(
                        "plex_share_direct_pre_cleanup_shared_server",
                        url=self.url,
                        plex_user_id=plex_user_id,
                    )
                except Exception as exc:
                    log.debug(
                        "plex_share_direct_pre_cleanup_shared_server_skipped",
                        url=self.url,
                        plex_user_id=plex_user_id,
                        error=str(exc),
                    )

                # Get the server's machine identifier
                machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Use the admin account's shared_servers API to grant access
                # This mirrors plexapi's updateFriend() when user has no existing access:
                # POST to shared_servers with invited_id (numeric Plex user ID)
                base_headers: dict[str, str] = self._account._headers()  # pyright: ignore[reportUnknownMemberType, reportAssignmentType, reportPrivateUsage, reportUnknownVariableType]
                headers: dict[str, str] = {
                    **base_headers,
                    "Content-Type": "application/json",
                }
                sharing_url = f"https://plex.tv/api/servers/{machine_id}/shared_servers"
                # Match plexapi's JSON body structure (nested dicts, not bracket-notation)
                # Empty library_section_ids list = share all libraries (same as plexapi default)
                # Non-empty list = share only those specific libraries
                # IMPORTANT: Plex shared_servers API requires cloud-side section IDs
                # (e.g. 142227451), not local section keys (e.g. 1).
                # Use plexapi's _getSectionIds() to translate.
                if library_section_ids:
                    sections = [  # pyright: ignore[reportUnknownVariableType]
                        self._server.library.sectionByID(sid)  # pyright: ignore[reportUnknownMemberType]
                        for sid in library_section_ids
                    ]
                    section_ids: list[int] = self._account._getSectionIds(  # pyright: ignore[reportUnknownMemberType, reportPrivateUsage, reportUnknownVariableType]
                        machine_id, sections
                    )
                else:
                    section_ids = []
                params: dict[str, str | dict[str, str | int | list[int]]] = {
                    "server_id": machine_id,
                    "shared_server": {
                        "library_section_ids": section_ids,
                        "invited_id": int(plex_user_id),
                        "skipFriendship": True,
                    },
                    "sharing_settings": {
                        "filterMovies": "",
                        "filterTelevision": "",
                        "filterMusic": "",
                    },
                }
                # Use the admin account's session to make the request (JSON body)
                resp = self._account._session.post(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                    sharing_url,
                    headers=headers,
                    json=params,
                    timeout=30,
                )
                _ = resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Capture admin username for the background auto-accept task
                admin_uname: str = self._account.username or ""  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                return (  # pyright: ignore[reportUnknownVariableType]
                    ExternalUser(
                        external_user_id=plex_user_id,
                        username=username,  # pyright: ignore[reportUnknownArgumentType]
                        email=email,
                        user_type="shared",
                    ),
                    machine_id,
                    admin_uname,
                )

            result, machine_id, admin_username = await self._run_with_timeout(
                _share_direct, operation="share_library_direct"
            )

            log.info(
                "plex_library_shared_direct",
                url=self.url,
                email=email,
                user_id=result.external_user_id,
                username=result.username,
            )

            # Fire auto-accept as a background task so the HTTP response
            # returns immediately.  Auto-accept is best-effort — if it
            # fails the user can accept the invite manually from Plex.
            task = asyncio.create_task(
                _auto_accept_plex_invite(
                    auth_token=auth_token,
                    admin_token=self.api_key,
                    admin_username=admin_username,
                    machine_id=machine_id,
                    email=email,
                    plex_user_id=result.external_user_id,
                ),
                name=f"plex-auto-accept-{result.external_user_id}",
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

            return result

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)
            log.error(
                "plex_direct_share_failed",
                url=self.url,
                email=email,
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to share library directly: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to share library directly: {exc}",
                operation="share_library_direct",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def _cancel_pending_invites_for_user(self, email: str) -> int:
        """Cancel any pending sent invites for a user on our server.

        Best-effort cleanup: uses the admin's account to find and cancel
        any pending invitations sent to the given email for this server.
        This prevents stale pending invites from lingering after direct
        library sharing has already granted access.

        Args:
            email: The email address to match against pending invites.

        Returns:
            The number of invites cancelled. Returns 0 on any error.
        """
        if self._account is None or self._server is None:
            return 0

        try:

            def _cancel_invites() -> int:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Get pending invites sent by the admin
                pending = self._account.pendingInvites(  # pyright: ignore[reportUnknownVariableType]
                    includeSent=True,
                    includeReceived=False,
                )

                cancelled = 0
                for invite in pending:  # pyright: ignore[reportUnknownVariableType]
                    invite_email: str = getattr(invite, "email", "") or ""  # pyright: ignore[reportUnknownArgumentType]
                    if invite_email.lower() != email.lower():
                        continue

                    # Check if this invite is for our server
                    invite_servers: list[object] = getattr(invite, "servers", []) or []  # pyright: ignore[reportUnknownArgumentType]
                    for server_share in invite_servers:
                        share_machine_id: str = getattr(
                            server_share, "machineIdentifier", ""
                        )
                        if share_machine_id == machine_id:
                            _ = self._account.cancelInvite(invite)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
                            cancelled += 1
                            break

                return cancelled

            count = await self._run_with_timeout(
                _cancel_invites, operation="cancel_pending_invites"
            )

            if count > 0:
                log.info(
                    "plex_pending_invites_cancelled",
                    url=self.url,
                    email=email,
                    count=count,
                )

            return count

        except Exception as exc:
            log.warning(
                "plex_cancel_pending_invites_failed",
                url=self.url,
                email=email,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return 0

    def _find_user_by_email_sync(self, email: str) -> tuple[str, str] | None:
        """Find a user in account.users() by email (case-insensitive).

        Synchronous helper — must be called from a thread (via asyncio.to_thread).

        Args:
            email: The email address to search for.

        Returns:
            A tuple of (numeric_plex_id, username) if found, None otherwise.
        """
        assert self._account is not None  # noqa: S101
        users = self._account.users()  # pyright: ignore[reportUnknownVariableType]
        for u in users:  # pyright: ignore[reportUnknownVariableType]
            u_email: str = getattr(u, "email", "") or ""  # pyright: ignore[reportUnknownArgumentType]
            if u_email.lower() == email.lower():
                plex_id: int | None = getattr(u, "id", None)  # pyright: ignore[reportUnknownArgumentType]
                if not plex_id:
                    return None
                return (
                    str(plex_id),
                    getattr(u, "username", None) or email,  # pyright: ignore[reportUnknownArgumentType]
                )
        return None

    def _invoke_invite_friend_sync(
        self,
        email: str,
        library_section_ids: list[int] | None,
    ) -> None:
        """Resolve library sections and call inviteFriend (synchronous).

        Synchronous helper — must be called from a thread (via asyncio.to_thread).

        Args:
            email: The email address of the Plex.tv account to invite.
            library_section_ids: Optional list of integer Plex library section
                IDs to restrict access to. None means all libraries.
        """
        assert self._account is not None  # noqa: S101
        assert self._server is not None  # noqa: S101
        sections = None
        if library_section_ids:
            sections = [  # pyright: ignore[reportUnknownVariableType]
                self._server.library.sectionByID(sid)  # pyright: ignore[reportUnknownMemberType]
                for sid in library_section_ids
            ]
        self._account.inviteFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
            user=email,
            server=self._server,
            sections=sections,
        )

    async def _invite_friend(
        self,
        email: str,
        *,
        library_section_ids: list[int] | None = None,
    ) -> ExternalUser:
        """Invite a Friend user via inviteFriend (legacy fallback).

        Sends an invitation to an existing Plex.tv account. The user must
        have an existing Plex account or create one to accept the invitation.

        Note: This creates a pending friend invitation that requires manual
        acceptance. Prefer _share_library_direct when an auth_token is available.

        Args:
            email: The email address of the Plex.tv account to invite.
            library_section_ids: Optional list of integer Plex library section
                IDs to restrict access to. These are resolved to LibrarySection
                objects for plexapi's inviteFriend(sections=...) parameter.
                None means all libraries.

        Returns:
            An ExternalUser with the numeric Plex user ID as external_user_id.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the user is already a Friend (USER_ALREADY_EXISTS).
            MediaClientError: If the invitation fails for other reasons.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="create_friend",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _invite() -> tuple[str, str]:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101
                self._invoke_invite_friend_sync(email, library_section_ids)

                # Resolve the numeric Plex user ID by looking up the user
                # in account.users(). The inviteFriend() return value's .id
                # may not be the numeric ID needed by Plex v2 APIs
                # (friends/sharings deletion). This lookup mirrors the
                # pattern used in delete_user().
                result = self._find_user_by_email_sync(email)
                if result is not None:
                    return result

                # Fallback: user not yet in friends list (pending
                # invite). Log warning; email stored as last resort.
                log.warning(
                    "plex_invite_friend_numeric_id_not_resolved",
                    url=self.url,
                    email=email,
                )
                return (email, email)

            user_id, username = await self._run_with_timeout(
                _invite, operation="invite_friend"
            )

            log.info(
                "plex_friend_created",
                url=self.url,
                email=email,
                user_id=user_id,
            )

            return ExternalUser(
                external_user_id=user_id,
                username=username,
                email=email,
                user_type="friend",
            )

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Handle orphaned Plex relationships: when a previous
            # deletion failed to fully clean up, the Plex friendship
            # persists and blocks re-invitation.  Attempt to remove the
            # orphaned relationship and retry once.
            if error_code == PlexErrorCode.USER_ALREADY_EXISTS:
                log.warning(
                    "plex_friend_already_exists",
                    url=self.url,
                    email=email,
                    error=str(exc),
                )

                # Attempt cleanup-and-retry
                try:
                    cleanup_result = await self._cleanup_orphaned_and_retry_invite(
                        email, library_section_ids=library_section_ids
                    )
                    if cleanup_result is not None:
                        return cleanup_result
                except Exception as cleanup_exc:
                    # Cleanup/retry failed - fall through to raise
                    # the original USER_ALREADY_EXISTS error below.
                    log.debug(
                        "plex_orphaned_cleanup_failed",
                        url=self.url,
                        email=email,
                        error=str(cleanup_exc),
                    )
            else:
                log.error(
                    "plex_create_friend_failed",
                    url=self.url,
                    email=email,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    error_code=error_code,
                )

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to invite Friend: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            raise _create_media_client_error(
                f"Failed to invite Friend: {exc}"
                if error_code != PlexErrorCode.USER_ALREADY_EXISTS
                else f"User with email {email} is already a Friend",
                operation="create_friend",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def _cleanup_orphaned_and_retry_invite(
        self,
        email: str,
        *,
        library_section_ids: list[int] | None = None,
    ) -> ExternalUser | None:
        """Attempt to clean up an orphaned Plex friendship and retry the invite.

        When a previous user deletion failed to fully remove the Plex
        relationship, the friendship persists and blocks re-invitation.
        This method looks up the user's numeric Plex ID, removes the
        orphaned friend/sharing relationships, and retries inviteFriend().

        Args:
            email: The email address of the Plex.tv account.
            library_section_ids: Optional library section IDs to share.

        Returns:
            An ExternalUser if the retry succeeded, None if the user
            could not be found in the friends list (cleanup not possible).
        """
        assert self._account is not None  # noqa: S101
        assert self._server is not None  # noqa: S101

        def _lookup_and_cleanup() -> str | None:
            result = self._find_user_by_email_sync(email)
            if result is not None:
                return result[0]
            return None

        plex_user_id = await self._run_with_timeout(
            _lookup_and_cleanup, operation="cleanup_orphaned_lookup"
        )

        if plex_user_id is None:
            log.warning(
                "plex_orphaned_cleanup_user_not_found",
                url=self.url,
                email=email,
            )
            return None

        log.info(
            "plex_orphaned_cleanup_attempting",
            url=self.url,
            email=email,
            plex_user_id=plex_user_id,
        )

        # Remove orphaned relationship (best_effort to avoid raising)
        cleanup_ok = await self._run_with_timeout(
            lambda: self._remove_friend_and_sharing_sync(
                plex_user_id, best_effort=True
            ),
            operation="cleanup_orphaned_remove",
        )

        log.info(
            "plex_orphaned_cleanup_result",
            url=self.url,
            email=email,
            plex_user_id=plex_user_id,
            cleanup_ok=cleanup_ok,
        )

        if not cleanup_ok:
            return None

        # Retry the invitation after cleanup
        def _retry_invite() -> tuple[str, str]:
            assert self._account is not None  # noqa: S101
            assert self._server is not None  # noqa: S101
            self._invoke_invite_friend_sync(email, library_section_ids)

            # Resolve the numeric Plex user ID (same pattern as _invite)
            result = self._find_user_by_email_sync(email)
            if result is not None:
                return result
            return (email, email)

        user_id, username = await self._run_with_timeout(
            _retry_invite, operation="cleanup_orphaned_reinvite"
        )

        log.info(
            "plex_orphaned_cleanup_reinvite_succeeded",
            url=self.url,
            email=email,
            user_id=user_id,
        )

        return ExternalUser(
            external_user_id=user_id,
            username=username,
            email=email,
            user_type="friend",
        )

    async def _create_friend(
        self,
        email: str,
        *,
        auth_token: str | None = None,
        library_section_ids: list[int] | None = None,
    ) -> ExternalUser:
        """Create a Friend/shared user on the Plex server.

        If auth_token is provided, uses direct library sharing via the
        shared_servers API (no friend relationship, immediate access).
        Otherwise falls back to inviteFriend (creates pending invitation).

        Args:
            email: The email address of the Plex.tv account.
            auth_token: Optional OAuth auth token from the user.
            library_section_ids: Optional list of integer Plex library section
                IDs to restrict access to. None means all libraries.

        Returns:
            An ExternalUser with the user's details.

        Raises:
            MediaClientError: If user creation fails.
        """
        if auth_token:
            return await self._share_library_direct(
                email, auth_token, library_section_ids=library_section_ids
            )
        return await self._invite_friend(email, library_section_ids=library_section_ids)

    async def _create_home_user(self, username: str) -> ExternalUser:
        """Create a Home User via createHomeUser.

        Creates a managed user within the Plex Home. Home Users do not
        require an external Plex.tv account.

        Args:
            username: The username for the new Home User.

        Returns:
            An ExternalUser with the Plex user ID as external_user_id.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the username is already taken (USERNAME_TAKEN).
            MediaClientError: If Home User creation fails for other reasons.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="create_home_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _create() -> object:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101
                # plexapi lacks type stubs, createHomeUser returns MyPlexUser
                return self._account.createHomeUser(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                    user=username,
                    server=self._server,
                )

            user = await self._run_with_timeout(_create, operation="create_home_user")
            # plexapi MyPlexUser has id attribute
            user_id: str = str(getattr(user, "id", ""))

            log.info(
                "plex_home_user_created",
                url=self.url,
                username=username,
                user_id=user_id,
            )

            return ExternalUser(
                external_user_id=user_id,
                username=username,
                email=None,
                user_type="home",
            )

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Log the error with appropriate level
            if error_code == PlexErrorCode.USERNAME_TAKEN:
                log.warning(
                    "plex_home_user_username_taken",
                    url=self.url,
                    username=username,
                    error=str(exc),
                )
            else:
                log.error(
                    "plex_create_home_user_failed",
                    url=self.url,
                    username=username,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    error_code=error_code,
                )

            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to create Home User: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc

            raise _create_media_client_error(
                f"Failed to create Home User: {exc}"
                if error_code != PlexErrorCode.USERNAME_TAKEN
                else f"Username '{username}' is already taken",
                operation="create_home_user",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def create_user(
        self,
        username: str,
        password: str,
        /,
        *,
        email: str | None = None,
        auth_token: str | None = None,
        library_ids: Sequence[str] | None = None,
    ) -> ExternalUser:
        """Create a new user on the Plex server.

        Uses email presence to determine the user type:
        - If email is provided, creates a Friend/shared user via Plex.tv.
          If auth_token is also provided, uses direct library sharing
          (no friend relationship, immediate access).
        - If no email, creates a managed Home User within the Plex Home.

        Note: The password parameter is ignored for Plex since authentication
        is handled through Plex.tv accounts or managed Home Users.

        Args:
            username: The username for the new account (positional-only).
            password: Ignored for Plex (positional-only).
            email: Email address (keyword-only). If provided, creates a Friend
                or shared user; otherwise creates a Home User.
            auth_token: Optional OAuth auth token from the user (keyword-only).
                When provided with email, enables direct library sharing.
            library_ids: Optional library external IDs (strings) to restrict
                access to at creation time (keyword-only). Converted to integer
                Plex section IDs internally. None means all libraries.

        Returns:
            An ExternalUser object with the created user's details.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the user already exists.
            MediaClientError: If user creation fails for other reasons.
        """
        _ = password  # Explicitly ignore password parameter

        # Convert string library IDs to integer Plex section IDs
        section_ids: list[int] | None = None
        if library_ids:
            try:
                section_ids = [int(lid) for lid in library_ids]
            except ValueError as exc:
                raise _create_media_client_error(
                    f"Invalid library ID(s): could not convert to integers: {exc}",
                    operation="create_user",
                    server_url=self.url,
                    cause=f"Non-integer library ID in {list(library_ids)}",
                    error_code=PlexErrorCode.INVALID_LIBRARY_ID,
                ) from exc

        if email is not None:
            return await self._create_friend(
                email,
                auth_token=auth_token,
                library_section_ids=section_ids,
            )

        # No email provided - create as Home User
        return await self._create_home_user(username)

    def _remove_shared_server_access_sync(self, external_user_id: str) -> bool:
        """Remove shared server access for a user (synchronous, call from thread).

        Queries the shared_servers API for the server's machine identifier,
        finds a shared server entry matching the user ID, and DELETEs it.

        Args:
            external_user_id: The user's numeric Plex user ID.

        Returns:
            True if a shared server entry was found and removed, False if not found.
        """
        assert self._account is not None  # noqa: S101
        assert self._server is not None  # noqa: S101

        machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        base_headers: dict[str, str] = self._account._headers()  # pyright: ignore[reportUnknownMemberType, reportAssignmentType, reportPrivateUsage, reportUnknownVariableType]
        headers: dict[str, str] = {
            **base_headers,
            "Accept": "application/json",
        }

        # GET shared servers for this machine
        sharing_url = f"https://plex.tv/api/servers/{machine_id}/shared_servers"
        resp = self._account._session.get(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
            sharing_url,
            headers=headers,
            timeout=30,
        )
        _ = resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

        # Parse JSON to find matching userID
        # Friend-only users may return an empty body (no shared server entries)
        try:
            data: dict[str, object] = resp.json()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except ValueError, TypeError:
            # Empty or non-JSON response — no shared server entries exist
            return False
        shared_servers: list[dict[str, object]] = []

        # Response may be {"SharedServer": [...]} or similar structure
        if isinstance(data, dict):
            for key in ("SharedServer", "shared_servers"):
                val = data.get(key)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
                if isinstance(val, list):
                    shared_servers = val  # pyright: ignore[reportUnknownVariableType]
                    break

        for entry in shared_servers:
            entry_user_id = str(entry.get("userID", ""))
            if entry_user_id == external_user_id:
                shared_server_id = entry.get("id", "")
                delete_url = f"https://plex.tv/api/servers/{machine_id}/shared_servers/{shared_server_id}"
                del_resp = self._account._session.delete(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                    delete_url,
                    headers=headers,
                    timeout=30,
                )
                _ = del_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                return True

        return False

    def _remove_friend_and_sharing_sync(
        self,
        external_user_id: str,
        *,
        best_effort: bool = False,
    ) -> bool:
        """Remove friend and sharing relationships for a user (synchronous).

        Calls DELETE on both /api/v2/friends/{id} and /api/v2/sharings/{id}
        to ensure complete removal regardless of how the user was added.

        Args:
            external_user_id: The user's numeric Plex user ID.
            best_effort: If True, suppress HTTP errors (404, etc.) from both
                endpoints. Used when the user wasn't found in account.users()
                and we're attempting cleanup speculatively.

        Returns:
            True if at least one endpoint succeeded, False otherwise.
        """
        assert self._account is not None  # noqa: S101
        base_headers: dict[str, str] = self._account._headers()  # pyright: ignore[reportUnknownMemberType, reportAssignmentType, reportPrivateUsage, reportUnknownVariableType]

        friends_removed = False
        sharing_removed = False

        # Attempt 1: Remove friend relationship via /api/v2/friends/
        friends_url = f"https://plex.tv/api/v2/friends/{external_user_id}"
        try:
            del_resp = self._account._session.delete(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                friends_url,
                headers=base_headers,
                timeout=30,
            )
            _ = del_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            log.info(
                "plex_friend_removed_via_v2_friends_api",
                url=self.url,
                user_id=external_user_id,
            )
            friends_removed = True
        except Exception as exc:
            if best_effort:
                log.debug(
                    "plex_friend_removal_skipped",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
            else:
                raise

        # Attempt 2: Remove sharing relationship via /api/v2/sharings/
        # This covers users added via _share_library_direct who may have
        # a sharing relationship but no friend relationship.
        sharings_url = f"https://plex.tv/api/v2/sharings/{external_user_id}"
        try:
            del_resp = self._account._session.delete(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportPrivateUsage]
                sharings_url,
                headers=base_headers,
                timeout=30,
            )
            _ = del_resp.raise_for_status()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            log.info(
                "plex_sharing_removed_via_v2_sharings_api",
                url=self.url,
                user_id=external_user_id,
            )
            sharing_removed = True
        except Exception as exc:
            resp = getattr(exc, "response", None)
            status: int | None = getattr(resp, "status_code", None)
            is_not_found = status == 404

            if best_effort or (friends_removed and is_not_found):
                # 404 is expected when friends removal already cascaded
                log.debug(
                    "plex_sharing_removal_skipped",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
            elif friends_removed:
                # Non-404 failure after successful friends removal.
                # The friend relationship is gone so the user is
                # effectively deleted; log a warning for visibility.
                log.warning(
                    "plex_sharing_removal_failed_after_friend_removal",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                    status_code=status,
                )
            else:
                raise

        return friends_removed or sharing_removed

    async def delete_user(self, external_user_id: str, /) -> bool:
        """Delete a user from the Plex server.

        Removes the user account identified by the external user ID.
        First removes shared server access (if server is connected),
        then removes the friend/home user relationship. Returns True if
        either path succeeds.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).

        Returns:
            True if the user was successfully deleted, False if the user
            was not found.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If deletion fails for reasons other than user not found.
        """
        if self._account is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="delete_user",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _delete() -> bool:
                assert self._account is not None  # noqa: S101
                # plexapi lacks type stubs, users() returns list of MyPlexUser
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                target_user: object | None = None
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    if user_id == external_user_id:
                        target_user = user  # pyright: ignore[reportUnknownVariableType]
                        break

                # Fallback: if no match by numeric ID, try matching by email
                # or username. This handles the case where external_user_id was
                # stored as an email address instead of a numeric Plex ID.
                if target_user is None:
                    for user in users:  # pyright: ignore[reportUnknownVariableType]
                        user_email: str = getattr(user, "email", "") or ""  # pyright: ignore[reportUnknownArgumentType]
                        user_username: str = getattr(user, "username", "") or ""  # pyright: ignore[reportUnknownArgumentType]
                        if external_user_id in (user_email, user_username):
                            target_user = user  # pyright: ignore[reportUnknownVariableType]
                            log.warning(
                                "plex_user_matched_by_email_fallback",
                                url=self.url,
                                external_user_id=external_user_id,
                                matched_id=str(getattr(user, "id", "")),  # pyright: ignore[reportUnknownArgumentType]
                            )
                            break

                # Step 1: Remove shared server access first (exceptions propagate)
                shared_deleted = False
                if self._server is not None:
                    shared_deleted = self._remove_shared_server_access_sync(
                        external_user_id
                    )

                # Step 2: Remove friend/home user relationship
                friend_deleted = False
                if target_user is not None:
                    is_home_user: bool = getattr(target_user, "home", False)  # pyright: ignore[reportUnknownArgumentType]

                    if is_home_user:
                        self._account.removeHomeUser(target_user)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportUnusedCallResult]
                        friend_deleted = True
                    else:
                        friend_deleted = self._remove_friend_and_sharing_sync(
                            external_user_id
                        )
                else:
                    # User not found in account.users() — may be a shared-only
                    # user (created via _share_library_direct). Always attempt
                    # friend/sharing removal to ensure complete cleanup,
                    # regardless of whether shared server access was found.
                    log.info(
                        "plex_user_not_in_friends_list_attempting_relationship_cleanup",
                        url=self.url,
                        user_id=external_user_id,
                    )
                    friend_deleted = self._remove_friend_and_sharing_sync(
                        external_user_id,
                        best_effort=True,
                    )

                return friend_deleted or shared_deleted

            deleted = await self._run_with_timeout(_delete, operation="delete_user")

            if deleted:
                log.info(
                    "plex_user_deleted",
                    url=self.url,
                    user_id=external_user_id,
                )
            else:
                log.warning(
                    "plex_user_not_found",
                    url=self.url,
                    user_id=external_user_id,
                )

            return deleted

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Check for not found error - return False instead of raising
            if error_code == PlexErrorCode.USER_NOT_FOUND:
                log.warning(
                    "plex_user_not_found",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            log.error(
                "plex_delete_user_failed",
                url=self.url,
                user_id=external_user_id,
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            # Any non-"not found" failure during deletion is an external
            # service error — the Plex API call itself failed.
            raise _create_external_service_error(
                f"Failed to delete user: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc

    async def remove_shared_access(self, external_user_id: str, /) -> bool:
        """Remove shared library access without removing the friend relationship.

        Calls _remove_shared_server_access_sync to delete the shared server
        entry for this user. The friend relationship is left intact.

        Args:
            external_user_id: The user's numeric Plex user ID (positional-only).

        Returns:
            True if shared access was found and removed, False otherwise.

        Raises:
            MediaClientError: If the client is not initialized or operation fails.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="remove_shared_access",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:
            removed = await self._run_with_timeout(
                lambda: self._remove_shared_server_access_sync(external_user_id),
                operation="remove_shared_access",
            )
            if removed:
                log.info(
                    "plex_shared_access_removed",
                    url=self.url,
                    user_id=external_user_id,
                )
            else:
                log.info(
                    "plex_no_shared_access_found",
                    url=self.url,
                    user_id=external_user_id,
                )
            return removed
        except MediaClientError:
            raise
        except Exception as exc:
            raise _create_external_service_error(
                f"Failed to remove shared access: {exc}",
                server_url=self.url,
                original_error=exc,
            ) from exc

    async def set_user_enabled(
        self,
        external_user_id: str,
        /,
        *,
        enabled: bool,
    ) -> bool:
        """Enable or disable a user on the Plex server.

        Note: Plex does not support enable/disable functionality.
        This method always returns False and logs a warning.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            enabled: Whether the user should be enabled (keyword-only).

        Returns:
            False always - Plex does not support this operation.
        """
        log.warning(
            "plex_set_user_enabled_unsupported",
            url=self.url,
            user_id=external_user_id,
            enabled=enabled,
            message="Plex does not support enable/disable user functionality",
        )
        return False

    async def set_library_access(
        self,
        external_user_id: str,
        library_ids: Sequence[str],
        /,
    ) -> bool:
        """Set which libraries a user can access on the Plex server.

        Configures the user's library permissions via updateFriend()
        for Friends or appropriate method for Home Users.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            library_ids: Sequence of library section keys to grant access to
                (positional-only). An empty sequence revokes all access.

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the library access update fails for reasons
                other than user not found.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="set_library_access",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _set_access() -> bool:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                # Get all users to find the target
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                # Find the user by ID
                target_user: object | None = None
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    if user_id == external_user_id:
                        target_user = user  # pyright: ignore[reportUnknownVariableType]
                        break

                if target_user is None:
                    return False

                # Get library sections to grant access to
                # Empty list means revoke all access
                sections: list[object] = []
                if library_ids:
                    for lib_id in library_ids:
                        try:
                            section = self._server.library.sectionByID(int(lib_id))  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
                            sections.append(section)  # pyright: ignore[reportUnknownArgumentType]
                        except Exception:
                            # Skip invalid library IDs
                            log.warning(
                                "plex_invalid_library_id",
                                url=self.url,
                                library_id=lib_id,
                            )

                # Determine if this is a Home User or Friend
                is_home_user: bool = getattr(target_user, "home", False)  # pyright: ignore[reportUnknownArgumentType]

                if is_home_user:
                    # For Home Users, use updateFriend with sections
                    # Note: Plex API uses same method for both user types
                    self._account.updateFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
                        user=target_user,  # pyright: ignore[reportUnknownArgumentType]
                        server=self._server,
                        sections=sections,
                    )
                else:
                    # For Friends, use updateFriend with sections
                    self._account.updateFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
                        user=target_user,  # pyright: ignore[reportUnknownArgumentType]
                        server=self._server,
                        sections=sections,
                    )

                return True

            updated = await self._run_with_timeout(
                _set_access, operation="set_library_access"
            )

            if updated:
                log.info(
                    "plex_library_access_updated",
                    url=self.url,
                    user_id=external_user_id,
                    library_count=len(library_ids),
                )
            else:
                log.warning(
                    "plex_user_not_found_for_library_access",
                    url=self.url,
                    user_id=external_user_id,
                )

            return updated

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Check for not found error - return False instead of raising
            if error_code == PlexErrorCode.USER_NOT_FOUND:
                log.warning(
                    "plex_user_not_found_for_library_access",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            log.error(
                "plex_set_library_access_failed",
                url=self.url,
                user_id=external_user_id,
                library_count=len(library_ids),
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to set library access: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to set library access: {exc}",
                operation="set_library_access",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def update_permissions(
        self,
        external_user_id: str,
        /,
        *,
        permissions: dict[str, bool],
    ) -> bool:
        """Update user permissions on the Plex server.

        Maps universal permissions to Plex-specific settings where applicable.
        Currently supports can_download -> allowSync mapping.

        Args:
            external_user_id: The user's unique identifier on the server
                (positional-only).
            permissions: Dictionary mapping universal permission names to boolean
                values (keyword-only). Only provided keys are updated.

        Returns:
            True if permissions were successfully updated, False if the user
            was not found.

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If the permission update fails for reasons
                other than user not found.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="update_permissions",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _update_permissions() -> bool:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                # Get all users to find the target
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                # Find the user by ID
                target_user: object | None = None
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    if user_id == external_user_id:
                        target_user = user  # pyright: ignore[reportUnknownVariableType]
                        break

                if target_user is None:
                    return False

                # Map universal permissions to Plex-specific settings
                # can_download -> allowSync
                allow_sync: bool | None = permissions.get("can_download")

                # Update the user's permissions via updateFriend
                # Note: Plex uses allowSync for download permission
                if allow_sync is not None:
                    self._account.updateFriend(  # pyright: ignore[reportUnknownMemberType, reportUnusedCallResult]
                        user=target_user,  # pyright: ignore[reportUnknownArgumentType]
                        server=self._server,
                        allowSync=allow_sync,
                    )

                return True

            updated = await self._run_with_timeout(
                _update_permissions, operation="update_permissions"
            )

            if updated:
                log.info(
                    "plex_permissions_updated",
                    url=self.url,
                    user_id=external_user_id,
                    permissions=list(permissions.keys()),
                )
            else:
                log.warning(
                    "plex_user_not_found_for_permissions",
                    url=self.url,
                    user_id=external_user_id,
                )

            return updated

        except MediaClientError:
            raise
        except Exception as exc:
            error_code = _map_plex_error_to_code(exc)

            # Check for not found error - return False instead of raising
            if error_code == PlexErrorCode.USER_NOT_FOUND:
                log.warning(
                    "plex_user_not_found_for_permissions",
                    url=self.url,
                    user_id=external_user_id,
                    error=str(exc),
                )
                return False

            log.error(
                "plex_update_permissions_failed",
                url=self.url,
                user_id=external_user_id,
                permissions=list(permissions.keys()),
                error=str(exc),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to update permissions: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to update permissions: {exc}",
                operation="update_permissions",
                server_url=self.url,
                cause=str(exc),
                error_code=error_code,
            ) from exc

    async def list_users(self) -> Sequence[ExternalUser]:
        """List all users with access to the Plex server.

        Retrieves all Friends and Home Users from the Plex account
        and maps them to ExternalUser structs.

        Returns:
            A sequence of ExternalUser objects with external_user_id,
            username, email (if available), and user_type (home, shared,
            or friend).

        Raises:
            MediaClientError: If the client is not initialized.
            MediaClientError: If user listing fails due to connection or API errors.
        """
        if self._account is None or self._server is None:
            raise _create_media_client_error(
                "Client not initialized - use async context manager",
                operation="list_users",
                server_url=self.url,
                cause="API client is None - __aenter__ was not called",
                error_code=PlexErrorCode.CLIENT_NOT_INITIALIZED,
            )

        try:

            def _list_users() -> list[ExternalUser]:
                assert self._account is not None  # noqa: S101
                assert self._server is not None  # noqa: S101

                machine_id: str = self._server.machineIdentifier  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                # Get all users (Friends and Home Users)
                users = self._account.users()  # pyright: ignore[reportUnknownVariableType]

                result: list[ExternalUser] = []
                for user in users:  # pyright: ignore[reportUnknownVariableType]
                    user_id: str = str(getattr(user, "id", ""))  # pyright: ignore[reportUnknownArgumentType]
                    username: str = getattr(user, "username", "") or user_id  # pyright: ignore[reportUnknownArgumentType]
                    email: str | None = getattr(user, "email", None)  # pyright: ignore[reportUnknownArgumentType]

                    if not user_id:
                        continue

                    # Classify user type based on home status and server shares
                    is_home: bool = getattr(user, "home", False)  # pyright: ignore[reportUnknownArgumentType]
                    if is_home:
                        user_type = "home"
                    else:
                        user_servers = getattr(user, "servers", []) or []  # pyright: ignore[reportUnknownArgumentType]
                        has_server_access = any(
                            getattr(s, "machineIdentifier", None) == machine_id  # pyright: ignore[reportUnknownArgumentType, reportAny]
                            for s in user_servers  # pyright: ignore[reportAny]
                        )
                        user_type = "shared" if has_server_access else "friend"

                    result.append(
                        ExternalUser(
                            external_user_id=user_id,
                            username=username,
                            email=email,
                            user_type=user_type,
                        )
                    )

                return result

            users = await self._run_with_timeout(_list_users, operation="list_users")

            log.info(
                "plex_users_listed",
                url=self.url,
                count=len(users),
            )

            return users

        except MediaClientError:
            raise
        except Exception as exc:
            log.error(
                "plex_list_users_failed",
                url=self.url,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Wrap external service errors appropriately
            if _is_external_service_error(exc):
                raise _create_external_service_error(
                    f"Failed to list users: {exc}",
                    server_url=self.url,
                    original_error=exc,
                ) from exc
            raise _create_media_client_error(
                f"Failed to list users: {exc}",
                operation="list_users",
                server_url=self.url,
                cause=str(exc),
                original_error=exc,
            ) from exc
