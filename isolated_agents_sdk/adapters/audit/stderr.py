"""Stderr audit logger adapter."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    AuditStats,
    EventType,
)


class StderrAuditAdapter(AuditAdapter):
    """Audit logger adapter that writes to sys.stderr.
    
    Useful for local development and CLI tools.
    """
    
    def __init__(self, **kwargs):
        """Initialize stderr audit adapter."""
        super().__init__()
        self._initialized = True
    
    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True
    
    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if adapter is healthy."""
        return True
    
    async def log_event(
        self,
        event_type: EventType,
        session_id: str,
        agent_id: str,
        payload: Optional[dict] = None,
        user_id: Optional[str] = None,
        severity: str = "info",
        tags: Optional[dict[str, str]] = None,
        timestamp: Optional[str] = None,
        raw_event_type: Optional[str] = None,
    ) -> str:
        """Log an audit event to sys.stderr."""
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Use provided timestamp or current UTC time
        if timestamp is None:
            ts = datetime.now(timezone.utc).isoformat()
        else:
            ts = timestamp
            
        # We want to maintain backward compatibility with the legacy JSON format
        # which used strings for event types and had a specific structure.
        
        entry = {
            "event_type": raw_event_type or (event_type.value if hasattr(event_type, 'value') else str(event_type)),
            "timestamp": ts,
            "session_id": session_id,
            "agent_id": agent_id,
            "payload": payload or {},
        }
        
        print(json.dumps(entry), file=sys.stderr)
        return event_id
    
    async def query_events(
        self,
        query: AuditQuery,
    ) -> list[AuditEvent]:
        """Query audit events (not supported for stderr)."""
        return []
    
    async def get_event(
        self,
        event_id: str,
    ) -> AuditEvent:
        """Get a specific audit event (not supported for stderr)."""
        raise NotImplementedError("get_event is not supported for StderrAuditAdapter")
    
    async def delete_events(
        self,
        query: AuditQuery,
    ) -> int:
        """Delete audit events (not supported for stderr)."""
        return 0
    
    async def get_stats(self) -> AuditStats:
        """Get audit log statistics (not supported for stderr)."""
        return AuditStats(
            total_events=0,
            events_by_type={},
            events_by_severity={},
            unique_sessions=0,
            unique_agents=0,
        )

# Made with Bob
