"""Audit Logger for the Isolated Agents SDK.

Emits AuditEvent objects via an AuditAdapter.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timezone
from typing import Optional

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
from isolated_agents_sdk.adapters.audit.stderr import StderrAuditAdapter
from isolated_agents_sdk.adapters.audit.types import EventType
from isolated_agents_sdk.adapters.factory import AdapterFactory
from isolated_agents_sdk.models import AuditEvent

# Detect if adapters are available
try:
    from isolated_agents_sdk.adapters.factory import AdapterFactory

    _ADAPTERS_AVAILABLE = True
except ImportError:
    _ADAPTERS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Violation event types that require violation_type and attempted_action in payload
VIOLATION_EVENT_TYPES = frozenset(
    {
        "filesystem_access_denied",
        "network_connection_denied",
        "resource_limit_exceeded",
        "privilege_escalation_attempt",
        "output_size_exceeded",
    }
)

# Mapping from legacy event types to Adapter EventTypes
EVENT_TYPE_MAP = {
    "container_created": EventType.CONTAINER_CREATED,
    "container_started": EventType.CONTAINER_STARTED,
    "container_stopped": EventType.CONTAINER_STOPPED,
    "container_destroyed": EventType.CONTAINER_DESTROYED,
    "agent_launched": EventType.AGENT_STARTED,
    "agent_interactive_start": EventType.AGENT_STARTED,
    "agent_completed": EventType.AGENT_COMPLETED,
    "agent_failed": EventType.AGENT_FAILED,
    "agent_timeout": EventType.AGENT_TIMEOUT,
    "policy_validated": EventType.POLICY_VALIDATED,
    "network_connection_denied": EventType.NETWORK_BLOCKED,
    "resource_limit_exceeded": EventType.RESOURCE_LIMIT_EXCEEDED,
    "filesystem_access_denied": EventType.POLICY_VIOLATION,
    "privilege_escalation_attempt": EventType.SECURITY_VIOLATION,
    "output_size_exceeded": EventType.POLICY_VIOLATION,
    "sub_agent_spawned": EventType.CONTAINER_CREATED,  # Sub-agents are currently mapped to container creation
    "sub_agent_completed": EventType.AGENT_COMPLETED,
    "policy_cap_clamped": EventType.POLICY_VALIDATED,
    "sub_agent_cancelled": EventType.AGENT_COMPLETED,
    "nesting_depth_exceeded": EventType.POLICY_VIOLATION,
    "sub_agent_count_exceeded": EventType.POLICY_VIOLATION,
}


class AuditLogger:
    """Emits structured audit log entries via an AuditAdapter.

    Args:
        adapter: An instance of :class:`AuditAdapter`. If None, a
                 :class:`FileAuditAdapter` is used.
        log_output_path: Legacy parameter for backward compatibility,
                         used to initialize FileAuditAdapter if no adapter is given.
        enabled: Whether to actually emit logs. Useful for clean CLI output.
    """

    def __init__(
        self,
        adapter: AuditAdapter | None = None,
        log_output_path: str | None = None,
        enabled: bool = True,
    ) -> None:
        """Initialize AuditLogger.

        Args:
            adapter: An instance of :class:`AuditAdapter`. If None, attempts to
                     create one via AdapterFactory or falls back to legacy path.
            log_output_path: Legacy parameter for backward compatibility.
            enabled: If False, log() calls will do nothing.
        """
        self.enabled = enabled
        if adapter:
            self._adapter = adapter
        elif log_output_path:
            self._adapter = FileAuditAdapter(log_file=log_output_path)
        else:
            # If no path, use stderr to match legacy behavior
            self._adapter = StderrAuditAdapter()

        self._initialized = False
        # v0.2.0 In-memory metrics for real-time observability
        self._metrics = {"total_runs": 0, "violations": 0, "agent_stats": {}}

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self._adapter.initialize()
            self._initialized = True

    async def emit(self, event: AuditEvent) -> None:
        """Serialise an AuditEvent to JSON and write it via the adapter.

        Args:
            event: The AuditEvent to emit.
        """
        if not self.enabled:
            return

        await self._ensure_initialized()

        # v0.2.0: Update metrics
        if event.event_type == "agent_launched":
            self._metrics["total_runs"] += 1
        elif event.event_type in VIOLATION_EVENT_TYPES:
            self._metrics["violations"] += 1

        event_type = EVENT_TYPE_MAP.get(event.event_type, EventType.SYSTEM_INFO)

        await self._adapter.log_event(
            event_type=event_type,
            session_id=event.session_id,
            agent_id=event.agent_id,
            payload=event.payload,
            severity="warning" if event.event_type in VIOLATION_EVENT_TYPES else "info",
            timestamp=event.timestamp,
            raw_event_type=event.event_type,
        )

    async def log_event(
        self,
        event_type: str,
        session_id: str,
        agent_id: str,
        payload: dict,
    ) -> None:
        """Create an AuditEvent with the current UTC timestamp and emit it.

        Args:
            event_type: Legacy event type string.
            session_id: The session identifier.
            agent_id: The agent identifier.
            payload: Event-specific fields.
        """
        timestamp = datetime.now(UTC).isoformat()
        event = AuditEvent(
            event_type=event_type,
            timestamp=timestamp,
            session_id=session_id,
            agent_id=agent_id,
            payload=payload,
        )
        await self.emit(event)
