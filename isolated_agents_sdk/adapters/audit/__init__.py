"""Audit logger adapters for the Isolated Agents SDK.

This package provides pluggable audit logger adapters for:
- File-based logging
- Database logging (PostgreSQL, MySQL, SQLite)
- Cloud logging services (CloudWatch, Datadog, Splunk)
- Structured logging with JSON

Example usage:
    from isolated_agents_sdk.adapters.audit import FileAuditAdapter
    from isolated_agents_sdk.adapters.factory import AdapterFactory
    
    # Create file audit adapter
    adapter = AdapterFactory.create_audit_adapter("file", log_path="/var/log/agents")
    await adapter.initialize()
    
    # Log event
    await adapter.log_event(
        event_type="container_created",
        session_id="session-123",
        agent_id="agent-456",
        payload={"container_id": "abc123"}
    )
"""

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    EventType,
)

__all__ = [
    "AuditAdapter",
    "FileAuditAdapter",
    "AuditEvent",
    "AuditQuery",
    "EventType",
]

# Made with Bob