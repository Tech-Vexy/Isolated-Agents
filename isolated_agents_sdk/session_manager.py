"""Session Manager for the Isolated Agents SDK.

Maintains a thread-safe registry of active sessions, registers cleanup
handlers on process exit and signals, and enforces per-session timeouts.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import logging
import signal
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.logging import get_logger
from isolated_agents_sdk.models import Policy, SessionInfo, SessionMetrics, SubSessionInfo

logger = get_logger("session_manager")

# Detect if adapters are available
try:
    from isolated_agents_sdk.adapters.registry import get_adapter_registry

    _ADAPTERS_AVAILABLE = True
except ImportError:
    _ADAPTERS_AVAILABLE = False


@dataclass
class _SessionEntry:
    """Internal entry combining public SessionInfo with runtime handles."""

    info: SessionInfo
    process: object | None  # subprocess.Popen or asyncio.subprocess.Process
    policy: Policy
    audit_logger: AuditLogger | None = None
    last_resource_poll: datetime | None = None
    parent_session_id: str | None = None

    # Resource Tracking (v0.2.1)
    # The allocated resources for this session's own container
    allocated_cpu: float = 0.0
    allocated_memory: int = 0
    # The resource budget for the entire subtree (including this agent and its sub-agents)
    subtree_cpu_budget: float = 0.0
    subtree_memory_budget: int = 0
    # Currently consumed by children
    consumed_cpu_by_children: float = 0.0
    consumed_memory_by_children: int = 0


class SessionManager:
    """Thread-safe registry of active agent sessions.

    Responsibilities:
    - Track all active :class:`~isolated_agents_sdk.models.SessionInfo` objects.
    - Register cleanup handlers (atexit/signals) to destroy containers on exit.
    - Consolidate background monitoring (timeouts, resources) into a single Reaper task.
    """

    def __init__(
        self,
        adapter: ContainerRuntimeAdapter | None = None,
        audit_logger: AuditLogger | None = None,
        state_dir: Path | None = None,
    ) -> None:
        if adapter:
            self._adapter = adapter
        elif _ADAPTERS_AVAILABLE:
            self._adapter = get_adapter_registry().get_container_adapter()
        else:
            from isolated_agents_sdk.adapters.container.podman import PodmanAdapter

            self._adapter = PodmanAdapter()

        self._audit_logger = audit_logger or AuditLogger()
        self.state_dir = state_dir
        if self.state_dir:
            self.state_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        # session_id -> _SessionEntry
        self._registry: dict[str, _SessionEntry] = {}
        # Guard so atexit/signal handlers are registered only once
        self._handlers_registered: bool = False
        self._reaper_task: asyncio.Task | None = None

        # Load existing durable sessions if state_dir is provided
        if self.state_dir:
            self._load_durable_sessions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_session(
        self,
        session_id: str,
        container_id: str,
        agent_id: str,
        process: object | None,
        policy: Policy,
        audit_logger: AuditLogger | None = None,
        parent_session_id: str | None = None,
    ) -> None:
        """Register a new active session and start background monitoring tasks.

        Args:
            session_id: Unique identifier for the session.
            container_id: ID of the container being used.
            agent_id: ID of the agent being run.
            process: Optional process handle (if applicable).
            policy: The :class:`Policy` governing this session.
            audit_logger: Optional override for the audit logger.
            parent_session_id: Optional ID of the parent agent (for resource tracking).
        """
        info = SessionInfo(
            session_id=session_id,
            container_id=container_id,
            agent_id=agent_id,
            started_at=datetime.now(UTC).isoformat(),
            status="running",
        )
        entry = _SessionEntry(
            info=info,
            process=process,
            policy=policy,
            audit_logger=audit_logger,
            parent_session_id=parent_session_id,
            allocated_cpu=policy.cpu_cores,
            allocated_memory=policy.memory_mb,
            subtree_cpu_budget=policy.cpu_cores,
            subtree_memory_budget=policy.memory_mb,
        )

        with self._lock:
            if parent_session_id in self._registry:
                parent = self._registry[parent_session_id]
                # Registering a child: update parent's sub_sessions list
                parent.info.sub_sessions.append(
                    SubSessionInfo(
                        sub_session_id=session_id,
                        parent_session_id=parent_session_id,
                        container_id=container_id,
                        agent_id=agent_id,
                        started_at=info.started_at,
                        status="running",
                        nesting_depth=getattr(parent.info, "nesting_depth", 0) + 1,
                    )
                )
                # Update resource tracking in parent
                parent.consumed_cpu_by_children += entry.allocated_cpu
                parent.consumed_memory_by_children += entry.allocated_memory

            self._registry[session_id] = entry
            if not self._handlers_registered:
                self._register_handlers()
                self._handlers_registered = True

            if policy.durable and self.state_dir:
                self._save_session_state(session_id)

        # Start the Reaper task if not already running
        try:
            loop = asyncio.get_running_loop()
            if self._reaper_task is None or self._reaper_task.done():
                self._reaper_task = loop.create_task(self._session_reaper_loop())
        except RuntimeError:
            # Sync context caller; Reaper will start upon the first async call.
            pass

    def get_remaining_budget(self, session_id: str) -> dict[str, float]:
        """Calculate the remaining resource budget for a session's subtree (v0.2.1)."""
        with self._lock:
            entry = self._registry.get(session_id)
            if not entry:
                return {"cpu": 0.0, "memory": 0}

            return {
                "cpu": max(
                    0.0,
                    entry.subtree_cpu_budget - entry.allocated_cpu - entry.consumed_cpu_by_children,
                ),
                "memory": max(
                    0,
                    entry.subtree_memory_budget
                    - entry.allocated_memory
                    - entry.consumed_memory_by_children,
                ),
            }

    def _save_session_state(self, session_id: str) -> None:
        """Persist session metadata to disk for durable execution."""
        if not self.state_dir:
            return

        entry = self._registry.get(session_id)
        if not entry:
            return

        state_file = self.state_dir / f"{session_id}.json"

        # Determine how to serialise info (Pydantic vs Dataclass)
        if hasattr(entry.info, "model_dump"):
            info_dict = entry.info.model_dump()
        else:
            from dataclasses import asdict

            info_dict = asdict(entry.info)

        state = {
            "info": info_dict,
            "policy": entry.policy._to_dict(),
        }

        try:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session state for {session_id}: {e}")

    def _load_durable_sessions(self) -> None:
        """Reload sessions marked as durable from the state directory."""
        if not self.state_dir:
            return

        for state_file in self.state_dir.glob("*.json"):
            try:
                with open(state_file) as f:
                    state = json.load(f)

                # Reconstruct SessionInfo and Policy
                info_data = state["info"]

                # Use model_validate for Pydantic or direct construction for dataclasses
                if hasattr(SessionInfo, "model_validate"):
                    info = SessionInfo.model_validate(info_data)
                else:
                    # Legacy fallback
                    if "sub_sessions" in info_data:
                        info_data["sub_sessions"] = [
                            SubSessionInfo(**s) for s in info_data["sub_sessions"]
                        ]
                    info = SessionInfo(**info_data)

                policy = Policy._from_dict(state["policy"])

                # Note: Process handle is lost on restart, but container might still be running.
                # In v0.2.0, we mark it as 'stale' or try to re-attach if possible.
                # For now, we load it into the registry.
                entry = _SessionEntry(info=info, process=None, policy=policy)
                self._registry[info.session_id] = entry

                logger.info(f"Recovered durable session: {info.session_id}")
            except Exception as e:
                logger.error(f"Failed to load session state from {state_file}: {e}")

    async def complete_session(
        self, session_id: str, exit_code: int, error: str | None = None
    ) -> None:
        """Mark a session as completed or failed and destroy its container."""

        # 1. Implementation cascading teardown (v0.2.1 Hardening)
        # Find all children in the registry that claim this session as parent
        # and terminate them recursively to avoid orphan containers.
        children_to_kill = []
        with self._lock:
            for sid, entry_other in self._registry.items():
                if entry_other.parent_session_id == session_id:
                    children_to_kill.append(sid)

        for child_sid in children_to_kill:
            await self.complete_session(
                child_sid,
                exit_code=1,
                error=f"Teardown triggered by parent session {session_id} termination.",
            )

        with self._lock:
            entry = self._registry.get(session_id)
            if entry is None:
                return
            entry.info.status = "completed" if exit_code == 0 else "failed"
            entry.info.error = error
            container_id = entry.info.container_id
            agent_id = entry.info.agent_id
            audit_logger = entry.audit_logger or self._audit_logger
            del self._registry[session_id]

            # Remove persistent state if it exists
            if self.state_dir:
                state_file = self.state_dir / f"{session_id}.json"
                if state_file.exists():
                    with contextlib.suppress(OSError):
                        state_file.unlink()

        await self.destroy_container_async(
            container_id, session_id, agent_id, audit_logger=audit_logger
        )

    def list_sessions(self) -> list[SessionInfo]:
        """Return a snapshot of all currently active :class:`SessionInfo` objects."""
        with self._lock:
            return [entry.info for entry in self._registry.values()]

    def get_session_policy(self, session_id: str) -> Policy | None:
        """Get the policy configured for an active session."""
        with self._lock:
            entry = self._registry.get(session_id)
            return entry.policy if entry else None

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
                audit_logger=entry.audit_logger,
            )

    async def destroy_container_async(
        self,
        container_id: str,
        session_id: str = "",
        agent_id: str = "",
        audit_logger: AuditLogger | None = None,
    ) -> None:
        """Forcefully remove a container asynchronously."""
        with contextlib.suppress(Exception):
            await self._adapter.destroy_container(container_id, force=True)

        audit_logger = audit_logger or self._audit_logger
        if audit_logger.enabled:
            await audit_logger.log_event(
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
        audit_logger: AuditLogger | None = None,
    ) -> None:
        """Forcefully remove a container synchronously (atexit fallback)."""
        if self._adapter:
            try:
                self._adapter.destroy_container_sync(container_id, force=True)
            except Exception as e:
                logging.debug(f"Sync destruction failed: {e}")
        else:
            logging.warning(
                f"No container adapter registered for synchronous cleanup of {container_id}"
            )

        # Legacy sync emit for atexit handlers
        audit_logger = audit_logger or self._audit_logger
        if not audit_logger.enabled:
            return

        try:
            import json

            entry = {
                "event_type": "container_destroyed",
                "timestamp": datetime.now(UTC).isoformat(),
                "session_id": session_id,
                "agent_id": agent_id,
                "payload": {"container_id": container_id, "mode": "sync_atexit"},
            }
            # We can't easily use the adapter here if it's async-only
            # For FileAuditAdapter, we can try to append directly
            if hasattr(audit_logger._adapter, "_log_file"):
                log_file = audit_logger._adapter._log_file
                if log_file:
                    with open(log_file, "a") as f:
                        f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _timeout_session(self, session_id: str, timeout_seconds: int) -> None:
        """Called when a session exceeds its limit."""

        # Cascading teardown for children on timeout
        children_to_kill = []
        with self._lock:
            for sid, entry_other in self._registry.items():
                if entry_other.parent_session_id == session_id:
                    children_to_kill.append(sid)

        for child_sid in children_to_kill:
            await self.complete_session(
                child_sid,
                exit_code=1,
                error=f"Teardown triggered by parent session {session_id} timeout.",
            )

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
                if hasattr(process, "kill"):
                    if asyncio.iscoroutinefunction(process.kill):
                        await process.kill()
                    else:
                        process.kill()
            except Exception:
                pass

        await self.destroy_container_async(container_id, session_id, agent_id)

        await self._audit_logger.log_event(
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

    async def _session_reaper_loop(self) -> None:
        """Main background loop that monitors all sessions for timeouts and resource limits."""
        while True:
            await asyncio.sleep(1.0)

            now = datetime.now(UTC)
            with self._lock:
                session_ids = list(self._registry.keys())

            for sid in session_ids:
                with self._lock:
                    entry = self._registry.get(sid)

                if not entry or entry.info.status != "running":
                    continue

                # 1. Timeout Check
                if entry.policy.timeout_seconds:
                    started_at = datetime.fromisoformat(entry.info.started_at)
                    if (now - started_at).total_seconds() >= entry.policy.timeout_seconds:
                        logger.warning(
                            f"Session {sid} timed out after {entry.policy.timeout_seconds}s"
                        )
                        await self._timeout_session(sid, entry.policy.timeout_seconds)
                        continue

                # 2. Resource Polling Check
                if entry.policy.resource_monitor_interval > 0:
                    last_poll = entry.last_resource_poll or datetime.fromisoformat(
                        entry.info.started_at
                    )
                    if (now - last_poll).total_seconds() >= entry.policy.resource_monitor_interval:
                        entry.last_resource_poll = now
                        # Fire and forget the poll so we don't block the reaper for other sessions
                        asyncio.create_task(self._poll_session_resources(sid))

    async def _poll_session_resources(self, session_id: str) -> None:
        """Poll container stats and emit audit events if thresholds are exceeded."""
        with self._lock:
            entry = self._registry.get(session_id)
        if not entry or entry.info.status != "running":
            return

        container_id = entry.info.container_id
        agent_id = entry.info.agent_id
        policy = entry.policy

        try:
            stats = await self._adapter.get_container_stats(container_id)
        except Exception:
            return

        # CPU Check
        if stats.cpu_percent > policy.cpu_threshold_percent:
            await self._audit_logger.log_event(
                event_type="resource_limit_exceeded",
                session_id=session_id,
                agent_id=agent_id,
                payload={
                    "violation_type": "cpu_threshold_exceeded",
                    "attempted_action": "cpu_usage",
                    "cpu_percent": stats.cpu_percent,
                    "cpu_threshold_percent": policy.cpu_threshold_percent,
                    "container_id": container_id,
                },
            )

        # Memory Check
        if policy.memory_mb > 0:
            mem_pct = (stats.memory_mb / policy.memory_mb) * 100.0
            if mem_pct > policy.memory_threshold_percent:
                await self._audit_logger.log_event(
                    event_type="resource_limit_exceeded",
                    session_id=session_id,
                    agent_id=agent_id,
                    payload={
                        "violation_type": "memory_threshold_exceeded",
                        "attempted_action": "memory_allocation",
                        "memory_used_mb": round(stats.memory_mb, 2),
                        "memory_limit_mb": policy.memory_mb,
                        "memory_threshold_percent": policy.memory_threshold_percent,
                        "container_id": container_id,
                    },
                )

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

    async def __aenter__(self) -> IsolatedSession:
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
