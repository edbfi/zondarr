"""Tests for dev_cli.preflight: secret key persistence and backend dependency sync."""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dev_cli.preflight import (
    _ensure_secret_key as _ensure_secret_key,  # pyright: ignore[reportPrivateUsage]  # testing private function
)
from dev_cli.preflight import (
    _install_backend_deps as _install_backend_deps,  # pyright: ignore[reportPrivateUsage]  # testing private function
)


def test_generates_and_persists_key_when_missing() -> None:
    """First run: generates key, writes to file, sets env var."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        with patch.dict(os.environ, {}, clear=True):
            _ensure_secret_key(repo)

            key_file = repo / "backend" / "data" / ".secret_key"
            assert key_file.is_file()
            stored = key_file.read_text().strip()
            assert len(stored) > 0
            assert os.environ["SECRET_KEY"] == stored


def test_loads_persisted_key_on_subsequent_run() -> None:
    """Second run: reads existing key file instead of generating a new one."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        key_file = repo / "backend" / "data" / ".secret_key"
        key_file.parent.mkdir(parents=True)
        _ = key_file.write_text("persisted-secret-value")

        with patch.dict(os.environ, {}, clear=True):
            _ensure_secret_key(repo)
            assert os.environ["SECRET_KEY"] == "persisted-secret-value"


def test_env_var_takes_precedence() -> None:
    """If SECRET_KEY is already set in env, do not read or create file."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        with patch.dict(os.environ, {"SECRET_KEY": "from-env"}, clear=True):
            _ensure_secret_key(repo)

            key_file = repo / "backend" / "data" / ".secret_key"
            assert not key_file.exists()
            assert os.environ["SECRET_KEY"] == "from-env"


def test_creates_data_directory_if_missing() -> None:
    """backend/data/ is created automatically on first run."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        data_dir = repo / "backend" / "data"
        assert not data_dir.exists()

        with patch.dict(os.environ, {}, clear=True):
            _ensure_secret_key(repo)
            assert data_dir.is_dir()
            assert (data_dir / ".secret_key").is_file()


def test_skips_empty_key_file() -> None:
    """If key file exists but is empty, generate a new key."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        key_file = repo / "backend" / "data" / ".secret_key"
        key_file.parent.mkdir(parents=True)
        _ = key_file.write_text("")

        with patch.dict(os.environ, {}, clear=True):
            _ensure_secret_key(repo)
            stored = key_file.read_text().strip()
            assert len(stored) > 0
            assert os.environ["SECRET_KEY"] == stored


def test_key_stable_across_calls() -> None:
    """Calling _ensure_secret_key twice returns the same key."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        with patch.dict(os.environ, {}, clear=True):
            _ensure_secret_key(repo)
            first = os.environ["SECRET_KEY"]

        with patch.dict(os.environ, {}, clear=True):
            _ensure_secret_key(repo)
            second = os.environ["SECRET_KEY"]

        assert first == second


def test_backend_deps_sync_runs_even_when_venv_exists() -> None:
    """An existing .venv is still synced: the dev server no longer goes through `uv run`."""
    with tempfile.TemporaryDirectory() as tmp:
        backend = Path(tmp)
        (backend / ".venv").mkdir()
        with patch(
            "dev_cli.preflight.subprocess.run",
            return_value=SimpleNamespace(returncode=0, stderr=""),
        ) as run:
            assert _install_backend_deps(backend)

        run.assert_called_once()
        assert run.call_args.args[0] == ["uv", "sync", "--extra", "dev"]
        assert run.call_args.kwargs["cwd"] == backend
