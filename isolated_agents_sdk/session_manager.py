"""Session Manager for the Isolated Agents SDK.

Maintains a thread-safe registry of active sessions, registers cleanup
handlers on process exit and signals, and enforces per-session timeouts.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import signal
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
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
        adapter: ContainerRuntimeAdapter instance (defaults to PodmanAdapter).
        audit_logger: :class:`~isolated_agents_sdk.audit_logger.AuditLogger`
            instance.
    """

    def __init__(
        self,
        adapter: Optional[ContainerRuntimeAdapter] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._adapter = adapter or PodmanAdapter()
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
        """Register a new session and start its timeout watcher if needed."""
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
        """Mark a session as completed or failed and destroy its container."""
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
        """Execute a command inside an existing, isolated container."""
        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None or entry.info.status != "running":
                raise RuntimeError(f"Session '{session_id}' is not active.")
            container_id = entry.info.container_id

        result = await self._adapter.exec_in_container(
            container_id=container_id,
            command=command,
            working_dir="/workspace",
        )

        return result.exit_code, result.stdout, result.stderr

    async def sync_artifact(
        self,
        session_id: str,
        container_path: str,
        host_path: str | Path,
    ) -> None:
        """Copy a specific file from a running agent's workspace to the host."""
        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None or entry.info.status != "running":
                raise RuntimeError(f"Session '{session_id}' is not active.")
            container_id = entry.info.container_id

        await self._adapter.copy_from_container(container_id, container_path, str(host_path))

    async def get_session_metrics(self, session_id: str) -> SessionMetrics:
        """Query metrics for the given session's container."""
        with self._lock:
            entry = self._registry.get(session_id)
        if entry is None:
            raise KeyError(f"Session '{session_id}' not found in active registry.")

        try:
            stats = await self._adapter.get_container_stats(entry.info.container_id)
            return SessionMetrics(
                cpu_percent=stats.cpu_percent,
                memory_mb=stats.memory_mb,
            )
        except Exception:
            return SessionMetrics(cpu_percent=0.0, memory_mb=0.0)

    def destroy_all(self) -> None:
        """Destroy all active containers synchronously."""
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
        """Forcefully remove a container asynchronously."""
        try:
            await self._adapter.destroy_container(container_id, force=True)
        except Exception:
            pass

        self._audit_logger.log_event(
            event_type="container_destroyed",
            session_id=session_id,
            agent_id=agent_id,
            payload={"container_id": container_id, "adapter": self._adapter.get_adapter_name()},
        )

    def destroy_container_sync(
        self,
        container_id: str,
        session_id: str = "",
        agent_id: str = "",
    ) -> None:
        """Forcefully remove a container synchronously (atexit fallback)."""
        # For atexit, we fall back to manual podman rm -f if the adapter is PodmanAdapter
        # and doesn't provide a sync method.
        if isinstance(self._adapter, PodmanAdapter):
            try:
                subprocess.run(
                    ["podman", "rm", "-f", container_id],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass
        else:
            # For other adapters, we might not be able to clean up synchronously easily
            # unless we add a destroy_container_sync to the interface.
            logger.warning(
                "Synchronous cleanup not implemented for adapter %s",
                self._adapter.get_adapter_name()
            )

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
        """Start a watcher that fires :meth:`_timeout_session` after the timeout."""
        async def _watcher() -> None:
            await asyncio.sleep(timeout_seconds)
            await self._timeout_session(session_id, timeout_seconds)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_watcher())
        except RuntimeError:
            def _thread_watcher() -> None:
                import time
                time.sleep(timeout_seconds)
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
        """Start an asyncio task that periodically polls adapter stats."""
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
                    break

                container_id = entry.info.container_id
                agent_id = entry.info.agent_id

                try:
                    stats = await self._adapter.get_container_stats(container_id)
                except Exception:
                    break

                # --- CPU threshold check ---
                if stats.cpu_percent > cpu_threshold:
                    self._audit_logger.log_event(
                        event_type="resource_limit_exceeded",
                        session_id=session_id,
                        agent_id=agent_id,
                        payload={
                            "violation_type": "cpu_threshold_exceeded",
                            "attempted_action": "cpu_usage",
                            "cpu_percent": stats.cpu_percent,
                            "cpu_threshold_percent": cpu_threshold,
                            "container_id": container_id,
                        },
                    )

                # --- Memory threshold check ---
                if mem_limit_mb > 0:
                    mem_pct = (stats.memory_mb / mem_limit_mb) * 100.0
                    if mem_pct > mem_threshold_pct:
                        self._audit_logger.log_event(
                            event_type="resource_limit_exceeded",
                            session_id=session_id,
                            agent_id=agent_id,
                            payload={
                                "violation_type": "memory_threshold_exceeded",
                                "attempted_action": "memory_allocation",
                                "memory_used_mb": round(stats.memory_mb, 2),
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
    """Async context manager that owns the full lifecycle of one agent session."""

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
        return False

    async def run(self):
        """Execute the agent and return an :class:`~isolated_agents_sdk.models.AgentResult`."""
        from isolated_agents_sdk import async_run_agent  # noqa: PLC0415

        self._result = await async_run_agent(
            agent=self._agent,
            working_dir=self._working_dir,
            policy=self._policy,
            host_output_path=self._host_output_path,
        )
        return self._result
