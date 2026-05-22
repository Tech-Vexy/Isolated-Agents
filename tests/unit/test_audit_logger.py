"""Unit tests for AuditLogger.

Covers:
- Each event type emits a structured log entry (Requirement 8.1)
- Violation events include required fields in payload (Requirement 8.2)
- Log routing to file when log_output_path is set (Requirement 8.3)
- Log routing to stderr when no log_output_path is specified (Requirement 8.4)
"""

from __future__ import annotations

import io
import json
import sys
import unittest.mock
from datetime import datetime

import pytest

from isolated_agents_sdk.audit_logger import AuditLogger, VIOLATION_EVENT_TYPES
from isolated_agents_sdk.models import AuditEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _capture_stderr(logger: AuditLogger, event_type: str, **kwargs) -> dict:
    """Call log_event and return the parsed JSON entry captured from stderr."""
    buf = io.StringIO()
    with unittest.mock.patch.object(sys, "stderr", buf):
        await logger.log_event(
            event_type,
            session_id=kwargs.get("session_id", "sess-1"),
            agent_id=kwargs.get("agent_id", "agent-1"),
            payload=kwargs.get("payload", {}),
        )
    return json.loads(buf.getvalue().strip())


# ---------------------------------------------------------------------------
# Requirement 8.1 – Structured log entry for each event type
# ---------------------------------------------------------------------------

STANDARD_EVENT_TYPES = [
    "container_created",
    "agent_launched",
    "filesystem_access_denied",
    "network_connection_denied",
    "resource_limit_exceeded",
    "privilege_escalation_attempt",
    "output_size_exceeded",
    "container_destroyed",
]

_REQUIRED_TOP_LEVEL_FIELDS = {"event_type", "timestamp", "session_id", "agent_id", "payload"}


class TestStructuredLogEntry:
    """Each event type produces a valid JSON entry with all required fields."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", [
        "container_created",
        "agent_launched",
        "container_destroyed",
    ])
    async def test_non_violation_event_emits_required_fields(self, event_type):
        logger = AuditLogger(log_output_path=None)
        entry = await _capture_stderr(logger, event_type)
        for field in _REQUIRED_TOP_LEVEL_FIELDS:
            assert field in entry, f"Missing required field '{field}' for event '{event_type}'"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", sorted(VIOLATION_EVENT_TYPES))
    async def test_violation_event_emits_required_fields(self, event_type):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "test_violation", "attempted_action": "read /etc/passwd"}
        entry = await _capture_stderr(logger, event_type, payload=payload)
        for field in _REQUIRED_TOP_LEVEL_FIELDS:
            assert field in entry, f"Missing required field '{field}' for event '{event_type}'"

    @pytest.mark.asyncio
    async def test_event_type_is_preserved(self):
        logger = AuditLogger(log_output_path=None)
        entry = await _capture_stderr(logger, "container_created")
        assert entry["event_type"] == "container_created"

    @pytest.mark.asyncio
    async def test_session_id_is_preserved(self):
        logger = AuditLogger(log_output_path=None)
        entry = await _capture_stderr(logger, "agent_launched", session_id="my-session-42")
        assert entry["session_id"] == "my-session-42"

    @pytest.mark.asyncio
    async def test_agent_id_is_preserved(self):
        logger = AuditLogger(log_output_path=None)
        entry = await _capture_stderr(logger, "agent_launched", agent_id="my-agent-99")
        assert entry["agent_id"] == "my-agent-99"

    @pytest.mark.asyncio
    async def test_payload_is_preserved(self):
        logger = AuditLogger(log_output_path=None)
        payload = {"key": "value", "count": 3}
        entry = await _capture_stderr(logger, "container_created", payload=payload)
        assert entry["payload"] == payload

    @pytest.mark.asyncio
    async def test_timestamp_is_iso8601_utc_string(self):
        logger = AuditLogger(log_output_path=None)
        entry = await _capture_stderr(logger, "container_created")
        ts = entry["timestamp"]
        assert isinstance(ts, str) and len(ts) > 0
        # Must parse as a valid datetime
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    @pytest.mark.asyncio
    async def test_output_is_valid_json(self):
        logger = AuditLogger(log_output_path=None)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("container_created", "s1", "a1", {})
        raw = buf.getvalue()
        # Should not raise
        json.loads(raw.strip())

    @pytest.mark.asyncio
    async def test_output_ends_with_newline(self):
        logger = AuditLogger(log_output_path=None)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("container_created", "s1", "a1", {})
        assert buf.getvalue().endswith("\n")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", STANDARD_EVENT_TYPES)
    async def test_all_standard_event_types_produce_output(self, event_type):
        logger = AuditLogger(log_output_path=None)
        payload = {}
        if event_type in VIOLATION_EVENT_TYPES:
            payload = {"violation_type": "v", "attempted_action": "a"}
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event(event_type, "s1", "a1", payload)
        assert buf.getvalue().strip(), f"No output for event type '{event_type}'"


# ---------------------------------------------------------------------------
# Requirement 8.2 – Violation events include violation_type, timestamp,
#                   agent_id, and attempted_action
# ---------------------------------------------------------------------------

class TestViolationEventFields:
    """Violation events must carry violation_type and attempted_action in payload."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", sorted(VIOLATION_EVENT_TYPES))
    async def test_violation_payload_contains_violation_type(self, event_type):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "policy_breach", "attempted_action": "open /secret"}
        entry = await _capture_stderr(logger, event_type, payload=payload)
        assert "violation_type" in entry["payload"]
        assert entry["payload"]["violation_type"] == "policy_breach"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", sorted(VIOLATION_EVENT_TYPES))
    async def test_violation_payload_contains_attempted_action(self, event_type):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "policy_breach", "attempted_action": "connect 8.8.8.8:443"}
        entry = await _capture_stderr(logger, event_type, payload=payload)
        assert "attempted_action" in entry["payload"]
        assert entry["payload"]["attempted_action"] == "connect 8.8.8.8:443"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", sorted(VIOLATION_EVENT_TYPES))
    async def test_violation_entry_contains_timestamp(self, event_type):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "v", "attempted_action": "a"}
        entry = await _capture_stderr(logger, event_type, payload=payload)
        assert "timestamp" in entry
        assert isinstance(entry["timestamp"], str) and len(entry["timestamp"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", sorted(VIOLATION_EVENT_TYPES))
    async def test_violation_entry_contains_agent_id(self, event_type):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "v", "attempted_action": "a"}
        entry = await _capture_stderr(logger, event_type, agent_id="agent-xyz", payload=payload)
        assert entry["agent_id"] == "agent-xyz"

    @pytest.mark.asyncio
    async def test_filesystem_access_denied_event(self):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "filesystem_access", "attempted_action": "read /etc/shadow"}
        entry = await _capture_stderr(logger, "filesystem_access_denied", payload=payload)
        assert entry["event_type"] == "filesystem_access_denied"
        assert entry["payload"]["violation_type"] == "filesystem_access"

    @pytest.mark.asyncio
    async def test_network_connection_denied_event(self):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "network_access", "attempted_action": "connect 1.2.3.4:80"}
        entry = await _capture_stderr(logger, "network_connection_denied", payload=payload)
        assert entry["event_type"] == "network_connection_denied"
        assert entry["payload"]["attempted_action"] == "connect 1.2.3.4:80"

    @pytest.mark.asyncio
    async def test_resource_limit_exceeded_event(self):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "memory_limit", "attempted_action": "allocate 2GB"}
        entry = await _capture_stderr(logger, "resource_limit_exceeded", payload=payload)
        assert entry["event_type"] == "resource_limit_exceeded"

    @pytest.mark.asyncio
    async def test_privilege_escalation_attempt_event(self):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "privilege_escalation", "attempted_action": "sudo su"}
        entry = await _capture_stderr(logger, "privilege_escalation_attempt", payload=payload)
        assert entry["event_type"] == "privilege_escalation_attempt"

    @pytest.mark.asyncio
    async def test_output_size_exceeded_event(self):
        logger = AuditLogger(log_output_path=None)
        payload = {"violation_type": "output_size", "attempted_action": "write 500MB"}
        entry = await _capture_stderr(logger, "output_size_exceeded", payload=payload)
        assert entry["event_type"] == "output_size_exceeded"


# ---------------------------------------------------------------------------
# Requirement 8.3 – Write to file when log_output_path is set
# ---------------------------------------------------------------------------

class TestLogRoutingToFile:
    """When log_output_path is provided, entries go to that file, not stderr."""

    @pytest.mark.asyncio
    async def test_entry_written_to_file(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        await logger.log_event("container_created", "s1", "a1", {})
        with open(log_file, encoding="utf-8") as f:
            content = f.read().strip()
        assert content, "Expected log entry in file"
        entry = json.loads(content)
        assert entry["event_type"] == "container_created"

    @pytest.mark.asyncio
    async def test_nothing_written_to_stderr_when_file_set(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("agent_launched", "s1", "a1", {})
        assert buf.getvalue() == "", "Expected no output on stderr when log_output_path is set"

    @pytest.mark.asyncio
    async def test_multiple_events_appended_to_file(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        await logger.log_event("container_created", "s1", "a1", {})
        await logger.log_event("agent_launched", "s1", "a1", {})
        await logger.log_event("container_destroyed", "s1", "a1", {})
        with open(log_file, encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        assert len(lines) == 3
        event_types = [json.loads(l)["event_type"] for l in lines]
        assert event_types == ["container_created", "agent_launched", "container_destroyed"]

    @pytest.mark.asyncio
    async def test_file_entry_is_valid_json(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        await logger.log_event("container_created", "s1", "a1", {"extra": "data"})
        with open(log_file, encoding="utf-8") as f:
            raw = f.read().strip()
        entry = json.loads(raw)
        assert entry["payload"] == {"extra": "data"}

    @pytest.mark.asyncio
    async def test_file_entry_contains_all_required_fields(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        await logger.log_event("agent_launched", "sess-abc", "agent-xyz", {})
        with open(log_file, encoding="utf-8") as f:
            entry = json.loads(f.read().strip())
        for field in _REQUIRED_TOP_LEVEL_FIELDS:
            assert field in entry

    @pytest.mark.asyncio
    async def test_violation_event_written_to_file(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        payload = {"violation_type": "network_access", "attempted_action": "connect 8.8.8.8"}
        await logger.log_event("network_connection_denied", "s1", "a1", payload)
        with open(log_file, encoding="utf-8") as f:
            entry = json.loads(f.read().strip())
        assert entry["event_type"] == "network_connection_denied"
        assert entry["payload"]["violation_type"] == "network_access"


# ---------------------------------------------------------------------------
# Requirement 8.4 – Write to stderr when no log_output_path is specified
# ---------------------------------------------------------------------------

class TestLogRoutingToStderr:
    """When log_output_path is None, entries go to stderr."""

    @pytest.mark.asyncio
    async def test_entry_written_to_stderr(self):
        logger = AuditLogger(log_output_path=None)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("container_created", "s1", "a1", {})
        assert buf.getvalue().strip(), "Expected log entry on stderr"

    @pytest.mark.asyncio
    async def test_stderr_entry_is_valid_json(self):
        logger = AuditLogger(log_output_path=None)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("agent_launched", "s1", "a1", {})
        entry = json.loads(buf.getvalue().strip())
        assert entry["event_type"] == "agent_launched"

    @pytest.mark.asyncio
    async def test_multiple_events_each_on_own_line(self):
        logger = AuditLogger(log_output_path=None)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("container_created", "s1", "a1", {})
            await logger.log_event("agent_launched", "s1", "a1", {})
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["event_type"] == "container_created"
        assert json.loads(lines[1])["event_type"] == "agent_launched"

    @pytest.mark.asyncio
    async def test_default_constructor_routes_to_stderr(self):
        # AuditLogger() with no args should default to stderr
        logger = AuditLogger()
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("container_destroyed", "s1", "a1", {})
        assert buf.getvalue().strip()

    @pytest.mark.asyncio
    async def test_explicit_none_routes_to_stderr(self):
        logger = AuditLogger(log_output_path=None)
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.log_event("container_destroyed", "s1", "a1", {})
        assert buf.getvalue().strip()


# ---------------------------------------------------------------------------
# emit() method – direct AuditEvent emission
# ---------------------------------------------------------------------------

class TestEmitMethod:
    """AuditLogger.emit() accepts an AuditEvent directly."""

    @pytest.mark.asyncio
    async def test_emit_writes_to_stderr(self):
        logger = AuditLogger(log_output_path=None)
        event = AuditEvent(
            event_type="container_created",
            timestamp="2024-01-01T00:00:00+00:00",
            session_id="s1",
            agent_id="a1",
            payload={},
        )
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", buf):
            await logger.emit(event)
        entry = json.loads(buf.getvalue().strip())
        assert entry["event_type"] == "container_created"
        assert entry["timestamp"] == "2024-01-01T00:00:00+00:00"

    @pytest.mark.asyncio
    async def test_emit_writes_to_file(self, tmp_path):
        log_file = str(tmp_path / "audit.log")
        logger = AuditLogger(log_output_path=log_file)
        event = AuditEvent(
            event_type="agent_launched",
            timestamp="2024-06-15T12:00:00+00:00",
            session_id="sess-emit",
            agent_id="agent-emit",
            payload={"info": "test"},
        )
        await logger.emit(event)
        with open(log_file, encoding="utf-8") as f:
            entry = json.loads(f.read().strip())
        assert entry["session_id"] == "sess-emit"
        assert entry["payload"] == {"info": "test"}
