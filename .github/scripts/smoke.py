"""Exercise migrated Granian and built Bun servers together over loopback HTTP."""

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[2]


def port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return int(reservation.getsockname()[1])


def read(url: str) -> bytes:
    if not url.startswith("http://127.0.0.1:"):
        raise ValueError("Smoke requests must stay on loopback HTTP")
    with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 — loopback HTTP checked above.
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP status: {response.status}")
        return response.read()


with tempfile.TemporaryDirectory(prefix="zondarr-smoke-") as temporary:
    backend_port, frontend_port = port(), port()
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    env = dict(os.environ)
    env.update(
        SECRET_KEY="ci-ephemeral-smoke-key-never-used-in-production-123456",
        DATABASE_URL=f"sqlite+aiosqlite:///{temporary}/smoke.db",
        BOOTSTRAP_TOKEN="ci-ephemeral-setup-token",
        BOOTSTRAP_TOKEN_FILE=f"{temporary}/bootstrap-token",
        INTERNAL_API_URL=backend_url,
        PUBLIC_API_URL="",
        CORS_ORIGINS=frontend_url,
        ORIGIN=frontend_url,
        HOST="127.0.0.1",
        PORT=str(frontend_port),
        NODE_ENV="production",
    )
    processes: list[subprocess.Popen[bytes]] = []
    with tempfile.TemporaryFile() as log:
        try:
            subprocess.run(
                [str(root / "backend/.venv/bin/alembic"), "upgrade", "head"],
                cwd=root / "backend",
                env=env,
                check=True,
                stdout=log,
                stderr=log,
            )
            processes.append(
                subprocess.Popen(
                    [
                        str(root / "backend/.venv/bin/zondarr"),
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(backend_port),
                    ],
                    cwd=root,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
            )
            processes.append(
                subprocess.Popen(
                    ["bun", "./build/index.js"],
                    cwd=root / "frontend",
                    env=env,
                    stdout=log,
                    stderr=log,
                )
            )
            for url in [
                backend_url + "/health/ready",
                frontend_url + "/api/auth/methods",
            ]:
                deadline = time.monotonic() + 30
                while True:
                    if any(process.poll() is not None for process in processes):
                        raise RuntimeError("A production server exited during startup")
                    try:
                        read(url)
                        break
                    except OSError, urllib.error.URLError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.2)
            assert json.loads(read(backend_url + "/health/ready"))["status"] == "ready"
            direct = json.loads(read(backend_url + "/api/auth/methods"))
            proxied = json.loads(read(frontend_url + "/api/auth/methods"))
            assert direct == proxied and proxied["setup_required"] is True
            html = read(frontend_url + "/setup?token=ci-ephemeral-setup-token").decode()
            assert "<!doctype html>" in html.lower() and "Zondarr" in html
            assert (
                Path(env["BOOTSTRAP_TOKEN_FILE"]).read_text() == env["BOOTSTRAP_TOKEN"]
            )
            subprocess.run(
                ["bun", "run", "--cwd", "frontend", "smoke:browser"],
                cwd=root,
                env={**env, "SMOKE_URL": frontend_url},
                check=True,
                timeout=90,
                stdout=log,
                stderr=log,
            )
            print(
                "Chromium hydration/validation, migrated backend readiness, frontend API proxy, setup SSR and bootstrap token passed."
            )
        except BaseException:
            log.seek(0)
            print(log.read().decode(errors="replace"))
            raise
        finally:
            shutdown_failed = False
            for process in reversed(processes):
                process.terminate()
                try:
                    if process.wait(timeout=10) != 0:
                        shutdown_failed = True
                except subprocess.TimeoutExpired:
                    shutdown_failed = True
                    process.kill()
                    process.wait()
            if shutdown_failed:
                raise RuntimeError("A production server failed to shut down cleanly")
