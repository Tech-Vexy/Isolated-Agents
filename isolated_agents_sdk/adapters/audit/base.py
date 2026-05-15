"""Base interface for audit logger adapters."""

from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    AuditStats,
    EventType,
)


class AuditAdapter(BaseAdapter):
    """Abstract base class for audit logger adapters.
    
    Implementations must provide methods for logging events, querying logs,
    and managing audit data across different backends (file, database, cloud).
    
    Lifecycle:
        1. Initialize adapter
        2. Log events
        3. Query and analyze logs
        4. Cleanup adapter
    
    Example:
        >>> adapter = FileAuditAdapter(log_path="/var/log/agents")
        >>> await adapter.initialize()
        >>> 
        >>> # Log event
        >>> await adapter.log_event(
        ...     event_type=EventType.CONTAINER_CREATED,
        ...     session_id="session-123",
        ...     agent_id="agent-456",
        ...     payload={"container_id": "abc123"}
        ... )
        >>> 
        >>> # Query events
        >>> query = AuditQuery(session_id="session-123")
        >>> events = await adapter.query_events(query)
        >>> 
        >>> await adapter.cleanup()
    """
    
    @abstractmethod
    async def log_event(
        self,
        event_type: EventType,
        session_id: str,
        agent_id: str,
        payload: Optional[dict] = None,
        user_id: Optional[str] = None,
        severity: str = "info",
        tags: Optional[dict[str, str]] = None,
    ) -> str:
        """Log an audit event.
        
        Args:
            event_type: Type of event
            session_id: Session identifier
            agent_id: Agent identifier
            payload: Event-specific data
            user_id: Optional user identifier
            severity: Event severity (info, warning, error, critical)
            tags: Optional key-value tags
        
        Returns:
            Event ID
        
        Raises:
            AdapterOperationError: If logging fails
        """
        pass
    
    @abstractmethod
    async def query_events(
        self,
        query: AuditQuery,
    ) -> list[AuditEvent]:
        """Query audit events.
        
        Args:
            query: Query parameters
        
        Returns:
            List of matching audit events
        
        Raises:
            AdapterOperationError: If query fails
        """
        pass
    
    @abstractmethod
    async def get_event(
        self,
        event_id: str,
    ) -> AuditEvent:
        """Get a specific audit event by ID.
        
        Args:
            event_id: Event identifier
        
        Returns:
            Audit event
        
        Raises:
            AdapterOperationError: If event not found
        """
        pass
    
    @abstractmethod
    async def delete_events(
        self,
        query: AuditQuery,
    ) -> int:
        """Delete audit events matching query.
        
        Args:
            query: Query parameters
        
        Returns:
            Number of events deleted
        
        Raises:
            AdapterOperationError: If deletion fails
        """
        pass
    
    async def get_stats(self) -> AuditStats:
        """Get audit log statistics.
        
        This is an optional method that may be implemented by adapters.
        
        Returns:
            Audit statistics
        """
        return AuditStats(total_events=0)
    
    async def export_events(
        self,
        query: AuditQuery,
        format: str = "json",
    ) -> str:
        """Export audit events in specified format.
        
        This is an optional method that may be implemented by adapters.
        
        Args:
            query: Query parameters
            format: Export format (json, csv, etc.)
        
        Returns:
            Exported data as string
        
        Raises:
            NotImplementedError: If adapter doesn't support export
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support event export"
        )
    
    async def archive_events(
        self,
        query: AuditQuery,
        archive_path: str,
    ) -> int:
        """Archive old audit events.
        
        This is an optional method that may be implemented by adapters.
        
        Args:
            query: Query parameters for events to archive
            archive_path: Path to archive location
        
        Returns:
            Number of events archived
        
        Raises:
            NotImplementedError: If adapter doesn't support archiving
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support event archiving"
        )

# Made with Bob