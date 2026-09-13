"""Retry and circuit-breaker infrastructure for external service calls.

Provides:
- RetryPolicy: Pure-async retry executor with exponential backoff and jitter.
- CircuitBreaker: Per-server state machine (CLOSED → OPEN → HALF_OPEN → CLOSED).
- CircuitBreakerRegistry: Container for per-server circuit breakers.
- is_retryable_sync_error: Provider-agnostic error classifier for sync operations.
- is_retryable_httpx_error: httpx error classifier for one-shot operations.
- is_retryable_httpx_connection: httpx error classifier for polled connections.
"""

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from uuid import UUID

import httpx
import structlog

from zondarr.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from zondarr.media.exceptions import MediaClientError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)  # pyright: ignore[reportAny]

# MediaClientError codes that indicate non-retryable, deterministic failures.
_NON_RETRYABLE_MEDIA_CODES: frozenset[str] = frozenset(
    {
        "INVALID_TOKEN",
        "USER_NOT_FOUND",
        "USERNAME_TAKEN",
        "PERMISSION_DENIED",
    }
)


def is_retryable_sync_error(exc: Exception, /) -> bool:
    """Determine whether an exception is retryable for sync operations.

    Classification works at the **exception type** level for provider-agnostic
    behaviour.  ``MediaClientError`` instances are further inspected: those
    carrying a ``media_error_code`` that indicates a deterministic failure
    (invalid token, user not found, username taken, permission denied) are
    treated as non-retryable.

    Unknown exception types default to **non-retryable** (fail safe).

    Args:
        exc: The exception to classify.

    Returns:
        ``True`` if the operation that raised *exc* should be retried.
    """
    # MediaClientError must be checked before ExternalServiceError because
    # MediaClientError inherits from ZondarrError (not ExternalServiceError),
    # but certain media errors are clearly non-retryable.
    if isinstance(exc, MediaClientError):
        if exc.media_error_code in _NON_RETRYABLE_MEDIA_CODES:
            return False
        # Other MediaClientErrors (e.g. transient API errors) are retryable.
        return True

    # Domain exceptions that are never retryable.
    if isinstance(exc, (NotFoundError, ValidationError)):
        return False

    # Transient infrastructure / external service failures.
    if isinstance(exc, (ExternalServiceError, TimeoutError, ConnectionError, OSError)):
        return True

    # Unknown exceptions — fail safe.
    return False


# HTTP status codes that represent transient server-side errors.
_RETRYABLE_HTTP_STATUS_CODES: frozenset[int] = frozenset({429, 502, 503, 504})


def is_retryable_httpx_error(exc: Exception, /) -> bool:
    """Determine whether an httpx exception is retryable for one-shot operations.

    Use this predicate with ``RetryPolicy`` when executing a single httpx
    request that should be retried on transient failures.  It classifies:

    - Connection-level errors (``ConnectError``, ``TimeoutException``) as
      retryable — the server may not have received the request at all.
    - HTTP status errors with codes 429, 502, 503, or 504 as retryable —
      these indicate transient server-side overload or downtime.
    - All other exceptions (including client errors like 400/401/404) as
      non-retryable.

    Args:
        exc: The exception to classify.

    Returns:
        ``True`` if the operation that raised *exc* should be retried.
    """
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_HTTP_STATUS_CODES

    return False


def _extract_retry_after(exc: Exception, /, *, max_delay: float) -> float | None:
    """Extract a ``Retry-After`` delay from an HTTP 429 response.

    Parses the ``Retry-After`` header in both delta-seconds and
    HTTP-date (IMF-fixdate) forms per RFC 9110 §10.2.3, and clamps
    the result to *max_delay*.  Returns ``None`` when the header is
    absent, unparsable, or the exception is not a 429 status error.

    Args:
        exc: The exception to inspect.
        max_delay: Upper bound applied to the parsed value.

    Returns:
        The clamped delay in seconds, or ``None``.
    """
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    if exc.response.status_code != 429:
        return None
    raw: str | None = exc.response.headers.get("retry-after")  # pyright: ignore[reportAny]
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        # Try HTTP-date form (IMF-fixdate, RFC 9110 §5.6.7).
        try:
            retry_dt = parsedate_to_datetime(raw)
        except ValueError, TypeError:
            return None
        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=UTC)
        seconds = max(0.0, (retry_dt - datetime.now(UTC)).total_seconds())
        return min(seconds, max_delay)
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return min(seconds, max_delay)


def is_retryable_httpx_connection(exc: Exception, /) -> bool:
    """Determine whether an httpx exception is retryable for polled connections.

    Use this predicate when the caller already retries at a higher level
    (e.g. polling for a PIN or waiting for an OAuth callback).  Only
    connection-level errors are retried — HTTP status errors are propagated
    immediately because the server *did* respond, and the higher-level
    retry logic should decide how to handle it.

    Args:
        exc: The exception to classify.

    Returns:
        ``True`` if the connection-level error warrants a retry.
    """
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class RetryPolicy:
    """Pure-async retry executor with exponential back-off and jitter.

    The delay between attempts is computed as::

        min(backoff_base * 2**attempt, max_delay) * (1 + random(0, jitter))

    For HTTP 429 responses with a ``Retry-After`` header, the server-
    requested delay (clamped to ``max_delay``) is used instead of the
    computed backoff.

    Attributes:
        max_retries: Maximum number of retries (total attempts = max_retries + 1).
        backoff_base: Base delay in seconds for the first retry.
        max_delay: Upper bound on computed delay.
        jitter: Maximum jitter factor applied to each delay.
    """

    max_retries: int
    backoff_base: float
    max_delay: float
    jitter: float

    def __init__(
        self,
        /,
        *,
        max_retries: int,
        backoff_base: float,
        max_delay: float = 60.0,
        jitter: float = 0.1,
    ) -> None:
        """Initialise a RetryPolicy.

        Args:
            max_retries: Maximum number of retries (total attempts = max_retries + 1).
            backoff_base: Base delay in seconds for the first retry.
            max_delay: Upper bound on computed delay.
            jitter: Maximum jitter factor applied to each delay.
        """
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_delay = max_delay
        self.jitter = jitter

    async def execute[T](
        self,
        operation: Callable[[], Awaitable[T]],
        /,
        *,
        is_retryable: Callable[[Exception], bool] = is_retryable_sync_error,
        on_retry: Callable[[int, float, Exception], None] | None = None,
    ) -> T:
        """Run *operation* with retry logic.

        Args:
            operation: An async callable to invoke.
            is_retryable: Predicate that decides whether an exception warrants
                a retry.  Defaults to ``is_retryable_sync_error``.
            on_retry: Optional callback invoked before each retry with
                ``(attempt, delay, exception)``.

        Returns:
            The result of a successful *operation* call.

        Raises:
            Exception: The last exception if all attempts are exhausted, or a
                non-retryable exception on the first occurrence.
        """
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation()
            except Exception as exc:
                last_exc = exc

                if not is_retryable(exc) or attempt >= self.max_retries:
                    raise

                retry_after = _extract_retry_after(exc, max_delay=self.max_delay)
                if retry_after is not None:
                    delay: float = retry_after
                else:
                    delay = min(
                        self.backoff_base * (1 << attempt),
                        self.max_delay,
                    ) * (1.0 + random.random() * self.jitter)  # noqa: S311

                if on_retry is not None:
                    on_retry(attempt, delay, exc)

                logger.debug(
                    "retrying_operation",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    delay=round(delay, 3),
                    error=str(exc),
                )

                await asyncio.sleep(delay)

        # Unreachable in practice — the loop always returns or raises.
        msg = "retry loop exited unexpectedly"
        raise RuntimeError(msg) if last_exc is None else last_exc  # pragma: no cover


class CircuitBreaker:
    """Per-server circuit breaker with three states.

    State transitions::

        CLOSED  ─(failures >= threshold)──▸  OPEN
        OPEN    ─(recovery timeout elapsed)─▸  HALF_OPEN
        HALF_OPEN ─(success)──────────────▸  CLOSED
        HALF_OPEN ─(failure)──────────────▸  OPEN

    Attributes:
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout: Time to wait before transitioning from OPEN to HALF_OPEN.
    """

    failure_threshold: int
    recovery_timeout: timedelta
    _state: str
    _consecutive_failures: int
    _opened_at: datetime | None
    _probe_sent: bool

    def __init__(
        self,
        /,
        *,
        failure_threshold: int,
        recovery_timeout_seconds: int,
    ) -> None:
        """Initialise a CircuitBreaker.

        Args:
            failure_threshold: Consecutive failures before opening the circuit.
            recovery_timeout_seconds: Seconds to wait before allowing a probe
                request (HALF_OPEN).
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self._state = "CLOSED"
        self._consecutive_failures = 0
        self._opened_at = None
        self._probe_sent = False

    @property
    def state(self) -> str:
        """Current circuit state: ``CLOSED``, ``OPEN``, or ``HALF_OPEN``."""
        return self._state

    @property
    def consecutive_failures(self) -> int:
        """Number of consecutive failures recorded."""
        return self._consecutive_failures

    @property
    def next_attempt_at(self) -> datetime | None:
        """Earliest time a request may be attempted when the circuit is OPEN."""
        if self._state == "OPEN" and self._opened_at is not None:
            return self._opened_at + self.recovery_timeout
        return None

    def should_allow(self) -> bool:
        """Return whether a request should be allowed through the circuit.

        When OPEN, the circuit transitions to HALF_OPEN once the recovery
        timeout has elapsed, allowing a single probe request.  Subsequent
        calls while still in HALF_OPEN return ``False`` until
        ``record_success`` or ``record_failure`` resets the probe gate.
        """
        if self._state == "CLOSED":
            return True

        if self._state == "HALF_OPEN":
            if self._probe_sent:
                return False
            self._probe_sent = True
            return True

        # OPEN — check if recovery timeout has elapsed.
        if self._opened_at is not None:
            if datetime.now(UTC) >= self._opened_at + self.recovery_timeout:
                self._state = "HALF_OPEN"
                self._probe_sent = True
                logger.info(
                    "circuit_half_open",
                    previous_failures=self._consecutive_failures,
                )
                return True

        return False

    def record_success(self) -> None:
        """Record a successful operation, resetting the circuit to CLOSED."""
        if self._state != "CLOSED":
            logger.info(
                "circuit_closed",
                previous_state=self._state,
                previous_failures=self._consecutive_failures,
            )
        self._state = "CLOSED"
        self._consecutive_failures = 0
        self._opened_at = None
        self._probe_sent = False

    def record_failure(self) -> None:
        """Record a failed operation, potentially opening the circuit."""
        self._consecutive_failures += 1

        if self._state == "HALF_OPEN":
            self._state = "OPEN"
            self._opened_at = datetime.now(UTC)
            self._probe_sent = False
            logger.warning(
                "circuit_opened",
                trigger="half_open_failure",
                consecutive_failures=self._consecutive_failures,
            )
            return

        if (
            self._state == "CLOSED"
            and self._consecutive_failures >= self.failure_threshold
        ):
            self._state = "OPEN"
            self._opened_at = datetime.now(UTC)
            logger.warning(
                "circuit_opened",
                trigger="threshold_reached",
                consecutive_failures=self._consecutive_failures,
                threshold=self.failure_threshold,
            )


class CircuitBreakerRegistry:
    """Container for per-server circuit breakers.

    Provides look-up, creation, removal, and manual reset of breakers
    keyed by media-server UUID.
    """

    _breakers: dict[UUID, CircuitBreaker]

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._breakers = {}

    def get_or_create(
        self,
        server_id: UUID,
        /,
        *,
        failure_threshold: int,
        recovery_timeout_seconds: int,
    ) -> CircuitBreaker:
        """Return the breaker for *server_id*, creating one if absent.

        Args:
            server_id: UUID of the media server.
            failure_threshold: Consecutive failures before opening the circuit.
            recovery_timeout_seconds: Seconds to wait before half-open probe.

        Returns:
            The ``CircuitBreaker`` instance for the given server.
        """
        if server_id not in self._breakers:
            self._breakers[server_id] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout_seconds=recovery_timeout_seconds,
            )
        return self._breakers[server_id]

    def remove(self, server_id: UUID, /) -> None:
        """Remove the breaker for *server_id* (no-op if absent).

        Args:
            server_id: UUID of the media server to remove.
        """
        _ = self._breakers.pop(server_id, None)

    def reset(self, server_id: UUID, /) -> None:
        """Manually reset the breaker for *server_id* to CLOSED.

        Args:
            server_id: UUID of the media server to reset.
        """
        breaker = self._breakers.get(server_id)
        if breaker is not None:
            breaker.record_success()
            logger.info("circuit_manually_reset", server_id=str(server_id))

    def get_state(self, server_id: UUID, /) -> tuple[str, int, datetime | None] | None:
        """Return the current state of the breaker for *server_id*.

        Args:
            server_id: UUID of the media server.

        Returns:
            A tuple of ``(state, consecutive_failures, next_attempt_at)`` or
            ``None`` if no breaker exists for the given server.
        """
        breaker = self._breakers.get(server_id)
        if breaker is None:
            return None
        return (breaker.state, breaker.consecutive_failures, breaker.next_attempt_at)
