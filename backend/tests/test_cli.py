"""The wheel's console entry point must serve through ``litestar run``.

Both checks run in a subprocess: ``zondarr.app`` builds its application at
import, which needs ``SECRET_KEY`` and configures structlog globally, and tests
must not import it.
"""

import os
import subprocess
import sys


def _run(code: str, *args: str) -> subprocess.CompletedProcess[str]:
    # Plain output whatever the caller sets: prek's --color=always passes FORCE_COLOR to hooks,
    # and Rich then styles the help text.
    forced = {"FORCE_COLOR", "CLICOLOR_FORCE", "PY_COLORS"}
    env = {
        **{k: v for k, v in os.environ.items() if k not in forced},
        "NO_COLOR": "1",
        "SECRET_KEY": "a" * 32,
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    }
    return subprocess.run(  # noqa: S603 — fixed interpreter and arguments.
        [sys.executable, "-c", code, *args],
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=120,
    )


def test_app_registers_granian_plugin() -> None:
    code = "\n".join(
        [
            "from litestar_granian import GranianPlugin",
            "from zondarr.app import app",
            "assert any(isinstance(p, GranianPlugin) for p in app.plugins)",
        ]
    )
    result = _run(code)
    assert result.returncode == 0, result.stderr


def test_cli_help() -> None:
    result = _run("from zondarr.cli import main; main()", "--help")
    assert result.returncode == 0, result.stderr
    assert "Usage: zondarr" in result.stdout
    # Only litestar-granian's `run` has this; bare granian spells it --log-level.
    assert "--granian-log-level" in result.stdout
