"""Smoke-test the production backend and frontend together over loopback HTTP.

Migrates an empty SQLite database with Alembic, starts the backend (`zondarr`,
Granian) and the built frontend through its production entry
(`bun scripts/serve.ts`) on free ports, then checks `/health/ready`,
`/api/auth/methods` directly and through the frontend's API proxy, and the
setup page. Run after `bun run --cwd frontend build`; CI runs
`uv run --locked --project backend python .github/scripts/smoke.py`.

Both ports must be free, each server must report listening on its own port
before it is asked anything, and a server that exits during startup fails the
smoke at once, so another listener on a port can never pass for it.
SMOKE_BACKEND_PORT and SMOKE_FRONTEND_PORT override the free ports (to prove
that an occupied port fails).
"""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parents[2]
BIN = Path(sys.executable).parent
STARTUP_SECONDS = 60
SHUTDOWN_SECONDS = 15
SETUP_TOKEN = "smoke-ephemeral-setup-token"  # noqa: S105 — throwaway, never a real credential.
# A developer's own server, proxy or debug settings must not leak into the smoke.
LEAKS = re.compile(
    r"^(ORIGIN|HOST|PORT|SOCKET_PATH|XFF_DEPTH|DEBUG|DEV_SKIP_AUTH|CSRF_ORIGIN"
    r"|SECURE_COOKIES|PUBLIC_API_URL|[A-Z]+_HEADER)$"
)


def port(name: str, other: int | None = None) -> int:
    """A free loopback port, or the one `name` sets, which must be free too.

    Granian binds with SO_REUSEPORT, so it would share a port with another
    SO_REUSEPORT listener instead of failing; this plain bind fails for any
    listener. Each reservation is released before the next, so `other` (the
    port already chosen for the other server) is rejected explicitly.
    """
    requested = int(os.environ.get(name) or 0)
    for _ in range(20):
        with socket.socket() as reservation:
            try:
                reservation.bind(("127.0.0.1", requested))
            except OSError as error:
                raise SystemExit(f"smoke: {name}: {error}") from None
            chosen = int(reservation.getsockname()[1])
        if chosen != other:
            return chosen
        if requested:
            raise SystemExit(f"smoke: {name}: port {chosen} is the other server's")
    raise SystemExit(f"smoke: {name}: no free port distinct from {other}")


def read(url: str) -> bytes:
    if not url.startswith("http://127.0.0.1:"):
        raise ValueError("Smoke requests must stay on loopback HTTP")
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 — loopback HTTP checked above.
        if response.status != 200:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        return response.read()


class Server:
    def __init__(
        self, name: str, command: list[str], cwd: Path, env: dict[str, str], log: Path
    ) -> None:
        self.name = name
        self.log = log
        self._output: IO[bytes] = log.open("wb")
        self.process = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=self._output, stderr=subprocess.STDOUT
        )

    def wait_listening(self, line: str) -> None:
        deadline = time.monotonic() + STARTUP_SECONDS
        while line not in self.log.read_text(errors="replace"):
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"{self.name} exited during startup with {self.process.returncode}"
                )
            if time.monotonic() >= deadline:
                raise RuntimeError(f"{self.name} did not report {line!r}")
            time.sleep(0.2)

    def wait_answer(self, url: str) -> bytes:
        """The first answer from this server once it listens (Granian logs before its worker)."""
        deadline = time.monotonic() + STARTUP_SECONDS
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(
                    f"{self.name} exited during startup with {self.process.returncode}"
                )
            try:
                return read(url)
            except urllib.error.HTTPError:
                raise  # an answer, just the wrong one
            # TimeoutError: Granian logs before its worker answers, so a request can time out.
            except ConnectionError, TimeoutError, urllib.error.URLError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)

    def stop(self) -> int | None:
        """SIGTERM and wait; `litestar run` stops Granian only on SIGTERM."""
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                _ = self.process.wait(timeout=SHUTDOWN_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()
                _ = self.process.wait()
                self._output.close()
                return None
        self._output.close()
        return self.process.returncode


def main() -> int:
    backend_port = port("SMOKE_BACKEND_PORT")
    frontend_port = port("SMOKE_FRONTEND_PORT", other=backend_port)
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    servers: list[Server] = []
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="zondarr-smoke-") as temporary:
        work = Path(temporary)
        base = {k: v for k, v in os.environ.items() if not LEAKS.match(k)}
        backend_env = base | {
            "SECRET_KEY": "smoke-ephemeral-key-never-used-in-production-123456",
            "DATABASE_URL": f"sqlite+aiosqlite:///{work}/smoke.db",
            "BOOTSTRAP_TOKEN": SETUP_TOKEN,
            "BOOTSTRAP_TOKEN_FILE": f"{work}/bootstrap-token",
            "CORS_ORIGINS": frontend_url,
            "CSRF_ORIGIN": frontend_url,
        }
        frontend_env = base | {
            "INTERNAL_API_URL": backend_url,
            "PUBLIC_API_URL": "",
            "ORIGIN": frontend_url,
            "HOST": "127.0.0.1",
            "PORT": str(frontend_port),
            "NODE_ENV": "production",
            "SHUTDOWN_TIMEOUT": "5",
        }
        try:
            migrate = subprocess.run(
                [str(BIN / "alembic"), "upgrade", "head"],
                cwd=ROOT / "backend",
                env=backend_env,
                capture_output=True,
                check=False,
            )
            if migrate.returncode != 0:
                print(migrate.stdout.decode(errors="replace"))
                print(migrate.stderr.decode(errors="replace"))
                raise RuntimeError(
                    f"alembic upgrade head exited with {migrate.returncode}"
                )
            print("ok alembic upgrade head")

            # The work directory has no .env for the Litestar CLI to load.
            backend = Server(
                "backend",
                [
                    str(BIN / "zondarr"),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(backend_port),
                ],
                work,
                backend_env,
                work / "backend.log",
            )
            servers.append(backend)
            # --no-env-file: a developer's frontend/.env must not refill the settings.
            frontend = Server(
                "frontend",
                ["bun", "--no-env-file", "scripts/serve.ts"],
                ROOT / "frontend",
                frontend_env,
                work / "frontend.log",
            )
            servers.append(frontend)
            backend.wait_listening(f"Listening at: {backend_url}")
            frontend.wait_listening(f"Listening on {frontend_url}/ for {frontend_url}")

            ready = json.loads(backend.wait_answer(backend_url + "/health/ready"))
            if ready.get("status") != "ready":
                raise RuntimeError(f"/health/ready: {ready!r}")
            print("ok backend /health/ready")
            direct = json.loads(read(backend_url + "/api/auth/methods"))
            proxied = json.loads(read(frontend_url + "/api/auth/methods"))
            if direct != proxied or proxied.get("setup_required") is not True:
                raise RuntimeError(
                    f"/api/auth/methods: {direct!r} direct, {proxied!r} proxied"
                )
            print("ok frontend proxy /api/auth/methods (setup required)")
            html = read(f"{frontend_url}/setup?token={SETUP_TOKEN}").decode()
            if "<!doctype html>" not in html.lower() or "Zondarr" not in html:
                raise RuntimeError("/setup did not render the Zondarr page")
            print("ok frontend /setup")
            if Path(backend_env["BOOTSTRAP_TOKEN_FILE"]).read_text() != SETUP_TOKEN:
                raise RuntimeError("the backend did not write the bootstrap token file")
            print("ok bootstrap token file")
        except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
            failures.append(str(error))
        finally:
            for server in reversed(servers):
                code = server.stop()
                if code != 0 and not failures:
                    failures.append(f"{server.name} did not shut down cleanly ({code})")
                elif code == 0:
                    print(f"ok {server.name} exited 0 on SIGTERM")
            if failures:
                for server in servers:
                    print(f"--- {server.name} log", file=sys.stderr)
                    print(server.log.read_text(errors="replace"), file=sys.stderr)
    if failures:
        print("\n".join(f"smoke: {failure}" for failure in failures), file=sys.stderr)
        return 1
    print("smoke: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
