"""Terminal telemetry adapter for audit logging.

Provides real-time, color-coded, and emoji-enhanced terminal output for agent activity.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, Optional

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    EventType,
)

# ANSI Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
WHITE = "\033[97m"
RESET = "\033[0m"
BOLD = "\033[1m"

class TelemetryAuditAdapter(AuditAdapter):
    """Audit adapter that streams events to the terminal with rich formatting.
    
    This implements the telemetry system described in the documentation,
    using ANSI colors and emojis to provide high visibility into agent execution.
    """
    
    def __init__(self, show_timestamp: bool = True, use_colors: bool = True):
        super().__init__()
        self._show_timestamp = show_timestamp
        self._use_colors = use_colors
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def cleanup(self) -> None:
        self._initialized = False

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
        if not self._initialized:
            return ""

        payload = payload or {}
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        icon, color, message = self._get_event_metadata(event_type, payload)
        
        # Header line
        time_str = f"[{timestamp}] " if self._show_timestamp else ""
        header = f"{icon} {color}{time_str}{message}...{RESET}"
        print(header)
        
        # Details (tree structure)
        details = self._get_details(event_type, payload)
        for i, (key, value) in enumerate(details.items()):
            char = "└─" if i == len(details) - 1 else "├─"
            print(f"   {char} {key}: {CYAN}{value}{RESET}")
            
        sys.stdout.flush()
        return "telemetry-event"

    def _get_event_metadata(self, event_type: EventType, payload: dict) -> tuple[str, str, str]:
        """Map event type to icon, color, and message."""
        mapping = {
            EventType.CONTAINER_CREATED: ("📦", BLUE, "Provisioning container"),
            EventType.CONTAINER_STARTED: ("🚀", BLUE, "Starting container"),
            EventType.CONTAINER_STOPPED: ("🛑", BLUE, "Stopping container"),
            EventType.CONTAINER_DESTROYED: ("🗑️", BLUE, "Destroying container"),
            EventType.AGENT_STARTED: ("🚀", BLUE, "Starting agent execution"),
            EventType.AGENT_COMPLETED: ("✅", GREEN, "Agent execution completed"),
            EventType.AGENT_FAILED: ("❌", RED, "Agent execution failed"),
            EventType.AGENT_TIMEOUT: ("⚠️", YELLOW, "Agent timed out"),
            EventType.POLICY_VALIDATED: ("🔧", WHITE, "Validating policy"),
            EventType.POLICY_VIOLATION: ("❌", RED, "Policy violation detected"),
            EventType.NETWORK_BLOCKED: ("🌐", RED, "Network connection denied"),
            EventType.RESOURCE_LIMIT_EXCEEDED: ("⚠️", YELLOW, "Resource limit exceeded"),
            EventType.ARTIFACT_STORED: ("📤", BLUE, "Collecting output artifacts"),
            EventType.SESSION_CREATED: ("🚀", BLUE, "Initializing isolated sandbox"),
            EventType.SYSTEM_ERROR: ("❌", RED, "System error occurred"),
        }
        
        return mapping.get(event_type, ("📝", WHITE, f"Event: {event_type.value}"))

    def _get_details(self, event_type: EventType, payload: dict) -> dict[str, Any]:
        """Extract relevant details for the tree view based on event type."""
        details = {}
        
        if event_type == EventType.CONTAINER_CREATED:
            details["Image"] = payload.get("image", "unknown")
            details["Container ID"] = payload.get("container_id", "pending")[:12]
            details["Adapter"] = payload.get("adapter", "unknown")
            
        elif event_type == EventType.SESSION_CREATED:
            details["Container Runtime"] = payload.get("runtime", "Podman")
            details["Storage Backend"] = payload.get("storage", "Local Filesystem")
            details["Audit Logger"] = payload.get("logger", "File")
            
        elif event_type == EventType.POLICY_VALIDATED:
            details["CPU Limit"] = f"{payload.get('cpu_cores', '1.0')} cores"
            details["Memory Limit"] = f"{payload.get('memory_mb', '512')} MB"
            details["Network"] = "Enabled" if payload.get("network_enabled") else "Disabled"
            details["Timeout"] = f"{payload.get('timeout_seconds', 'None')} seconds"
            
        elif event_type == EventType.AGENT_STARTED:
            details["Agent"] = payload.get("agent_id", "unknown")
            details["Container ID"] = payload.get("container_id", "unknown")[:12]
            
        elif event_type == EventType.AGENT_COMPLETED:
            details["Exit Code"] = payload.get("exit_code", 0)
            details["Status"] = "Success"
            
        elif event_type == EventType.RESOURCE_LIMIT_EXCEEDED:
            details["Violation"] = payload.get("violation_type", "unknown")
            details["Action"] = payload.get("attempted_action", "unknown")
            details["Reason"] = payload.get("reason", "unknown")
            
        elif event_type == EventType.NETWORK_BLOCKED:
            details["Destination"] = payload.get("attempted_endpoint", "unknown")
            details["Action"] = "Blocked"
            
        elif event_type == EventType.ARTIFACT_STORED:
            details["File"] = payload.get("artifact_name", "unknown")
            details["Size"] = f"{payload.get('size_bytes', 0)} bytes"
            
        # Add general payload fields if not already covered and not too many
        for k, v in payload.items():
            if k not in ["image", "container_id", "adapter", "runtime", "storage", "logger", 
                         "cpu_cores", "memory_mb", "network_enabled", "timeout_seconds",
                         "agent_id", "exit_code", "violation_type", "attempted_action", 
                         "reason", "attempted_endpoint", "artifact_name", "size_bytes"]:
                if len(details) < 5:
                    details[k.replace("_", " ").title()] = v
                    
        return details

    async def query_events(self, query: AuditQuery) -> list[AuditEvent]:
        return []

    async def get_event(self, event_id: str) -> AuditEvent:
        raise NotImplementedError("Telemetry adapter does not support event retrieval")

    async def get_stats(self) -> dict[str, Any]:
        return {}
