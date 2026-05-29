"""Property-based tests for Audit Logger.

Feature: isolated-agents-sdk
"""

# Feature: isolated-agents-sdk, Property 10: Audit log entries contain all required fields
# Feature: isolated-agents-sdk, Property 11: Audit logs are written to the correct destination

import asyncio
import io
import json
import os
import sys
import tempfile
import unittest.mock

from hypothesis import given, settings
from hypothesis import strategies as st

from isolated_agents_sdk.audit_logger import VIOLATION_EVENT_TYPES, AuditLogger

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty printable text for IDs and event types
_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"),
    min_size=1,
    max_size=50,
)

# Simple payload values: strings, ints, booleans
_payload_value = st.one_of(st.text(max_size=30), st.integers(), st.booleans())

_payload_strategy = st.dictionaries(
    keys=_text,
    values=_payload_value,
    max_size=5,
)

# Non-violation event types
_non_violation_event_types = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=40,
).filter(lambda t: t not in VIOLATION_EVENT_TYPES)

_violation_event_types = st.sampled_from(sorted(VIOLATION_EVENT_TYPES))

# Payload for violation events must include violation_type and attempted_action
_violation_payload_strategy = st.fixed_dictionaries(
    {
        "violation_type": _text,
        "attempted_action": _text,
    },
    optional={
        "extra": _payload_value,
    },
)


# ---------------------------------------------------------------------------
# Property 10: Audit log entries contain all required fields
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {"event_type", "timestamp", "session_id", "agent_id", "payload"}


@given(
    event_type=_non_violation_event_types,
    session_id=_text,
    agent_id=_text,
    payload=_payload_strategy,
)
@settings(max_examples=100)
def test_audit_log_required_fields_non_violation(
    event_type: str,
    session_id: str,
    agent_id: str,
    payload: dict,
) -> None:
    """For any non-violation event, the emitted JSON SHALL contain all required fields.

    Validates: Requirements 8.1, 8.2
    """
    logger = AuditLogger(log_output_path=None)
    buf = io.StringIO()

    with unittest.mock.patch.object(sys, "stderr", buf):
        asyncio.run(logger.log_event(event_type, session_id, agent_id, payload))

    line = buf.getvalue().strip()
    assert line, "No output was emitted"

    entry = json.loads(line)

    for field in _REQUIRED_FIELDS:
        assert field in entry, f"Required field '{field}' missing from audit log entry"

    assert entry["event_type"] == event_type
    assert entry["session_id"] == session_id
    assert entry["agent_id"] == agent_id
    assert entry["payload"] == payload
    # Timestamp must be a non-empty string (ISO 8601 UTC)
    assert isinstance(entry["timestamp"], str) and len(entry["timestamp"]) > 0


@given(
    event_type=_violation_event_types,
    session_id=_text,
    agent_id=_text,
    payload=_violation_payload_strategy,
)
@settings(max_examples=100)
def test_audit_log_required_fields_violation(
    event_type: str,
    session_id: str,
    agent_id: str,
    payload: dict,
) -> None:
    """For violation events, the emitted JSON SHALL contain all required fields,
    and the payload SHALL include 'violation_type' and 'attempted_action'.

    Validates: Requirements 8.1, 8.2
    """
    logger = AuditLogger(log_output_path=None)
    buf = io.StringIO()

    with unittest.mock.patch.object(sys, "stderr", buf):
        asyncio.run(logger.log_event(event_type, session_id, agent_id, payload))

    line = buf.getvalue().strip()
    assert line, "No output was emitted"

    entry = json.loads(line)

    for field in _REQUIRED_FIELDS:
        assert field in entry, f"Required field '{field}' missing from audit log entry"

    assert entry["event_type"] == event_type
    assert entry["session_id"] == session_id
    assert entry["agent_id"] == agent_id

    emitted_payload = entry["payload"]
    assert "violation_type" in emitted_payload, (
        "Violation event payload must contain 'violation_type'"
    )
    assert "attempted_action" in emitted_payload, (
        "Violation event payload must contain 'attempted_action'"
    )


# ---------------------------------------------------------------------------
# Property 11: Audit logs are written to the correct destination
# ---------------------------------------------------------------------------


@given(
    event_type=_non_violation_event_types,
    session_id=_text,
    agent_id=_text,
    payload=_payload_strategy,
)
@settings(max_examples=100)
def test_audit_log_destination_stderr_when_no_path(
    event_type: str,
    session_id: str,
    agent_id: str,
    payload: dict,
) -> None:
    """When log_output_path is None, audit entries SHALL be written to stderr.

    Validates: Requirements 8.4
    """
    logger = AuditLogger(log_output_path=None)
    buf = io.StringIO()

    with unittest.mock.patch.object(sys, "stderr", buf):
        asyncio.run(logger.log_event(event_type, session_id, agent_id, payload))

    assert buf.getvalue().strip(), "Expected a log entry on stderr but got nothing"
    entry = json.loads(buf.getvalue().strip())
    assert entry["event_type"] == event_type


@given(
    event_type=_non_violation_event_types,
    session_id=_text,
    agent_id=_text,
    payload=_payload_strategy,
)
@settings(max_examples=100)
def test_audit_log_destination_file_when_path_given(
    event_type: str,
    session_id: str,
    agent_id: str,
    payload: dict,
) -> None:
    """When log_output_path is set, audit entries SHALL be written to that file
    and NOT to stderr.

    Validates: Requirements 8.3
    """
    with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        logger = AuditLogger(log_output_path=tmp_path)
        stderr_buf = io.StringIO()

        with unittest.mock.patch.object(sys, "stderr", stderr_buf):
            asyncio.run(logger.log_event(event_type, session_id, agent_id, payload))

        # Nothing should have been written to stderr
        assert stderr_buf.getvalue() == "", (
            "Expected no output on stderr when log_output_path is set"
        )

        # The log entry should be in the file
        with open(tmp_path, encoding="utf-8") as f:
            line = f.read().strip()

        assert line, "Expected a log entry in the file but got nothing"
        entry = json.loads(line)
        assert entry["event_type"] == event_type
        assert entry["session_id"] == session_id
        assert entry["agent_id"] == agent_id
    finally:
        os.unlink(tmp_path)
