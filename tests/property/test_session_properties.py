"""Property-based tests for session lifecycle behaviour.

Feature: isolated-agents-sdk
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest.mock
from pathlib import Path

from hypothesis import given, settings, strategies as st, HealthCheck

from isolated_agents_sdk.container_provisioner import ContainerProvisioner
from isolated_agents_sdk.models import NetworkPolicy, Policy


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_WINDOWS_RESERVED = frozenset({
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
})

# Lowercase-only filenames avoid Windows case-insensitive filesystem collisions.
_filename_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=30,
).filter(lambda s: s not in _WINDOWS_RESERVED)

_file_content_strategy = st.binary(min_size=0, max_size=1024)

_file_set_strategy = st.dictionaries(
    keys=_filename_strategy,
    values=_file_content_strategy,
    min_size=1,
    max_size=10,
)

_network_policy_strategy = st.builds(
    NetworkPolicy,
    disabled=st.booleans(),
    allowed_endpoints=st.lists(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters=".-:/",
            ),
            min_size=1,
            max_size=50,
        ),
        max_size=5,
    ),
)

_policy_strategy = st.builds(
    Policy,
    cpu_cores=st.floats(min_value=0.1, max_value=64.0, allow_nan=False, allow_infinity=False),
    memory_mb=st.integers(min_value=1, max_value=65536),
    network=_network_policy_strategy,
    readonly_mounts=st.just([]),
    allowed_env_vars=st.just([]),
    output_path_in_container=st.just("/output"),
    max_output_bytes=st.none(),
    timeout_seconds=st.none(),
    log_output_path=st.none(),
)


# ---------------------------------------------------------------------------
# Property 2: Working directory contents are present before agent execution
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 2: Working directory contents are present before agent execution
@given(files=_file_set_strategy, policy=_policy_strategy)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_working_directory_contents_present_before_execution(
    files: dict[str, bytes],
    policy: Policy,
) -> None:
    """For any working directory containing arbitrary files, after the SDK
    provisions the container, all files from the working directory SHALL be
    present inside the container at the expected path before the agent callable
    is invoked.

    The test verifies this by:
    1. Creating a real temporary working directory populated with the generated
       file set.
    2. Mocking ``subprocess.run`` so no real Podman process is spawned.
    3. Asserting that the ``podman run`` command mounts the working directory
       as ``/workspace:rw``, guaranteeing all files are accessible inside the
       container at ``/workspace/<filename>`` before any agent code runs.

    Validates: Requirements 1.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        working_dir = Path(tmpdir)

        # Populate the working directory with the generated file set
        for filename, content in files.items():
            (working_dir / filename).write_bytes(content)

        # Verify all files were written to the working directory
        written_files = {f.name for f in working_dir.iterdir() if f.is_file()}
        assert written_files == set(files.keys()), (
            f"Not all files were written to working dir. "
            f"Expected: {set(files.keys())}, got: {written_files}"
        )

        # Mock subprocess.run so ContainerProvisioner.provision() doesn't
        # require a real Podman installation.
        fake_container_id = "abc123fakeid"
        mock_result = unittest.mock.MagicMock()
        mock_result.stdout = fake_container_id
        mock_result.returncode = 0

        with unittest.mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            # Also mock shutil.which so _check_podman() passes
            with unittest.mock.patch("shutil.which", return_value="/usr/bin/podman"):
                provisioner = ContainerProvisioner()
                handle = provisioner.provision(
                    working_dir=working_dir,
                    policy=policy,
                    session_id="test-session-001",
                    agent_id="test-agent-001",
                )

        # Confirm the container was provisioned with the correct ID
        assert handle.container_id == fake_container_id

        # Extract the podman run command that was passed to subprocess.run
        assert mock_run.called, "subprocess.run was never called — container was not provisioned"
        podman_cmd: list[str] = mock_run.call_args[0][0]

        # The working directory MUST be mounted as /workspace:rw so that all
        # files are accessible inside the container before agent execution.
        expected_mount = f"{working_dir}:/workspace:rw"
        mount_args = [podman_cmd[i + 1] for i, arg in enumerate(podman_cmd) if arg == "-v"]

        assert expected_mount in mount_args, (
            f"Working directory not mounted correctly. "
            f"Expected '{expected_mount}' in volume mounts, got: {mount_args}"
        )

        # Every file in the working directory maps to /workspace/<filename>
        # inside the container. Assert the mount covers all generated files.
        for filename in files:
            expected_container_path = f"/workspace/{filename}"
            # The mount of working_dir:/workspace:rw makes this path available;
            # confirm the mount is present (already asserted above) and that
            # the file exists on the host side of the mount.
            host_file = working_dir / filename
            assert host_file.exists(), (
                f"File '{filename}' missing from working directory host path"
            )
            assert host_file.read_bytes() == files[filename], (
                f"File '{filename}' content mismatch in working directory"
            )


# ---------------------------------------------------------------------------
# Property 3: Container is destroyed after every session
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 3: Container is destroyed after every session
@given(
    container_id=st.text(
        alphabet="abcdef0123456789",
        min_size=12,
        max_size=64,
    ),
    session_id=st.uuids().map(str),
    agent_id=st.text(min_size=1, max_size=40),
    exit_code=st.integers(min_value=0, max_value=255),
    termination_mode=st.sampled_from(["normal", "error", "timeout", "unexpected_exit"]),
)
@settings(max_examples=100)
def test_container_destroyed_after_every_session(
    container_id: str,
    session_id: str,
    agent_id: str,
    exit_code: int,
    termination_mode: str,
) -> None:
    """For any session — whether it ends by normal completion, agent error,
    timeout, or unexpected SDK process exit — the associated container SHALL
    no longer exist after the session ends.

    The test verifies this by:
    1. Registering a session with the SessionManager.
    2. Simulating the given termination mode (normal, error, timeout, unexpected exit).
    3. Asserting that ``podman rm -f <container_id>`` was called exactly once,
       confirming the container was destroyed regardless of how the session ended.

    Validates: Requirements 1.5, 9.1
    """
    from isolated_agents_sdk.session_manager import SessionManager
    from isolated_agents_sdk.audit_logger import AuditLogger

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as log_file:
        log_path = log_file.name

    audit_logger = AuditLogger(log_output_path=log_path)
    manager = SessionManager(audit_logger=audit_logger)

    # Use a non-zero exit code for "error" mode
    effective_exit_code = exit_code if termination_mode != "error" else max(exit_code, 1)

    destroyed_containers: list[str] = []

    def fake_subprocess_run(cmd, **kwargs):
        if cmd[:3] == ["podman", "rm", "-f"]:
            destroyed_containers.append(cmd[3])
        result = unittest.mock.MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    with unittest.mock.patch("subprocess.run", side_effect=fake_subprocess_run):
        # Register the session (simulates container provisioned successfully)
        manager.register_session(
            session_id=session_id,
            container_id=container_id,
            agent_id=agent_id,
            process=None,
            policy=Policy(),
        )

        if termination_mode in ("normal", "error"):
            # Normal completion or agent error — complete_session destroys the container
            manager.complete_session(session_id, effective_exit_code)

        elif termination_mode == "timeout":
            # Timeout — _timeout_session destroys the container
            manager._timeout_session(session_id, timeout_seconds=1)

        elif termination_mode == "unexpected_exit":
            # Unexpected SDK exit — destroy_all destroys all containers
            manager.destroy_all()

    # The container MUST have been destroyed exactly once regardless of mode
    assert container_id in destroyed_containers, (
        f"Container '{container_id}' was not destroyed after session ended "
        f"(termination_mode={termination_mode!r}). "
        f"Destroyed containers: {destroyed_containers}"
    )
    assert destroyed_containers.count(container_id) == 1, (
        f"Container '{container_id}' was destroyed {destroyed_containers.count(container_id)} "
        f"times (expected exactly 1) for termination_mode={termination_mode!r}"
    )

    # The session MUST be removed from the registry after destruction
    remaining = manager.list_sessions()
    remaining_ids = [s.session_id for s in remaining]
    assert session_id not in remaining_ids, (
        f"Session '{session_id}' still present in registry after "
        f"termination_mode={termination_mode!r}. Active sessions: {remaining_ids}"
    )


# ---------------------------------------------------------------------------
# Property 12: Session registry reflects active sessions
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 12: Session registry reflects active sessions
@given(
    session_data=st.lists(
        st.tuples(
            st.uuids().map(str),   # session_id
            st.text(alphabet="abcdef0123456789", min_size=12, max_size=64),  # container_id
            st.text(min_size=1, max_size=40),  # agent_id
        ),
        min_size=1,
        max_size=10,
        unique_by=lambda t: t[0],  # unique session_ids
    ),
    sessions_to_complete=st.data(),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_session_registry_reflects_active_sessions(
    session_data: list[tuple[str, str, str]],
    sessions_to_complete: st.DataObject,
) -> None:
    """For any set of concurrently running sessions, list_sessions() SHALL
    return exactly one SessionInfo entry per active session, each containing
    the correct session_id and container_id. Completed or destroyed sessions
    SHALL not appear in the list.

    The test verifies this by:
    1. Registering multiple sessions concurrently in the SessionManager.
    2. Asserting list_sessions() returns exactly one entry per active session
       with correct session_id and container_id.
    3. Completing a random subset of sessions and asserting they no longer
       appear in list_sessions().

    Validates: Requirements 9.3
    """
    from isolated_agents_sdk.session_manager import SessionManager
    from isolated_agents_sdk.audit_logger import AuditLogger

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as log_file:
        log_path = log_file.name

    audit_logger = AuditLogger(log_output_path=log_path)
    manager = SessionManager(audit_logger=audit_logger)

    def fake_subprocess_run(cmd, **kwargs):
        result = unittest.mock.MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    with unittest.mock.patch("subprocess.run", side_effect=fake_subprocess_run):
        # Register all sessions
        for session_id, container_id, agent_id in session_data:
            manager.register_session(
                session_id=session_id,
                container_id=container_id,
                agent_id=agent_id,
                process=None,
                policy=Policy(),
            )

        # Assert list_sessions() returns exactly one entry per active session
        active = manager.list_sessions()
        active_ids = [s.session_id for s in active]
        active_container_ids = {s.session_id: s.container_id for s in active}

        assert len(active) == len(session_data), (
            f"Expected {len(session_data)} active sessions, got {len(active)}. "
            f"Active IDs: {active_ids}"
        )

        for session_id, container_id, _ in session_data:
            assert session_id in active_ids, (
                f"Session '{session_id}' not found in list_sessions(). "
                f"Active IDs: {active_ids}"
            )
            assert active_container_ids[session_id] == container_id, (
                f"Session '{session_id}' has wrong container_id. "
                f"Expected '{container_id}', got '{active_container_ids[session_id]}'"
            )

        # Choose a random subset of sessions to complete
        indices_to_complete = sessions_to_complete.draw(
            st.lists(
                st.integers(min_value=0, max_value=len(session_data) - 1),
                max_size=len(session_data),
                unique=True,
            )
        )
        completed_ids = {session_data[i][0] for i in indices_to_complete}
        remaining_ids = {s[0] for s in session_data} - completed_ids

        # Complete the chosen sessions
        for i in indices_to_complete:
            session_id = session_data[i][0]
            manager.complete_session(session_id, exit_code=0)

        # Assert completed sessions are no longer in list_sessions()
        after_completion = manager.list_sessions()
        after_ids = {s.session_id for s in after_completion}

        for session_id in completed_ids:
            assert session_id not in after_ids, (
                f"Completed session '{session_id}' still appears in list_sessions(). "
                f"Active IDs: {after_ids}"
            )

        # Assert remaining sessions are still present with correct data
        for session_id in remaining_ids:
            assert session_id in after_ids, (
                f"Active session '{session_id}' missing from list_sessions() "
                f"after completing other sessions. Active IDs: {after_ids}"
            )


# ---------------------------------------------------------------------------
# Property 13: Timeout terminates session
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 13: Timeout terminates session
@given(
    timeout_seconds=st.integers(min_value=1, max_value=60),
    container_id=st.text(
        alphabet="abcdef0123456789",
        min_size=12,
        max_size=64,
    ),
    session_id=st.uuids().map(str),
    agent_id=st.text(min_size=1, max_size=40),
)
@settings(max_examples=100, deadline=None)
def test_timeout_terminates_session(
    timeout_seconds: int,
    container_id: str,
    session_id: str,
    agent_id: str,
) -> None:
    """For any session with a timeout_seconds value, if the agent has not
    completed within that duration, the SDK SHALL terminate the agent process,
    destroy the container, and emit a resource_limit_exceeded audit event.

    The test verifies this by:
    1. Registering a session with a policy that has timeout_seconds set.
    2. Directly invoking _timeout_session() to simulate the timeout firing,
       without waiting for real wall-clock time.
    3. Asserting that:
       - The agent process was killed (process.kill() called).
       - podman rm -f <container_id> was called (container destroyed).
       - A resource_limit_exceeded audit event was emitted with violation_type=timeout.
       - The session is no longer present in list_sessions().

    Validates: Requirements 9.4
    """
    from isolated_agents_sdk.session_manager import SessionManager
    from isolated_agents_sdk.audit_logger import AuditLogger

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as log_file:
        log_path = log_file.name

    audit_logger = AuditLogger(log_output_path=log_path)
    manager = SessionManager(audit_logger=audit_logger)

    # Track which containers were destroyed
    destroyed_containers: list[str] = []

    def fake_subprocess_run(cmd, **kwargs):
        if cmd[:3] == ["podman", "rm", "-f"]:
            destroyed_containers.append(cmd[3])
        result = unittest.mock.MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    # Mock agent process to verify kill() is called
    mock_process = unittest.mock.MagicMock()

    policy = Policy(timeout_seconds=timeout_seconds)

    with unittest.mock.patch("subprocess.run", side_effect=fake_subprocess_run):
        manager.register_session(
            session_id=session_id,
            container_id=container_id,
            agent_id=agent_id,
            process=mock_process,
            policy=policy,
        )

        # Simulate the timeout firing (avoids waiting for real wall-clock time)
        manager._timeout_session(session_id, timeout_seconds)

    # 1. Agent process MUST have been killed
    mock_process.kill.assert_called_once()

    # 2. Container MUST have been destroyed
    assert container_id in destroyed_containers, (
        f"Container '{container_id}' was not destroyed after timeout. "
        f"Destroyed containers: {destroyed_containers}"
    )

    # 3. Session MUST be removed from the registry
    remaining = manager.list_sessions()
    remaining_ids = [s.session_id for s in remaining]
    assert session_id not in remaining_ids, (
        f"Session '{session_id}' still present in registry after timeout. "
        f"Active sessions: {remaining_ids}"
    )

    # 4. A resource_limit_exceeded audit event MUST have been emitted
    import json
    with open(log_path) as f:
        log_lines = [line.strip() for line in f if line.strip()]

    timeout_events = []
    for line in log_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            event.get("event_type") == "resource_limit_exceeded"
            and event.get("session_id") == session_id
        ):
            timeout_events.append(event)

    assert len(timeout_events) >= 1, (
        f"No resource_limit_exceeded audit event found for session '{session_id}'. "
        f"Log entries: {log_lines}"
    )

    # The payload MUST identify this as a timeout violation
    event_payload = timeout_events[0].get("payload", {})
    assert event_payload.get("violation_type") == "timeout", (
        f"Expected violation_type='timeout' in audit event payload, "
        f"got: {event_payload}"
    )
