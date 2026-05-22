"""File-based audit logger adapter."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    AuditStats,
    EventType,
)
from isolated_agents_sdk.adapters.exceptions import (
    AdapterInitializationError,
    AdapterOperationError,
)


class FileAuditAdapter(AuditAdapter):
    """File-based audit logger adapter.
    
    Stores audit events as JSON lines in log files, organized by date.
    
    Directory structure:
        log_path/
            2026-05-15.jsonl
            2026-05-16.jsonl
            ...
    
    Each line is a JSON object representing an audit event.
    
    Example:
        >>> adapter = FileAuditAdapter(log_path="/var/log/agents")
        >>> await adapter.initialize()
        >>> 
        >>> event_id = await adapter.log_event(
        ...     event_type=EventType.CONTAINER_CREATED,
        ...     session_id="session-123",
        ...     agent_id="agent-456",
        ...     payload={"container_id": "abc123"}
        ... )
    """
    
    def __init__(
        self, 
        log_path: Optional[str | Path] = None, 
        log_file: Optional[str | Path] = None,
        create_dirs: bool = True,
        **kwargs
    ):
        """Initialize file audit adapter.
        
        Args:
            log_path: Directory for log files
            log_file: Specific log file path (if provided, directory will be used as log_path)
            create_dirs: Automatically create log directory
            **kwargs: Additional configuration parameters
        """
        super().__init__()
        
        self._fixed_log_file = None
        
        # Determine log path from either log_path or log_file
        if log_file:
            self._fixed_log_file = Path(log_file)
            self._log_path = self._fixed_log_file.parent
        elif log_path:
            self._log_path = Path(log_path)
        else:
            self._log_path = Path("./.isolated_agents/logs")
            
        self._create_dirs = create_dirs
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the adapter and create log directory."""
        if self._initialized:
            return
        
        try:
            if self._log_path:
                self._log_path.mkdir(parents=True, exist_ok=True)
            self._initialized = True
        except Exception as e:
            raise AdapterInitializationError(
                f"Failed to create log directory {self._log_path}: {e}"
            )
    
    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if log directory is accessible."""
        try:
            return self._log_path.exists() and self._log_path.is_dir()
        except Exception:
            return False
    
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
        """Log an audit event to file."""
        if not self._initialized:
            await self.initialize()
        
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Parse timestamp or use current time
        if timestamp:
            try:
                dt_timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                dt_timestamp = datetime.now()
        else:
            dt_timestamp = datetime.now()
        
        # Create event
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=dt_timestamp,
            session_id=session_id,
            agent_id=agent_id,
            user_id=user_id,
            payload=payload or {},
            severity=severity,
            tags=tags or {},
        )
        
        # We need to preserve raw_event_type if provided for backward compatibility
        # in the serialized output.
        serialized_data = self._serialize_event(event)
        if raw_event_type:
            obj = json.loads(serialized_data)
            obj["event_type"] = raw_event_type
            serialized_data = json.dumps(obj)
        
        # Get log file for today
        log_file = self._get_log_file(dt_timestamp)
        
        # Append event to log file
        try:
            with log_file.open("a") as f:
                f.write(serialized_data + "\n")
        except Exception as e:
            raise AdapterOperationError(
                f"Failed to write audit event: {e}"
            )
        
        return event_id
    
    async def query_events(
        self,
        query: AuditQuery,
    ) -> list[AuditEvent]:
        """Query audit events from log files."""
        events = []
        
        # Determine which log files to search
        log_files = self._get_log_files_for_query(query)
        
        for log_file in log_files:
            if not log_file.exists():
                continue
            
            try:
                with log_file.open("r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            event = self._deserialize_event(line)
                            if self._matches_query(event, query):
                                events.append(event)
                        except Exception:
                            # Skip malformed lines
                            continue
            except Exception:
                # Skip files that can't be read
                continue
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Apply pagination
        start = query.offset
        end = start + query.limit
        return events[start:end]
    
    async def get_event(
        self,
        event_id: str,
    ) -> AuditEvent:
        """Get a specific audit event by ID."""
        # Search all log files
        for log_file in self._log_path.glob("*.jsonl"):
            try:
                with log_file.open("r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            event = self._deserialize_event(line)
                            if event.event_id == event_id:
                                return event
                        except Exception:
                            continue
            except Exception:
                continue
        
        raise AdapterOperationError(
            f"Event {event_id} not found"
        )
    
    async def delete_events(
        self,
        query: AuditQuery,
    ) -> int:
        """Delete audit events matching query.
        
        Note: This creates new log files without the deleted events.
        """
        deleted_count = 0
        log_files = self._get_log_files_for_query(query)
        
        for log_file in log_files:
            if not log_file.exists():
                continue
            
            # Read all events
            events = []
            try:
                with log_file.open("r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            event = self._deserialize_event(line)
                            if not self._matches_query(event, query):
                                events.append(event)
                            else:
                                deleted_count += 1
                        except Exception:
                            # Keep malformed lines
                            events.append(line)
            except Exception:
                continue
            
            # Rewrite log file without deleted events
            try:
                with log_file.open("w") as f:
                    for event in events:
                        if isinstance(event, AuditEvent):
                            f.write(self._serialize_event(event) + "\n")
                        else:
                            f.write(event + "\n")
            except Exception as e:
                raise AdapterOperationError(
                    f"Failed to rewrite log file: {e}"
                )
        
        return deleted_count
    
    async def get_stats(self) -> AuditStats:
        """Get audit log statistics."""
        total_events = 0
        events_by_type = {}
        events_by_severity = {}
        sessions = set()
        agents = set()
        oldest = None
        newest = None
        
        for log_file in self._log_path.glob("*.jsonl"):
            try:
                with log_file.open("r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            event = self._deserialize_event(line)
                            total_events += 1
                            
                            # Count by type
                            event_type = event.event_type.value
                            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
                            
                            # Count by severity
                            events_by_severity[event.severity] = events_by_severity.get(event.severity, 0) + 1
                            
                            # Track sessions and agents
                            sessions.add(event.session_id)
                            agents.add(event.agent_id)
                            
                            # Track timestamps
                            if oldest is None or event.timestamp < oldest:
                                oldest = event.timestamp
                            if newest is None or event.timestamp > newest:
                                newest = event.timestamp
                        except Exception:
                            continue
            except Exception:
                continue
        
        return AuditStats(
            total_events=total_events,
            events_by_type=events_by_type,
            events_by_severity=events_by_severity,
            unique_sessions=len(sessions),
            unique_agents=len(agents),
            oldest_event=oldest,
            newest_event=newest,
        )
    
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    
    def _get_log_file(self, timestamp: datetime) -> Path:
        """Get log file path for a given timestamp."""
        if self._fixed_log_file:
            return self._fixed_log_file
        date_str = timestamp.strftime("%Y-%m-%d")
        return self._log_path / f"{date_str}.jsonl"
    
    def _get_log_files_for_query(self, query: AuditQuery) -> list[Path]:
        """Get list of log files to search for a query."""
        if query.start_time and query.end_time:
            # Generate list of dates between start and end
            files = []
            current = query.start_time.date()
            end = query.end_time.date()
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                files.append(self._log_path / f"{date_str}.jsonl")
                current = current.replace(day=current.day + 1)
            return files
        else:
            # Search all log files
            return sorted(self._log_path.glob("*.jsonl"))
    
    def _matches_query(self, event: AuditEvent, query: AuditQuery) -> bool:
        """Check if an event matches query criteria."""
        if query.session_id and event.session_id != query.session_id:
            return False
        
        if query.agent_id and event.agent_id != query.agent_id:
            return False
        
        if query.user_id and event.user_id != query.user_id:
            return False
        
        if query.event_types and event.event_type not in query.event_types:
            return False
        
        if query.start_time and event.timestamp < query.start_time:
            return False
        
        if query.end_time and event.timestamp > query.end_time:
            return False
        
        if query.severity and event.severity != query.severity:
            return False
        
        return True
    
    def _serialize_event(self, event: AuditEvent) -> str:
        """Serialize event to JSON string."""
        return json.dumps({
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "session_id": event.session_id,
            "agent_id": event.agent_id,
            "user_id": event.user_id,
            "payload": event.payload,
            "severity": event.severity,
            "tags": event.tags,
        })
    
    def _deserialize_event(self, data: str) -> AuditEvent:
        """Deserialize event from JSON string."""
        obj = json.loads(data)
        return AuditEvent(
            event_id=obj["event_id"],
            event_type=EventType(obj["event_type"]),
            timestamp=datetime.fromisoformat(obj["timestamp"]),
            session_id=obj["session_id"],
            agent_id=obj["agent_id"],
            user_id=obj.get("user_id"),
            payload=obj.get("payload", {}),
            severity=obj.get("severity", "info"),
            tags=obj.get("tags", {}),
        )

# Made with Bob