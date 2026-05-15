"""Audit Logger for the Isolated Agents SDK.

Emits AuditEvent objects as newline-delimited JSON to either a file path
specified in the policy or to stderr.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from isolated_agents_sdk.models import AuditEvent

# Violation event types that require violation_type and attempted_action in payload
VIOLATION_EVENT_TYPES = frozenset({
    "filesystem_access_denied",
    "network_connection_denied",
    "resource_limit_exceeded",
    "privilege_escalation_attempt",
    "output_size_exceeded",
})


class AuditLogger:
    """Emits structured audit log entries as newline-delimited JSON.

    Args:
        log_output_path: Path to write audit logs. If None, writes to stderr.
    """

    def __init__(self, log_output_path: Optional[str] = None) -> None:
        self._log_output_path = log_output_path

    def emit(self, event: AuditEvent) -> None:
        """Serialise an AuditEvent to JSON and write it as a newline-delimited entry.

        Args:
            event: The AuditEvent to emit.
        """
        entry = json.dumps(asdict(event))
        line = entry + "\n"

        if self._log_output_path is not None:
            with open(self._log_output_path, "a", encoding="utf-8") as f:
                f.write(line)
        else:
            sys.stderr.write(line)
            sys.stderr.flush()

    def log_event(
        self,
        event_type: str,
        session_id: str,
        agent_id: str,
        payload: dict,
    ) -> None:
        """Create an AuditEvent with the current UTC timestamp and emit it.

        For violation event types, the payload must include 'violation_type'
        and 'attempted_action'.

        Args:
            event_type: One of the defined event type strings.
            session_id: The session identifier.
            agent_id: The agent identifier.
            payload: Event-specific fields. For violation events, must include
                     'violation_type' and 'attempted_action'.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        event = AuditEvent(
            event_type=event_type,
            timestamp=timestamp,
            session_id=session_id,
            agent_id=agent_id,
            payload=payload,
        )
        self.emit(event)
