"""Subprocess orchestration for dev servers."""

import asyncio
import os
import signal
import sys
import webbrowser
from pathlib import Path
from typing import final

from .output import BOLD, CYAN, DIM, MAGENTA, RESET, print_error, print_info
from .pidfile import remove_pid, write_pid


@final
class ServerProcess:
    """Wraps a single child process with colored output streaming."""

    def __init__(
        self,
        *,
        name: str,
        cmd: list[str],
        cwd: Path,
        env: dict[str, str],
        color: str,
        ready_pattern: str,
        repo_root: Path,
    ) -> None:
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.color = color
        self.ready_pattern = ready_pattern
        self.repo_root = repo_root
        self.process: asyncio.subprocess.Process | None = None
        self.ready = asyncio.Event()

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *self.cmd,
            cwd=self.cwd,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=sys.platform != "win32",
        )
        assert self.process.pid is not None
        write_pid(self.repo_root, self.name, self.process.pid)
        print_info(f"Started {self.name} (pid={self.process.pid})")

    async def stream_output(
        self,
        stream: asyncio.StreamReader,
        *,
        shutdown_event: asyncio.Event,
    ) -> None:
        prefix = f"{self.color}{BOLD}{self.name:<8}{RESET}{DIM}|{RESET} "
        while not shutdown_event.is_set():
            try:
                line = await asyncio.wait_for(stream.readline(), timeout=0.5)
            except TimeoutError:
                continue
            if not line:
                break
            decoded = line.decode(errors="replace").rstrip()
            print(f"{prefix}{decoded}")
            if not self.ready.is_set() and self.ready_pattern in decoded:
                self.ready.set()

    async def stop(self) -> None:
        if self.process is None or self.process.returncode is not None:
            remove_pid(self.repo_root, self.name)
            return
        pid = self.process.pid
        assert pid is not None, "Process started but has no PID"
        print_info(f"Stopping {self.name} (pid={pid})...")

        # Signal the entire process group on Unix to catch worker processes
        if sys.platform != "win32":
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError, PermissionError:
                self.process.terminate()
        else:
            self.process.terminate()

        try:
            _ = await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except TimeoutError:
            print_error(f"{self.name} did not exit in 5s — sending SIGKILL")
            if sys.platform != "win32":
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError, PermissionError:
                    self.process.kill()
            else:
                self.process.kill()
            _ = await self.process.wait()

        remove_pid(self.repo_root, self.name)


def _backend_python(backend_dir: Path) -> str:
    """Return the backend virtualenv's interpreter.

    The server is not started through ``uv run``: uv forwards SIGTERM to its
    child, so the group-wide SIGTERM of ``dev_cli stop`` reaches ``litestar
    run`` twice, and litestar-granian answers a second signal by killing the
    workers (exit 137) instead of letting them drain. Pre-flight syncs the
    environment before the server starts (``--skip-checks`` skips that sync).
    """
    if sys.platform == "win32":
        return str(backend_dir / ".venv" / "Scripts" / "python.exe")
    return str(backend_dir / ".venv" / "bin" / "python")


@final
class DevRunner:
    """Orchestrates multiple ServerProcess instances."""

    def __init__(
        self,
        *,
        repo_root: Path,
        backend_port: int,
        frontend_port: int,
        backend_only: bool,
        frontend_only: bool,
        open_browser: bool = False,
        reload: bool = True,
        skip_auth: bool = False,
    ) -> None:
        self.repo_root = repo_root
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.backend_only = backend_only
        self.frontend_only = frontend_only
        self.open_browser = open_browser
        self.reload = reload
        self.skip_auth = skip_auth
        self.shutdown_event = asyncio.Event()
        self.servers: list[ServerProcess] = []

    def _build_servers(self) -> None:
        parent_env = dict(os.environ)
        token_file = str(self.repo_root / "backend" / "data" / ".bootstrap_token")

        if not self.frontend_only:
            backend_env = {
                **parent_env,
                "DEBUG": "true",
                "CORS_ORIGINS": f"http://localhost:{self.frontend_port}",
                "BOOTSTRAP_TOKEN_FILE": token_file,
                **({"DEV_SKIP_AUTH": "true"} if self.skip_auth else {}),
            }
            backend_cmd = [
                _backend_python(self.repo_root / "backend"),
                "-m",
                "litestar",
                "--app",
                "zondarr.app:app",
                "run",
                "--host",
                "0.0.0.0",  # noqa: S104 — existing explicit development-server listener.
                "--port",
                str(self.backend_port),
                "--backpressure",
                "16",
                "--respawn-failed-workers",
                "--workers-kill-timeout",
                "10",
                "--workers",
                "1",  # Must stay 1 for SQLite; multiple workers cause write lock contention
                "--runtime-mode",
                "st",
                "--respawn-interval",
                "30",
            ]
            if self.reload:
                data_dir = str(self.repo_root / "backend" / "data")
                db_file = str(self.repo_root / "backend" / "zondarr.db")
                db_wal = str(self.repo_root / "backend" / "zondarr.db-wal")
                db_shm = str(self.repo_root / "backend" / "zondarr.db-shm")
                backend_cmd.extend(
                    [
                        "--reload",
                        "--reload-ignore-paths",
                        token_file,
                        "--reload-ignore-paths",
                        data_dir,
                        "--reload-ignore-paths",
                        db_file,
                        "--reload-ignore-paths",
                        db_wal,
                        "--reload-ignore-paths",
                        db_shm,
                    ]
                )
            self.servers.append(
                ServerProcess(
                    name="backend",
                    cmd=backend_cmd,
                    cwd=self.repo_root / "backend",
                    env=backend_env,
                    color=CYAN,
                    ready_pattern="Listening at:",
                    repo_root=self.repo_root,
                )
            )

        if not self.backend_only:
            frontend_env = {
                **parent_env,
                "PUBLIC_API_URL": f"http://localhost:{self.backend_port}",
                "BOOTSTRAP_TOKEN_FILE": token_file,
                **({"DEV_SKIP_AUTH": "true"} if self.skip_auth else {}),
            }
            self.servers.append(
                ServerProcess(
                    name="frontend",
                    cmd=[
                        "bun",
                        "run",
                        "dev",
                        "--",
                        "--port",
                        str(self.frontend_port),
                    ],
                    cwd=self.repo_root / "frontend",
                    env=frontend_env,
                    color=MAGENTA,
                    ready_pattern="Local:",
                    repo_root=self.repo_root,
                )
            )

    _STARTUP_TIMEOUT: float = 30.0

    async def run(self) -> int:
        self._build_servers()

        if not self.servers:
            print_error("No servers to run (check --backend-only / --frontend-only)")
            return 1

        backend_python = Path(_backend_python(self.repo_root / "backend"))
        if not self.frontend_only and not backend_python.exists():
            print_error(
                f"Backend environment missing ({backend_python}): run "
                + "`uv sync --extra dev` in backend/, or start without --skip-checks"
            )
            return 1

        # Install signal handlers
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.shutdown_event.set)

        tasks: list[asyncio.Task[None]] = []

        # Separate backend and frontend servers for sequenced startup
        backend = next((s for s in self.servers if s.name == "backend"), None)
        frontend = next((s for s in self.servers if s.name == "frontend"), None)

        # Start all processes concurrently (frontend doesn't need backend at startup)
        for server in self.servers:
            await server.start()
            tasks.extend(self._stream_tasks(server))

        # Await backend ready + health check first (if present)
        if backend is not None:
            ready = await self._await_ready(backend)
            if not ready:
                self.shutdown_event.set()
                _ = await asyncio.gather(*tasks, return_exceptions=True)
                for server in self.servers:
                    await server.stop()
                return 1

            # Verify lifespans are initialized
            if frontend is not None:
                healthy = await self._verify_health(self.backend_port)
                if not healthy:
                    self.shutdown_event.set()
                    _ = await asyncio.gather(*tasks, return_exceptions=True)
                    for server in self.servers:
                        await server.stop()
                    return 1

        # Await frontend ready (likely already done since it started in parallel)
        if frontend is not None:
            ready = await self._await_ready(frontend)
            if not ready:
                self.shutdown_event.set()
                _ = await asyncio.gather(*tasks, return_exceptions=True)
                for server in self.servers:
                    await server.stop()
                return 1

        # All servers confirmed ready — open browser if requested
        if self.open_browser:
            url = (
                f"http://localhost:{self.frontend_port}"
                if frontend is not None
                else f"http://localhost:{self.backend_port}"
            )
            _ = webbrowser.open(url)

        # Watch for unexpected exits (event-driven, no polling)
        tasks.append(asyncio.create_task(self._watch_exits()))

        # Wait for shutdown signal or all streams to end
        _ = await asyncio.gather(*tasks, return_exceptions=True)

        # Stop any remaining servers
        for server in self.servers:
            await server.stop()

        return 0

    def _stream_tasks(self, server: ServerProcess) -> list[asyncio.Task[None]]:
        """Create stdout + stderr stream tasks for a server."""
        assert server.process is not None
        assert server.process.stdout is not None
        assert server.process.stderr is not None
        return [
            asyncio.create_task(
                server.stream_output(
                    server.process.stdout,
                    shutdown_event=self.shutdown_event,
                )
            ),
            asyncio.create_task(
                server.stream_output(
                    server.process.stderr,
                    shutdown_event=self.shutdown_event,
                )
            ),
        ]

    async def _await_ready(self, server: ServerProcess) -> bool:
        """Wait for a server's ready event with timeout.

        Races the ready event against process exit so an immediate crash
        (e.g. import/config error) is reported without waiting the full
        timeout.
        """
        assert server.process is not None
        ready_task = asyncio.create_task(server.ready.wait())
        exit_task = asyncio.create_task(server.process.wait())

        done, pending = await asyncio.wait(
            {ready_task, exit_task},
            timeout=self._STARTUP_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            _ = task.cancel()

        if ready_task in done:
            return True

        if exit_task in done:
            code = server.process.returncode
            print_error(f"{server.name} exited with code {code} before becoming ready")
            return False

        # Neither finished → timeout
        print_error(f"{server.name} did not start within {self._STARTUP_TIMEOUT:.0f}s")
        return False

    async def _verify_health(self, port: int) -> bool:
        """Poll GET /health/ready to confirm Litestar lifespans have initialized."""
        import http.client
        import urllib.error
        import urllib.request

        url = f"http://127.0.0.1:{port}/health/ready"
        print_info("Verifying backend health...")

        max_attempts = 15
        delay = 0.1
        for attempt in range(max_attempts):
            if self.shutdown_event.is_set():
                return False
            try:
                response: http.client.HTTPResponse = await asyncio.to_thread(  # pyright: ignore[reportAny]  # urlopen overloads lose type via to_thread
                    urllib.request.urlopen, url, timeout=2
                )
                try:
                    if response.status == 200:
                        print_info("Backend health check passed")
                        return True
                finally:
                    response.close()
            except urllib.error.URLError, OSError, TimeoutError:
                pass

            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 0.5)

        print_error(f"Backend health check failed after {max_attempts} attempts")
        return False

    async def _watch_exits(self) -> None:
        """Monitor server processes and cascade shutdown on unexpected exit."""
        process_tasks: dict[asyncio.Task[int], ServerProcess] = {}
        for server in self.servers:
            if server.process is not None:
                task = asyncio.create_task(server.process.wait())
                process_tasks[task] = server

        if not process_tasks:
            _ = await self.shutdown_event.wait()
            return

        shutdown_task = asyncio.create_task(self.shutdown_event.wait())
        pending: set[asyncio.Task[int | bool]] = {
            shutdown_task,
            *process_tasks,
        }

        try:
            while pending - {shutdown_task}:
                done, pending = await asyncio.wait(
                    pending,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if shutdown_task in done:
                    return

                for task in done:
                    if task not in process_tasks:
                        continue
                    server = process_tasks[task]
                    code = task.result()
                    if code == 0:
                        print_info(f"{server.name} exited cleanly")
                    else:
                        print_error(f"{server.name} exited with code {code}")
                    self.shutdown_event.set()
                    return
        finally:
            for task in pending:
                _ = task.cancel()
