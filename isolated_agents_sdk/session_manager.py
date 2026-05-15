"""Session Manager for the Isolated Agents SDK.

Maintains a thread-safe registry of active sessions, registers cleanup
handlers on process exit and signals, and enforces per-session timeouts.
"""

from __future__ import annotations

import asyncio
import atexit
import signal
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.models import Policy, SessionInfo, SessionMetrics


@dataclass
class _SessionEntry:
    """Internal entry combining public SessionInfo with runtime handles."""

    info: SessionInfo
    process: Optional[object]  # subprocess.Popen or asyncio.subprocess.Process
    policy: Policy


class SessionManager:
    """Thread-safe registry of active agent sessions.

    Responsibilities:
    - Track all active :class:`~isolated_agents_sdk.models.SessionInfo` objects.
    - Register ``atexit`` / ``SIGTERM`` / ``SIGINT`` handlers on first session
      creation so that all containers are destroyed when the process exits.
    - Enforce per-session timeouts via asyncio tasks.
    - Emit ``container_destroyed`` and ``resource_limit_exceeded`` audit events.

    Args:
        audit_logger: :class:`~isolated_agents_sdk.audit_logger.AuditLogger`
            instance.  A default logger (writing to stderr) is created when
            *audit_logger* is ``None``.
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None) -> None:
        self._audit_logger = audit_logger or AuditLogger()
        self._lock = threading.Lock()
        # session_id -> _SessionEntry
        self._registry: dict[str, _SessionEntry] = {}
        # Guard so atexit/signal handlers are registered only once
        self._handlers_registered: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_session(
        self,
        session_id: str,
        container_id: str,
        agent_id: str,
        process: Optional[object],
        policy: Policy,
    ) -> None:
        """Register a new session and start its timeout watcher if needed.

        Args:
            session_id: Unique identifier for this session.
            container_id: Podman container ID.
            agent_id: Identifier for the agent.
            process: The process handle for the agent process, or ``None``.
            policy: The validated :class:`~isolated_agents_sdk.models.Policy`
                for this session.
        """
        info = SessionInfo(
            session_id=session_id,
            container_id=container_id,
            agent_id=agent_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            status="running",
        )
        entry = _SessionEntry(info=info, process=process, policy=policy)

        with self._lock:
            self._registry[session_id] = entry
            if not self._handlers_registered:
                self._register_handlers()
                self._handlers_registered = True

        if policy.timeout_seconds is not None:
            self._start_timeout_watcher(session_id, policy.timeout_seconds)

        if policy.resource_monitor_interval > 0:
            self._start_resource_monitor(session_id)

    async def complete_session(self, session_id: str, exit_code: int) -> None:
        """Mark a session as completed or failed and destroy its container.

        Args:
            session_id: The session to complete.
            exit_code: The agent process exit code.  ``0`` → "completed",
                anything else → "failed".
        """
        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None:
                return
            entry.info.status = "completed" if exit_code == 0 else "failed"
            container_id = entry.info.container_id
            agent_id = entry.info.agent_id
            del self._registry[session_id]

        await self.destroy_container_async(container_id, session_id, agent_id)

    def list_sessions(self) -> list[SessionInfo]:
        """Return a snapshot of all currently active :class:`SessionInfo` objects."""
        with self._lock:
            return [entry.info for entry in self._registry.values()]

    async def exec_in_session(
        self,
        session_id: str,
        command: list[str],
    ) -> tuple[int, str, str]:
        """Execute a command inside an existing, isolated container.

        Allows iterative execution (e.g., for coding agents).

        Args:
            session_id: The active session ID.
            command: The command list to execute via ``podman exec``.

        Returns:
            A tuple of (exit_code, stdout, stderr).

        Raises:
            RuntimeError: If the session is not active.
        """
        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None or entry.info.status != "running":
                raise RuntimeError(f"Session '{session_id}' is not active.")
            container_id = entry.info.container_id

        proc = await asyncio.create_subprocess_exec(
            "podman", "exec", container_id, *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        return proc.returncode, stdout.decode(), stderr.decode()

    async def sync_artifact(
        self,
        session_id: str,
        container_path: str,
        host_path: str | Path,
    ) -> None:
        """Copy a specific file from a running agent's workspace to the host.

        Args:
            session_id: The active session ID.
            container_path: Path to the file inside the container.
            host_path: Destination path on the host.

        Raises:
            RuntimeError: If the session is not active or ``podman cp`` fails.
        """
        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None or entry.info.status != "running":
                raise RuntimeError(f"Session '{session_id}' is not active.")
            container_id = entry.info.container_id

        proc = await asyncio.create_subprocess_exec(
            "podman", "cp", f"{container_id}:{container_path}", str(host_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to sync artifact: {stderr.decode()}")

    async def get_session_metrics(self, session_id: str) -> SessionMetrics:
        """Query ``podman stats`` for the given session's container and return metrics.

        Args:
            session_id: The session to query.

        Returns:
            A :class:`SessionMetrics` with ``cpu_percent`` and ``memory_mb``.

        Raises:
            KeyError: If *session_id* is not found in the active registry.
        """
        with self._lock:
            entry = self._registry.get(session_id)
        if entry is None:
            raise KeyError(f"Session '{session_id}' not found in active registry.")

        proc = await asyncio.create_subprocess_exec(
            "podman", "stats", "--no-stream", "--format",
            "{{.CPUPerc}},{{.MemUsage}}",
            entry.info.container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        
        cpu_percent = 0.0
        memory_mb = 0.0
        if proc.returncode == 0:
            line = stdout.decode().strip()
            parts = line.split(",", 1)
            if len(parts) == 2:
                cpu_str, mem_str = parts
                try:
                    cpu_percent = float(cpu_str.strip().rstrip("%"))
                except ValueError:
                    pass
                # mem_str is like "123.4MiB / 512MiB" — take the first token
                mem_token = mem_str.strip().split()[0]
                try:
                    if mem_token.endswith("GiB"):
                        memory_mb = float(mem_token[:-3]) * 1024
                    elif mem_token.endswith("MiB"):
                        memory_mb = float(mem_token[:-3])
                    elif mem_token.endswith("KiB"):
                        memory_mb = float(mem_token[:-3]) / 1024
                    elif mem_token.endswith("kB"):
                        memory_mb = float(mem_token[:-2]) / 1024
                    else:
                        memory_mb = float(mem_token)
                except ValueError:
                    pass

        return SessionMetrics(cpu_percent=cpu_percent, memory_mb=memory_mb)

    def destroy_all(self) -> None:
        """Destroy all active containers synchronously.

        Called by ``atexit`` and signal handlers to guarantee cleanup on
        unexpected process exit.

        Signal-safety note: this method is intentionally synchronous and uses
        only ``subprocess.run`` (not asyncio) so it is safe to call from a
        signal handler, which may fire while the event loop is running.  The
        async path (``complete_session`` → ``destroy_container_async``) is
        used during normal teardown; this path is the last-resort fallback.
        """
        with self._lock:
            entries = list(self._registry.values())
            self._registry.clear()

        for entry in entries:
            self.destroy_container_sync(
                entry.info.container_id,
                entry.info.session_id,
                entry.info.agent_id,
            )

    async def destroy_container_async(
        self,
        container_id: str,
        session_id: str = "",
        agent_id: str = "",
    ) -> None:
        """Forcefully remove a Podman container asynchronously."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "rm", "-f", container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        except FileNotFoundError:
            pass

        self._audit_logger.log_event(
            event_type="container_destroyed",
            session_id=session_id,
            agent_id=agent_id,
            payload={"container_id": container_id},
        )

    def destroy_container_sync(
        self,
        container_id: str,
        session_id: str = "",
        agent_id: str = "",
    ) -> None:
        """Forcefully remove a Podman container synchronously."""
        try:
            subprocess.run(
                ["podman", "rm", "-f", container_id],
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            pass

        self._audit_logger.log_event(
            event_type="container_destroyed",
            session_id=session_id,
            agent_id=agent_id,
            payload={"container_id": container_id},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _timeout_session(self, session_id: str, timeout_seconds: int) -> None:
        """Called when a session exceeds its limit."""
        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None:
                return
            if entry.info.status != "running":
                return
            entry.info.status = "terminated"
            container_id = entry.info.container_id
            agent_id = entry.info.agent_id
            process = entry.process
            del self._registry[session_id]

        # Kill the agent process if it is still alive
        if process is not None:
            try:
                if hasattr(process, 'kill'):
                    if asyncio.iscoroutinefunction(process.kill):
                        await process.kill()
                    else:
                        process.kill()
            except Exception:
                pass

        await self.destroy_container_async(container_id, session_id, agent_id)

        self._audit_logger.log_event(
            event_type="resource_limit_exceeded",
            session_id=session_id,
            agent_id=agent_id,
            payload={
                "violation_type": "timeout",
                "attempted_action": "session_timeout",
                "reason": "timeout",
                "timeout_seconds": timeout_seconds,
            },
        )

    def _start_timeout_watcher(self, session_id: str, timeout_seconds: int) -> None:
        """Start a watcher that fires :meth:`_timeout_session` after the timeout.

        When called from within a running event loop (the normal async path),
        an asyncio task is created.  When called from the synchronous
        ``run_agent()`` path — where ``asyncio.run()`` creates a *new* loop
        that is not yet running at the point ``register_session`` is called —
        a daemon thread is used instead.  The thread creates its own event loop
        so it can drive the async ``_timeout_session`` coroutine without
        interfering with the caller's loop.
        """
        async def _watcher() -> None:
            await asyncio.sleep(timeout_seconds)
            await self._timeout_session(session_id, timeout_seconds)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_watcher())
        except RuntimeError:
            # No running event loop at call time — use a daemon thread with
            # its own isolated event loop.  We deliberately do NOT call
            # asyncio.run() on the caller's loop because that loop may not
            # exist yet (it is created by asyncio.run() in run_agent()).
            def _thread_watcher() -> None:
                import time
                time.sleep(timeout_seconds)
                # Create a fresh loop for this thread; avoids "no current
                # event loop" errors and does not touch the caller's loop.
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self._timeout_session(session_id, timeout_seconds)
                    )
                finally:
                    loop.close()

            t = threading.Thread(target=_thread_watcher, daemon=True)
            t.start()

    def _start_resource_monitor(self, session_id: str) -> None:
        """Start an asyncio task that periodically polls ``podman stats`` and
        emits ``resource_limit_exceeded`` audit events when CPU or memory
        thresholds defined in the session's Policy are breached.

        The monitor stops automatically when the session is no longer in the
        registry (i.e. after :meth:`complete_session` removes it).
        """
        async def _monitor_loop() -> None:
            with self._lock:
                entry = self._registry.get(session_id)
            if entry is None:
                return

            interval = entry.policy.resource_monitor_interval
            cpu_threshold = entry.policy.cpu_threshold_percent
            mem_limit_mb = entry.policy.memory_mb
            mem_threshold_pct = entry.policy.memory_threshold_percent

            while True:
                await asyncio.sleep(interval)

                with self._lock:
                    entry = self._registry.get(session_id)
                if entry is None or entry.info.status != "running":
                    # Session completed or was terminated — stop monitoring.
                    break

                container_id = entry.info.container_id
                agent_id = entry.info.agent_id

                try:
                    proc = await asyncio.create_subprocess_exec(
                        "podman", "stats", "--no-stream", "--format",
                        "{{.CPUPerc}},{{.MemUsage}}",
                        container_id,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, _ = await proc.communicate()
                except Exception:
                    # Podman unavailable or container gone — stop monitoring.
                    break

                if proc.returncode != 0:
                    break

                line = stdout.decode().strip()
                parts = line.split(",", 1)
                if len(parts) != 2:
                    continue

                cpu_str, mem_str = parts

                # --- CPU threshold check ---
                try:
                    cpu_pct = float(cpu_str.strip().rstrip("%"))
                except ValueError:
                    cpu_pct = 0.0

                if cpu_pct > cpu_threshold:
                    self._audit_logger.log_event(
                        event_type="resource_limit_exceeded",
                        session_id=session_id,
                        agent_id=agent_id,
                        payload={
                            "violation_type": "cpu_threshold_exceeded",
                            "attempted_action": "cpu_usage",
                            "cpu_percent": cpu_pct,
                            "cpu_threshold_percent": cpu_threshold,
                            "container_id": container_id,
                        },
                    )

                # --- Memory threshold check ---
                # mem_str is like "123.4MiB / 512MiB" — parse the used portion.
                mem_token = mem_str.strip().split()[0]
                try:
                    if mem_token.endswith("GiB"):
                        used_mb = float(mem_token[:-3]) * 1024
                    elif mem_token.endswith("MiB"):
                        used_mb = float(mem_token[:-3])
                    elif mem_token.endswith("KiB"):
                        used_mb = float(mem_token[:-3]) / 1024
                    elif mem_token.endswith("kB"):
                        used_mb = float(mem_token[:-2]) / 1024
                    else:
                        used_mb = float(mem_token)
                except ValueError:
                    used_mb = 0.0

                if mem_limit_mb > 0:
                    mem_pct = (used_mb / mem_limit_mb) * 100.0
                    if mem_pct > mem_threshold_pct:
                        self._audit_logger.log_event(
                            event_type="resource_limit_exceeded",
                            session_id=session_id,
                            agent_id=agent_id,
                            payload={
                                "violation_type": "memory_threshold_exceeded",
                                "attempted_action": "memory_allocation",
                                "memory_used_mb": round(used_mb, 2),
                                "memory_limit_mb": mem_limit_mb,
                                "memory_percent": round(mem_pct, 2),
                                "memory_threshold_percent": mem_threshold_pct,
                                "container_id": container_id,
                            },
                        )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_monitor_loop())
        except RuntimeError:
            # No running event loop — start a background thread with its own
            # isolated loop.  Same rationale as _start_timeout_watcher.
            def _thread_monitor() -> None:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(_monitor_loop())
                finally:
                    loop.close()

            t = threading.Thread(target=_thread_monitor, daemon=True)
            t.start()

    def _register_handlers(self) -> None:
        """Register ``atexit`` and signal handlers.  Must be called under ``_lock``."""
        atexit.register(self.destroy_all)

        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        def _handle_sigterm(signum: int, frame: object) -> None:
            self.destroy_all()
            # Re-raise by restoring the original handler and re-sending the signal
            if original_sigterm and callable(original_sigterm):
                signal.signal(signal.SIGTERM, original_sigterm)
            else:
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
            signal.raise_signal(signal.SIGTERM)

        def _handle_sigint(signum: int, frame: object) -> None:
            self.destroy_all()
            if original_sigint and callable(original_sigint):
                signal.signal(signal.SIGINT, original_sigint)
            else:
                signal.signal(signal.SIGINT, signal.SIG_DFL)
            signal.raise_signal(signal.SIGINT)

        signal.signal(signal.SIGTERM, _handle_sigterm)
        signal.signal(signal.SIGINT, _handle_sigint)


# ---------------------------------------------------------------------------
# IsolatedSession — async context manager for single-session lifecycle
# ---------------------------------------------------------------------------

class IsolatedSession:
    """Async context manager that owns the full lifecycle of one agent session.

    Provisions a container on entry, runs the agent, collects output, and
    guarantees container teardown on exit — even if an exception is raised.

    Usage::

        async with IsolatedSession(agent=my_fn, working_dir="/data") as session:
            result = await session.run()
            print(result.exit_code, result.artifacts)

    The context manager is a thin convenience wrapper around
    :func:`~isolated_agents_sdk.async_run_agent`.  For advanced use cases
    (daemon mode, iterative exec) use the lower-level APIs directly.

    Args:
        agent: Callable to execute inside the container.
        working_dir: Host path to the working directory.
        policy: Optional :class:`~isolated_agents_sdk.models.Policy`.
        host_output_path: Optional host directory for output artifacts.
    """

    def __init__(
        self,
        agent,
        working_dir,
        policy=None,
        host_output_path=None,
    ) -> None:
        self._agent = agent
        self._working_dir = working_dir
        self._policy = policy
        self._host_output_path = host_output_path
        self._result = None

    async def __aenter__(self) -> "IsolatedSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        # Nothing to clean up here — async_run_agent handles teardown
        # internally via SessionManager.complete_session().
        return False  # do not suppress exceptions

    async def run(self):
        """Execute the agent and return an :class:`~isolated_agents_sdk.models.AgentResult`.

        Can only be called once per context-manager instance.
        """
        # Import here to avoid circular imports (this module is imported by
        # __init__.py which also imports SessionManager).
        from isolated_agents_sdk import async_run_agent  # noqa: PLC0415

        self._result = await async_run_agent(
            agent=self._agent,
            working_dir=self._working_dir,
            policy=self._policy,
            host_output_path=self._host_output_path,
        )
        return self._result
