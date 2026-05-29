"""Type definitions for audit adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Optional


class EventType(StrEnum):
    """Audit event types."""

    # Container lifecycle
    CONTAINER_CREATED = "container_created"
    CONTAINER_STARTED = "container_started"
    CONTAINER_STOPPED = "container_stopped"
    CONTAINER_DESTROYED = "container_destroyed"

    # Agent execution
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    AGENT_TIMEOUT = "agent_timeout"

    # Policy enforcement
    POLICY_VALIDATED = "policy_validated"
    POLICY_VIOLATION = "policy_violation"
    NETWORK_BLOCKED = "network_blocked"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"

    # Artifact management
    ARTIFACT_STORED = "artifact_stored"
    ARTIFACT_RETRIEVED = "artifact_retrieved"
    ARTIFACT_DELETED = "artifact_deleted"

    # Session management
    SESSION_CREATED = "session_created"
    SESSION_CLOSED = "session_closed"

    # Security events
    SECURITY_VIOLATION = "security_violation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"

    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"


@dataclass
class AuditEvent:
    """Audit event record.

    Attributes:
        event_id: Unique event identifier
        event_type: Type of event
        timestamp: Event timestamp
        session_id: Session identifier
        agent_id: Agent identifier
        user_id: Optional user identifier
        payload: Event-specific data
        severity: Event severity (info, warning, error, critical)
        tags: Optional key-value tags
    """

    event_id: str
    event_type: EventType
    timestamp: datetime
    session_id: str
    agent_id: str
    user_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    severity: str = "info"
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class AuditQuery:
    """Query parameters for audit log search.

    Attributes:
        session_id: Filter by session ID
        agent_id: Filter by agent ID
        user_id: Filter by user ID
        event_types: Filter by event types
        start_time: Filter events after this time
        end_time: Filter events before this time
        severity: Filter by severity
        limit: Maximum number of results
        offset: Pagination offset
    """

    session_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None
    event_types: list[EventType] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    severity: str | None = None
    limit: int = 100
    offset: int = 0


@dataclass
class AuditStats:
    """Audit log statistics.

    Attributes:
        total_events: Total number of events
        events_by_type: Count of events by type
        events_by_severity: Count of events by severity
        unique_sessions: Number of unique sessions
        unique_agents: Number of unique agents
        oldest_event: Timestamp of oldest event
        newest_event: Timestamp of newest event
    """

    total_events: int
    events_by_type: dict[str, int] = field(default_factory=dict)
    events_by_severity: dict[str, int] = field(default_factory=dict)
    unique_sessions: int = 0
    unique_agents: int = 0
    oldest_event: datetime | None = None
    newest_event: datetime | None = None


# Made with Bob
