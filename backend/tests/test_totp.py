"""Comprehensive tests for TOTP two-factor authentication.

Tests cover:
- TOTP encryption (Fernet+HKDF encrypt/decrypt roundtrip)
- Backup code generation, hashing, and verification
- TOTPService (setup, confirm, verify, disable, regenerate, rate limiting)
- Challenge token creation and validation
"""

import re
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pyotp
import pytest
from litestar import Litestar
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from zondarr.core.exceptions import AuthenticationError
from zondarr.models.admin import AdminAccount
from zondarr.repositories.admin import AdminAccountRepository
from zondarr.services.password import hash_password
from zondarr.services.totp import (
    BACKUP_CODE_COUNT,
    MAX_FAILED_ATTEMPTS,
    RATE_LIMIT_WINDOW_SECONDS,
    TOTP_DIGITS,
    TOTP_INTERVAL,
    TOTPService,
    generate_backup_codes,
    hash_backup_codes,
    verify_backup_code,
)
from zondarr.services.totp_encryption import (
    InvalidToken,
    decrypt_totp_secret,
    encrypt_totp_secret,
)

# Stable test secret key (>= 32 chars)
TEST_SECRET_KEY = "test-secret-key-for-totp-at-least-32-chars-long!"  # noqa: S105


# =============================================================================
# Helpers
# =============================================================================


async def _create_admin(
    session: AsyncSession,
    *,
    username: str = "admin",
    password: str = "testpassword123",  # noqa: S107
    totp_enabled: bool = False,
) -> AdminAccount:
    """Create and persist an AdminAccount for testing."""
    admin = AdminAccount(
        username=username,
        password_hash=hash_password(password),
        auth_method="local",
        enabled=True,
        totp_enabled=totp_enabled,
    )
    session.add(admin)
    await session.flush()
    return admin


def _setup_totp_for_admin(admin: AdminAccount) -> str:
    """Set up TOTP fields on admin directly (bypasses QR generation).

    Returns the raw TOTP secret for generating valid codes.
    """
    secret = pyotp.random_base32()
    admin.totp_secret_encrypted = encrypt_totp_secret(
        secret, secret_key=TEST_SECRET_KEY
    )
    backup_codes = generate_backup_codes()
    admin.totp_backup_codes = hash_backup_codes(backup_codes)
    return secret


def _get_valid_totp_code(secret: str) -> str:
    """Generate a currently-valid TOTP code from a raw secret."""
    totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
    return totp.now()


def _enable_totp_for_admin(admin: AdminAccount, secret: str) -> None:
    """Enable TOTP on an admin by confirming setup and clearing code-reuse tracking.

    This avoids code-reuse rejection when the same TOTP time-window code
    is used later in the test for verification.
    """
    totp_svc = TOTPService(secret_key=TEST_SECRET_KEY)
    code = _get_valid_totp_code(secret)
    totp_svc.confirm_setup(admin, code)  # pyright: ignore[reportUnusedCallResult]
    # Clear code-reuse tracking so the same code can be used in verification
    admin.totp_last_used_code = None
    admin.totp_last_used_at = None


# =============================================================================
# TOTP Encryption Tests
# =============================================================================


class TestTOTPEncryption:
    """Tests for Fernet+HKDF encrypt/decrypt of TOTP secrets."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encrypting then decrypting returns the original plaintext."""
        secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(secret, secret_key=TEST_SECRET_KEY)
        decrypted = decrypt_totp_secret(encrypted, secret_key=TEST_SECRET_KEY)
        assert decrypted == secret

    def test_encrypted_output_differs_from_plaintext(self) -> None:
        """The encrypted string should not contain the plaintext."""
        secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(secret, secret_key=TEST_SECRET_KEY)
        assert encrypted != secret
        assert secret not in encrypted

    def test_decrypt_with_wrong_key_raises(self) -> None:
        """Decrypting with a different secret key raises InvalidToken."""
        secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(secret, secret_key=TEST_SECRET_KEY)
        with pytest.raises(InvalidToken):
            decrypt_totp_secret(  # pyright: ignore[reportUnusedCallResult]
                encrypted,
                secret_key="a-completely-different-secret-key-32chars!",
            )

    def test_decrypt_corrupted_ciphertext_raises(self) -> None:
        """Decrypting corrupted ciphertext raises InvalidToken."""
        with pytest.raises(Exception):  # noqa: B017
            decrypt_totp_secret("not-valid-ciphertext", secret_key=TEST_SECRET_KEY)  # pyright: ignore[reportUnusedCallResult]

    def test_different_secrets_produce_different_ciphertexts(self) -> None:
        """Two different plaintexts produce different ciphertexts."""
        s1 = pyotp.random_base32()
        s2 = pyotp.random_base32()
        e1 = encrypt_totp_secret(s1, secret_key=TEST_SECRET_KEY)
        e2 = encrypt_totp_secret(s2, secret_key=TEST_SECRET_KEY)
        assert e1 != e2


# =============================================================================
# Backup Code Helper Tests
# =============================================================================


class TestBackupCodeHelpers:
    """Tests for backup code generation, hashing, and verification."""

    def test_generate_backup_codes_count(self) -> None:
        """Generates exactly BACKUP_CODE_COUNT codes."""
        codes = generate_backup_codes()
        assert len(codes) == BACKUP_CODE_COUNT

    def test_generate_backup_codes_format(self) -> None:
        """Each code matches XXXX-XXXX format (uppercase alphanumeric)."""
        codes = generate_backup_codes()
        pattern = re.compile(r"^[A-Z0-9]{4}-[A-Z0-9]{4}$")
        for code in codes:
            assert pattern.match(code), f"Code {code!r} doesn't match XXXX-XXXX format"

    def test_generate_backup_codes_unique(self) -> None:
        """All generated codes are unique."""
        codes = generate_backup_codes()
        assert len(set(codes)) == len(codes)

    def test_generate_backup_codes_sorted(self) -> None:
        """Codes are returned sorted."""
        codes = generate_backup_codes()
        assert codes == sorted(codes)

    def test_hash_and_verify_backup_code(self) -> None:
        """A valid backup code matches its hash and is consumed."""
        codes = generate_backup_codes()
        hashed_json = hash_backup_codes(codes)

        # Verify the first code
        matched, updated_json = verify_backup_code(hashed_json, codes[0])
        assert matched is True
        assert updated_json is not None

        # The used code should no longer match
        matched2, _ = verify_backup_code(updated_json, codes[0])
        assert matched2 is False

    def test_verify_backup_code_case_insensitive(self) -> None:
        """Verification is case-insensitive."""
        codes = generate_backup_codes()
        hashed_json = hash_backup_codes(codes)

        matched, _ = verify_backup_code(hashed_json, codes[0].lower())
        assert matched is True

    def test_verify_backup_code_with_whitespace(self) -> None:
        """Verification strips whitespace."""
        codes = generate_backup_codes()
        hashed_json = hash_backup_codes(codes)

        matched, _ = verify_backup_code(hashed_json, f"  {codes[0]}  ")
        assert matched is True

    def test_verify_invalid_backup_code(self) -> None:
        """An invalid code returns (False, None)."""
        codes = generate_backup_codes()
        hashed_json = hash_backup_codes(codes)

        matched, updated_json = verify_backup_code(hashed_json, "ZZZZ-ZZZZ")
        assert matched is False
        assert updated_json is None

    def test_all_backup_codes_can_be_consumed(self) -> None:
        """All backup codes can be verified and consumed one by one."""
        codes = generate_backup_codes()
        hashed_json = hash_backup_codes(codes)

        for code in codes:
            matched, hashed_json = verify_backup_code(hashed_json, code)  # type: ignore[arg-type]
            assert matched is True
            assert hashed_json is not None

        # After all consumed, nothing should match
        matched, _ = verify_backup_code(hashed_json, codes[0])
        assert matched is False


# =============================================================================
# TOTPService Tests
# =============================================================================


class TestTOTPServiceSetup:
    """Tests for TOTPService.generate_setup and confirm_setup."""

    @pytest.mark.asyncio
    async def test_generate_setup_returns_uri_qr_codes(
        self, session: AsyncSession
    ) -> None:
        """generate_setup returns a provisioning URI, QR SVG, and backup codes."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        # Mock segno QR save to avoid "currentColor" issue in test env
        fake_svg = b"<svg>mock</svg>"
        with patch("zondarr.services.totp.segno") as mock_segno:
            mock_qr = mock_segno.make.return_value  # pyright: ignore[reportAny]
            mock_qr.save.side_effect = lambda buf, **_kw: buf.write(fake_svg)  # pyright: ignore[reportAny, reportUnknownMemberType, reportUnknownLambdaType]
            uri, qr_svg, backup_codes = service.generate_setup(admin)

        assert uri.startswith("otpauth://totp/")
        assert "Zondarr" in uri
        assert admin.username in uri
        assert "svg" in qr_svg.lower()
        assert len(backup_codes) == BACKUP_CODE_COUNT
        assert admin.totp_secret_encrypted is not None
        assert admin.totp_backup_codes is not None
        assert admin.totp_enabled is False  # Not enabled until confirmed

    @pytest.mark.asyncio
    async def test_generate_setup_rejects_if_already_enabled(
        self, session: AsyncSession
    ) -> None:
        """generate_setup raises if TOTP is already enabled."""
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="already enabled"):
            service.generate_setup(admin)  # pyright: ignore[reportUnusedCallResult]

    @pytest.mark.asyncio
    async def test_confirm_setup_with_valid_code(self, session: AsyncSession) -> None:
        """confirm_setup enables TOTP when given a valid code."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        code = _get_valid_totp_code(secret)
        result = service.confirm_setup(admin, code)

        assert result is True
        assert admin.totp_enabled is True
        assert admin.totp_enabled_at is not None

    @pytest.mark.asyncio
    async def test_confirm_setup_with_invalid_code(self, session: AsyncSession) -> None:
        """confirm_setup returns False for invalid code."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        _setup_totp_for_admin(admin)  # pyright: ignore[reportUnusedCallResult]

        result = service.confirm_setup(admin, "000000")

        assert result is False
        assert admin.totp_enabled is False

    @pytest.mark.asyncio
    async def test_confirm_setup_rejects_if_already_enabled(
        self, session: AsyncSession
    ) -> None:
        """confirm_setup raises if TOTP is already enabled."""
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="already enabled"):
            service.confirm_setup(admin, "123456")  # pyright: ignore[reportUnusedCallResult]

    @pytest.mark.asyncio
    async def test_confirm_setup_rejects_if_no_pending_secret(
        self, session: AsyncSession
    ) -> None:
        """confirm_setup raises if no setup has been initiated."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="No TOTP setup"):
            service.confirm_setup(admin, "123456")  # pyright: ignore[reportUnusedCallResult]


class TestTOTPServiceVerify:
    """Tests for TOTPService.verify_code and verify_backup_code."""

    @pytest.mark.asyncio
    async def test_verify_code_with_valid_totp(self, session: AsyncSession) -> None:
        """verify_code returns True for a valid TOTP code."""
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)
        admin.totp_enabled = True  # re-set after helper

        # Verify with a valid code (no prior code used, so no replay rejection)
        fresh_code = _get_valid_totp_code(secret)
        assert service.verify_code(admin, fresh_code) is True

    @pytest.mark.asyncio
    async def test_verify_code_with_invalid_totp(self, session: AsyncSession) -> None:
        """verify_code returns False for an invalid code."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        code = _get_valid_totp_code(secret)
        service.confirm_setup(admin, code)  # pyright: ignore[reportUnusedCallResult]

        assert service.verify_code(admin, "000000") is False

    @pytest.mark.asyncio
    async def test_verify_code_raises_if_not_enabled(
        self, session: AsyncSession
    ) -> None:
        """verify_code raises AuthenticationError if TOTP not enabled."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="not enabled"):
            service.verify_code(admin, "123456")  # pyright: ignore[reportUnusedCallResult]

    @pytest.mark.asyncio
    async def test_verify_backup_code_succeeds(self, session: AsyncSession) -> None:
        """verify_backup_code returns True and consumes the code."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        # Enable TOTP
        code = _get_valid_totp_code(secret)
        service.confirm_setup(admin, code)  # pyright: ignore[reportUnusedCallResult]

        # Get backup codes by regenerating
        backup_codes = service.regenerate_backup_codes(admin)
        first_code = backup_codes[0]

        assert service.verify_backup_code(admin, first_code) is True
        # Same code should fail now (consumed)
        assert service.verify_backup_code(admin, first_code) is False

    @pytest.mark.asyncio
    async def test_verify_backup_code_raises_if_not_enabled(
        self, session: AsyncSession
    ) -> None:
        """verify_backup_code raises if TOTP is not enabled."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="not enabled"):
            service.verify_backup_code(admin, "ABCD-1234")  # pyright: ignore[reportUnusedCallResult]

    @pytest.mark.asyncio
    async def test_verify_backup_code_raises_if_no_codes(
        self, session: AsyncSession
    ) -> None:
        """verify_backup_code raises if no backup codes are stored."""
        admin = await _create_admin(session, totp_enabled=True)
        admin.totp_backup_codes = None
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="No backup codes"):
            service.verify_backup_code(admin, "ABCD-1234")  # pyright: ignore[reportUnusedCallResult]


class TestTOTPReplayProtection:
    """Tests for TOTP code replay protection in verify_code and confirm_setup."""

    @pytest.mark.asyncio
    async def test_verify_code_rejects_replayed_code(
        self, session: AsyncSession
    ) -> None:
        """verify_code rejects a code that was already used in the same window."""
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)
        admin.totp_enabled = True  # re-set after _setup_totp_for_admin

        # Pin time to 10s into the current interval so we can't cross a boundary
        fixed_time = (int(time.time()) // TOTP_INTERVAL) * TOTP_INTERVAL + 10
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        code = totp.at(fixed_time)

        with patch("zondarr.services.totp.time") as mock_time:
            mock_time.time.return_value = fixed_time  # pyright: ignore[reportAny]
            # First use succeeds
            assert service.verify_code(admin, code) is True
            # Same code in same window is rejected
            assert service.verify_code(admin, code) is False

    @pytest.mark.asyncio
    async def test_verify_code_rejects_different_code_in_same_window(
        self, session: AsyncSession
    ) -> None:
        """verify_code rejects a different valid code within the same counter window.

        Counter-based replay protection blocks ALL codes until the time
        counter advances, not just the exact code that was already used.
        This closes the gap where adjacent-window codes could be interleaved
        to replay a previously used code.
        """
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)
        admin.totp_enabled = True

        # Pin time to 10s into the current interval so we can't cross a boundary
        fixed_time = (int(time.time()) // TOTP_INTERVAL) * TOTP_INTERVAL + 10
        totp = pyotp.TOTP(secret, digits=TOTP_DIGITS, interval=TOTP_INTERVAL)
        current_code = totp.at(fixed_time)

        with patch("zondarr.services.totp.time") as mock_time:
            mock_time.time.return_value = fixed_time  # pyright: ignore[reportAny]
            assert service.verify_code(admin, current_code) is True

            # A code from the previous time step (valid with valid_window=1)
            prev_counter = int(fixed_time) // TOTP_INTERVAL - 1
            prev_code = totp.at(prev_counter * TOTP_INTERVAL)
            # Even a different valid code must be rejected in the same window
            if prev_code != current_code:
                assert service.verify_code(admin, prev_code) is False

    @pytest.mark.asyncio
    async def test_verify_code_accepts_after_counter_advances(
        self, session: AsyncSession
    ) -> None:
        """verify_code allows a code when the last-used counter is in the past."""
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)
        admin.totp_enabled = True

        code = _get_valid_totp_code(secret)

        # Simulate that a code was used 5 intervals ago
        admin.totp_last_used_at = (int(time.time()) // TOTP_INTERVAL) - 5

        # Code should be accepted since the counter has advanced
        assert service.verify_code(admin, code) is True

    @pytest.mark.asyncio
    async def test_verify_code_records_counter_not_code_string(
        self, session: AsyncSession
    ) -> None:
        """verify_code sets totp_last_used_at to the counter and clears totp_last_used_code."""
        admin = await _create_admin(session, totp_enabled=True)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)
        admin.totp_enabled = True

        code = _get_valid_totp_code(secret)
        assert admin.totp_last_used_code is None
        assert admin.totp_last_used_at is None

        fixed_time = 1700000000.0
        with patch("zondarr.services.totp.time") as mock_time:
            mock_time.time.return_value = fixed_time  # pyright: ignore[reportAny]
            service.verify_code(admin, code)  # pyright: ignore[reportUnusedCallResult]

        assert admin.totp_last_used_code is None
        assert admin.totp_last_used_at == int(fixed_time) // TOTP_INTERVAL

    @pytest.mark.asyncio
    async def test_confirm_setup_rejects_when_counter_not_advanced(
        self, session: AsyncSession
    ) -> None:
        """confirm_setup rejects any code when the counter has not advanced."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        code = _get_valid_totp_code(secret)

        # Simulate that a code was already used in the current window
        admin.totp_last_used_at = int(time.time()) // TOTP_INTERVAL

        result = service.confirm_setup(admin, code)
        assert result is False
        assert admin.totp_enabled is False

    @pytest.mark.asyncio
    async def test_confirm_setup_records_counter_not_code_string(
        self, session: AsyncSession
    ) -> None:
        """confirm_setup records the counter and clears code string on success."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        code = _get_valid_totp_code(secret)
        fixed_time = 1700000000.0
        with patch("zondarr.services.totp.time") as mock_time:
            mock_time.time.return_value = fixed_time  # pyright: ignore[reportAny]
            result = service.confirm_setup(admin, code)

        assert result is True
        assert admin.totp_last_used_code is None
        assert admin.totp_last_used_at == int(fixed_time) // TOTP_INTERVAL


class TestTOTPServiceDisable:
    """Tests for TOTPService.disable."""

    @pytest.mark.asyncio
    async def test_disable_clears_all_totp_fields(self, session: AsyncSession) -> None:
        """disable clears secret, backup codes, enabled flag, and counters."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        code = _get_valid_totp_code(secret)
        service.confirm_setup(admin, code)  # pyright: ignore[reportUnusedCallResult]
        assert admin.totp_enabled is True

        service.disable(admin)

        assert admin.totp_enabled is False
        assert admin.totp_secret_encrypted is None
        assert admin.totp_backup_codes is None
        assert admin.totp_enabled_at is None
        assert admin.totp_failed_attempts == 0
        assert admin.totp_last_failed_at is None
        assert admin.totp_last_used_code is None
        assert admin.totp_last_used_at is None
        assert admin.totp_challenge_nonce is None

    @pytest.mark.asyncio
    async def test_disable_raises_if_not_enabled(self, session: AsyncSession) -> None:
        """disable raises AuthenticationError if TOTP is not enabled."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="not enabled"):
            service.disable(admin)


class TestTOTPServiceRegenerateBackupCodes:
    """Tests for TOTPService.regenerate_backup_codes."""

    @pytest.mark.asyncio
    async def test_regenerate_returns_new_codes(self, session: AsyncSession) -> None:
        """regenerate_backup_codes returns fresh codes and updates admin."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        secret = _setup_totp_for_admin(admin)

        code = _get_valid_totp_code(secret)
        service.confirm_setup(admin, code)  # pyright: ignore[reportUnusedCallResult]

        old_backup_json = admin.totp_backup_codes
        new_codes = service.regenerate_backup_codes(admin)

        assert len(new_codes) == BACKUP_CODE_COUNT
        assert admin.totp_backup_codes != old_backup_json

        # New codes should be verifiable
        assert service.verify_backup_code(admin, new_codes[0]) is True

    @pytest.mark.asyncio
    async def test_regenerate_raises_if_not_enabled(
        self, session: AsyncSession
    ) -> None:
        """regenerate_backup_codes raises if TOTP is not enabled."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="not enabled"):
            service.regenerate_backup_codes(admin)  # pyright: ignore[reportUnusedCallResult]


class TestTOTPServiceRateLimiting:
    """Tests for rate limiting of TOTP attempts."""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_after_max_attempts(
        self, session: AsyncSession
    ) -> None:
        """check_rate_limit raises after MAX_FAILED_ATTEMPTS within window."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        # Simulate MAX_FAILED_ATTEMPTS failures.
        admin.totp_failed_attempts = MAX_FAILED_ATTEMPTS
        admin.totp_last_failed_at = datetime.now(UTC)

        with pytest.raises(AuthenticationError, match="Too many failed"):
            service.check_rate_limit(admin)

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window_expires(
        self, session: AsyncSession
    ) -> None:
        """check_rate_limit resets counter when window has elapsed."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        # Set failed attempts with expired window.
        admin.totp_failed_attempts = MAX_FAILED_ATTEMPTS
        admin.totp_last_failed_at = datetime.now(UTC) - timedelta(
            seconds=RATE_LIMIT_WINDOW_SECONDS + 1
        )

        # Should not raise, and should reset counter
        service.check_rate_limit(admin)
        assert admin.totp_failed_attempts == 0
        assert admin.totp_last_failed_at is None

    @pytest.mark.asyncio
    async def test_rate_limit_does_not_block_under_threshold(
        self, session: AsyncSession
    ) -> None:
        """check_rate_limit does not raise when under MAX_FAILED_ATTEMPTS."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        admin.totp_failed_attempts = MAX_FAILED_ATTEMPTS - 1
        admin.totp_last_failed_at = datetime.now(UTC)

        # Should not raise
        service.check_rate_limit(admin)

    @pytest.mark.asyncio
    async def test_rate_limit_survives_a_database_round_trip(
        self, session: AsyncSession
    ) -> None:
        """A recorded failure read back from the database is aware UTC.

        The column stores naive UTC; reloading must not hand check_rate_limit
        a naive value, which it could not subtract from datetime.now(UTC).
        """
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)
        for _ in range(MAX_FAILED_ATTEMPTS):
            service.record_failed_attempt(admin)
        admin_id = admin.id
        await session.commit()
        session.expire_all()

        reloaded = await session.get(AdminAccount, admin_id)
        assert reloaded is not None
        assert reloaded.totp_last_failed_at is not None
        assert reloaded.totp_last_failed_at.tzinfo is UTC
        with pytest.raises(AuthenticationError, match="Too many failed"):
            service.check_rate_limit(reloaded)

    @pytest.mark.asyncio
    async def test_record_failed_attempt_increments(
        self, session: AsyncSession
    ) -> None:
        """record_failed_attempt increments counter and sets timestamp."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        assert admin.totp_failed_attempts == 0
        service.record_failed_attempt(admin)
        assert admin.totp_failed_attempts == 1
        assert admin.totp_last_failed_at is not None

        service.record_failed_attempt(admin)
        assert admin.totp_failed_attempts == 2

    @pytest.mark.asyncio
    async def test_reset_failed_attempts_clears(self, session: AsyncSession) -> None:
        """reset_failed_attempts zeroes counter and timestamp."""
        admin = await _create_admin(session)
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        admin.totp_failed_attempts = 3
        admin.totp_last_failed_at = datetime.now(UTC)

        service.reset_failed_attempts(admin)
        assert admin.totp_failed_attempts == 0
        assert admin.totp_last_failed_at is None


class TestTOTPServiceDecryptionFailure:
    """Tests for TOTP secret decryption failure handling."""

    @pytest.mark.asyncio
    async def test_verify_code_raises_on_decryption_failure(
        self, session: AsyncSession
    ) -> None:
        """verify_code raises AuthenticationError if secret cannot be decrypted."""
        admin = await _create_admin(session, totp_enabled=True)
        admin.totp_secret_encrypted = "corrupted-ciphertext"  # noqa: S105
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="decrypt"):
            service.verify_code(admin, "123456")  # pyright: ignore[reportUnusedCallResult]

    @pytest.mark.asyncio
    async def test_verify_code_raises_when_secret_missing(
        self, session: AsyncSession
    ) -> None:
        """verify_code raises when totp_secret_encrypted is None."""
        admin = await _create_admin(session, totp_enabled=True)
        admin.totp_secret_encrypted = None
        service = TOTPService(secret_key=TEST_SECRET_KEY)

        with pytest.raises(AuthenticationError, match="not enabled"):
            service.verify_code(admin, "123456")  # pyright: ignore[reportUnusedCallResult]


# =============================================================================
# Challenge Token Tests
# =============================================================================


class TestChallengeToken:
    """Tests for challenge token creation and validation."""

    def test_create_and_validate_roundtrip(self) -> None:
        """A freshly created challenge token validates successfully."""
        from zondarr.api.totp import create_challenge_token, validate_challenge_token

        admin_id = uuid4()
        nonce = "test-nonce-abc123"
        token = create_challenge_token(str(admin_id), TEST_SECRET_KEY, nonce)
        result_id, result_nonce = validate_challenge_token(token, TEST_SECRET_KEY)
        assert result_id == admin_id
        assert result_nonce == nonce

    def test_validate_with_wrong_key_raises(self) -> None:
        """Validation fails with a different secret key."""
        from zondarr.api.totp import create_challenge_token, validate_challenge_token

        admin_id = uuid4()
        token = create_challenge_token(str(admin_id), TEST_SECRET_KEY, "nonce")
        with pytest.raises(AuthenticationError, match="Invalid challenge token"):
            validate_challenge_token(token, "different-secret-key-also-32-chars-long!!")  # pyright: ignore[reportUnusedCallResult]

    def test_validate_expired_token_raises(self) -> None:
        """An expired challenge token raises AuthenticationError."""
        import jwt as pyjwt

        from zondarr.api.totp import validate_challenge_token

        admin_id = uuid4()
        # Encode a JWT with an already-expired exp (bypass Litestar Token validation)
        payload = {
            "sub": str(admin_id),
            "exp": (datetime.now(UTC) - timedelta(minutes=1)).timestamp(),
            "iss": "zondarr",
            "purpose": "totp_challenge",
            "nonce": "test-nonce",
        }
        encoded = pyjwt.encode(payload, TEST_SECRET_KEY, algorithm="HS256")

        with pytest.raises(AuthenticationError):
            validate_challenge_token(encoded, TEST_SECRET_KEY)  # pyright: ignore[reportUnusedCallResult]

    def test_validate_wrong_purpose_raises(self) -> None:
        """A token with wrong purpose claim raises AuthenticationError."""
        from litestar.security.jwt import Token

        from zondarr.api.totp import validate_challenge_token

        admin_id = uuid4()
        token = Token(
            sub=str(admin_id),
            exp=datetime.now(UTC) + timedelta(minutes=5),
            iss="zondarr",
            extras={"purpose": "not_totp", "nonce": "test"},
        )
        encoded = token.encode(secret=TEST_SECRET_KEY, algorithm="HS256")

        with pytest.raises(AuthenticationError, match="purpose"):
            validate_challenge_token(encoded, TEST_SECRET_KEY)  # pyright: ignore[reportUnusedCallResult]

    def test_validate_garbage_token_raises(self) -> None:
        """A completely invalid token string raises AuthenticationError."""
        from zondarr.api.totp import validate_challenge_token

        with pytest.raises(AuthenticationError, match="Invalid challenge token"):
            validate_challenge_token("not.a.jwt", TEST_SECRET_KEY)  # pyright: ignore[reportUnusedCallResult]

    def test_validate_token_without_purpose_raises(self) -> None:
        """A token missing the purpose extra raises AuthenticationError."""
        from litestar.security.jwt import Token

        from zondarr.api.totp import validate_challenge_token

        admin_id = uuid4()
        token = Token(
            sub=str(admin_id),
            exp=datetime.now(UTC) + timedelta(minutes=5),
            iss="zondarr",
            extras={},
        )
        encoded = token.encode(secret=TEST_SECRET_KEY, algorithm="HS256")

        with pytest.raises(AuthenticationError, match="purpose"):
            validate_challenge_token(encoded, TEST_SECRET_KEY)  # pyright: ignore[reportUnusedCallResult]

    def test_validate_token_without_nonce_raises(self) -> None:
        """A token missing the nonce extra raises AuthenticationError."""
        from litestar.security.jwt import Token

        from zondarr.api.totp import validate_challenge_token

        admin_id = uuid4()
        token = Token(
            sub=str(admin_id),
            exp=datetime.now(UTC) + timedelta(minutes=5),
            iss="zondarr",
            extras={"purpose": "totp_challenge"},
        )
        encoded = token.encode(secret=TEST_SECRET_KEY, algorithm="HS256")

        with pytest.raises(AuthenticationError, match="nonce"):
            validate_challenge_token(encoded, TEST_SECRET_KEY)  # pyright: ignore[reportUnusedCallResult]


# =============================================================================
# External Login TOTP Enforcement Tests
# =============================================================================


def _make_external_login_app(
    session_factory: async_sessionmaker[AsyncSession],
) -> Litestar:
    """Create a minimal Litestar app with AuthController for testing."""
    from collections.abc import AsyncGenerator

    from litestar import Litestar
    from litestar.datastructures import State
    from litestar.di import Provide

    from zondarr.api.auth import AuthController
    from zondarr.api.errors import authentication_error_handler
    from zondarr.api.totp import TOTPController
    from zondarr.config import Settings

    settings = Settings(secret_key=TEST_SECRET_KEY)

    async def provide_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def provide_settings(state: State) -> Settings:
        return state.settings  # pyright: ignore[reportAny]

    return Litestar(
        route_handlers=[AuthController, TOTPController],
        state=State({"settings": settings}),
        dependencies={
            "session": Provide(provide_session),
            "settings": Provide(provide_settings, sync_to_thread=False),
        },
        exception_handlers={
            AuthenticationError: authentication_error_handler,
        },
    )


class TestExternalLoginTOTPEnforcement:
    """Tests for TOTP enforcement in the external login endpoint.

    The login_external() controller method must check admin.totp_enabled
    after authenticate_external() succeeds. When TOTP is enabled, it
    returns a challenge token instead of issuing access cookies.
    """

    @pytest.mark.asyncio
    async def test_external_login_totp_enabled_returns_challenge(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """External login with TOTP enabled returns totp_required + challenge_token."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="extadmin")
            secret = _setup_totp_for_admin(admin)
            _enable_totp_for_admin(admin, secret)
            assert admin.totp_enabled is True
            await session.commit()

        app = _make_external_login_app(session_factory)

        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        assert resp.status_code == 200
        data: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
        assert data["totp_required"] is True
        assert data["challenge_token"] is not None
        # No refresh token or access cookie should be issued before TOTP verification
        assert "refresh_token" not in data
        assert "zondarr_access_token" not in resp.cookies

    @pytest.mark.asyncio
    async def test_external_login_totp_disabled_returns_tokens(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """External login without TOTP returns success + access cookie."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="extadmin2")
            assert admin.totp_enabled is False
            await session.commit()

        app = _make_external_login_app(session_factory)

        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        assert resp.status_code == 200
        data: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
        assert data.get("totp_required") is not True
        # Access cookie should be set
        assert "zondarr_access_token" in resp.cookies

    @pytest.mark.asyncio
    async def test_external_login_challenge_token_completes_via_totp_verify(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Challenge token from external login can be used with /api/auth/totp/verify."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="extadmin3")
            secret = _setup_totp_for_admin(admin)
            _enable_totp_for_admin(admin, secret)
            assert admin.totp_enabled is True
            await session.commit()

        app = _make_external_login_app(session_factory)

        # Step 1: External login returns challenge token
        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        assert resp.status_code == 200
        data: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
        assert data["totp_required"] is True
        challenge_token = data["challenge_token"]
        assert isinstance(challenge_token, str)

        # Step 2: Complete login via the actual TOTP verify endpoint
        totp_code = _get_valid_totp_code(secret)
        with TestClient(app) as client:
            verify_resp = client.post(
                "/api/auth/totp/verify",
                json={
                    "challenge_token": challenge_token,
                    "code": totp_code,
                },
            )

        assert verify_resp.status_code == 200
        verify_data: dict[str, object] = verify_resp.json()  # pyright: ignore[reportAny]
        assert verify_data.get("success") is True
        assert "zondarr_access_token" in verify_resp.cookies


# =============================================================================
# Challenge Token Nonce Enforcement Tests
# =============================================================================


class TestChallengeTokenNonceEnforcement:
    """Tests for single-use nonce enforcement on challenge tokens.

    Ensures that challenge tokens can only be consumed once, preventing
    replay attacks where an attacker reuses a captured challenge token.
    """

    @pytest.mark.asyncio
    async def test_totp_verify_clears_nonce_on_success(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Successful TOTP verification clears the challenge nonce."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="nonce_clear")
            secret = _setup_totp_for_admin(admin)
            _enable_totp_for_admin(admin, secret)
            assert admin.totp_enabled is True
            await session.commit()

        app = _make_external_login_app(session_factory)

        # Step 1: Login to get challenge token (sets nonce on admin)
        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        data: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
        challenge_token = data["challenge_token"]
        assert isinstance(challenge_token, str)

        # Step 2: Verify TOTP (should succeed and clear nonce)
        totp_code = _get_valid_totp_code(secret)
        with TestClient(app) as client:
            verify_resp = client.post(
                "/api/auth/totp/verify",
                json={"challenge_token": challenge_token, "code": totp_code},
            )

        assert verify_resp.status_code == 200

        # Verify nonce was cleared in DB
        async with session_factory() as session:
            admin_repo = AdminAccountRepository(session)
            refreshed_admin = await admin_repo.get_by_id(admin.id)
            assert refreshed_admin is not None
            assert refreshed_admin.totp_challenge_nonce is None

    @pytest.mark.asyncio
    async def test_totp_verify_rejects_replayed_challenge_token(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Second use of the same challenge token is rejected."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="nonce_replay")
            secret = _setup_totp_for_admin(admin)
            _enable_totp_for_admin(admin, secret)
            assert admin.totp_enabled is True
            await session.commit()

        app = _make_external_login_app(session_factory)

        # Step 1: Login to get challenge token
        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        data: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
        challenge_token = data["challenge_token"]
        assert isinstance(challenge_token, str)

        # Step 2: First verification succeeds
        totp_code = _get_valid_totp_code(secret)
        with TestClient(app) as client:
            verify_resp = client.post(
                "/api/auth/totp/verify",
                json={"challenge_token": challenge_token, "code": totp_code},
            )
        assert verify_resp.status_code == 200

        # Step 3: Replay the same challenge token — must be rejected
        fresh_code = _get_valid_totp_code(secret)
        with TestClient(app) as client:
            replay_resp = client.post(
                "/api/auth/totp/verify",
                json={"challenge_token": challenge_token, "code": fresh_code},
            )
        assert replay_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_backup_code_verify_rejects_replayed_challenge_token(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Second use of challenge token via backup code endpoint is rejected."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="nonce_backup_replay")
            secret = _setup_totp_for_admin(admin)
            _enable_totp_for_admin(admin, secret)
            assert admin.totp_enabled is True
            totp_svc = TOTPService(secret_key=TEST_SECRET_KEY)
            backup_codes = totp_svc.regenerate_backup_codes(admin)
            await session.commit()

        app = _make_external_login_app(session_factory)

        # Step 1: Login to get challenge token
        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        data: dict[str, object] = resp.json()  # pyright: ignore[reportAny]
        challenge_token = data["challenge_token"]
        assert isinstance(challenge_token, str)

        # Step 2: First verification with backup code succeeds
        with TestClient(app) as client:
            verify_resp = client.post(
                "/api/auth/totp/backup-code",
                json={"challenge_token": challenge_token, "code": backup_codes[0]},
            )
        assert verify_resp.status_code == 200

        # Step 3: Replay the same challenge token — must be rejected
        with TestClient(app) as client:
            replay_resp = client.post(
                "/api/auth/totp/backup-code",
                json={"challenge_token": challenge_token, "code": backup_codes[1]},
            )
        assert replay_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_new_login_generates_fresh_nonce(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Each login generates a new nonce, invalidating previous challenge tokens."""
        from litestar.testing import TestClient

        async with session_factory() as session:
            admin = await _create_admin(session, username="nonce_fresh")
            secret = _setup_totp_for_admin(admin)
            _enable_totp_for_admin(admin, secret)
            assert admin.totp_enabled is True
            await session.commit()

        app = _make_external_login_app(session_factory)

        # Step 1: First login — get challenge token #1
        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp1 = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        data1: dict[str, object] = resp1.json()  # pyright: ignore[reportAny]
        challenge_token_1 = data1["challenge_token"]

        # Step 2: Second login — get challenge token #2 (overwrites nonce)
        with (
            patch(
                "zondarr.services.auth.AuthService.authenticate_external",
                return_value=admin,
            ),
            TestClient(app) as client,
        ):
            resp2 = client.post(
                "/api/auth/login/plex",
                json={"credentials": {"token": "fake"}},
            )

        data2: dict[str, object] = resp2.json()  # pyright: ignore[reportAny]
        challenge_token_2 = data2["challenge_token"]

        # Step 3: Challenge token #1 should be rejected (nonce was overwritten)
        totp_code = _get_valid_totp_code(secret)
        with TestClient(app) as client:
            stale_resp = client.post(
                "/api/auth/totp/verify",
                json={"challenge_token": challenge_token_1, "code": totp_code},
            )
        assert stale_resp.status_code == 401

        # Step 4: Challenge token #2 should work
        fresh_code = _get_valid_totp_code(secret)
        with TestClient(app) as client:
            fresh_resp = client.post(
                "/api/auth/totp/verify",
                json={"challenge_token": challenge_token_2, "code": fresh_code},
            )
        assert fresh_resp.status_code == 200
