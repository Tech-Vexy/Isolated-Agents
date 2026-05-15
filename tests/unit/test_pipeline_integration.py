"""Integration tests for the full run_agent() pipeline.

Tests the end-to-end flow: PolicyValidator → ContainerProvisioner →
AgentRunner → OutputCollector → SessionManager, with all Podman subprocess
calls mocked so no live Podman installation is required.

Requirements: 6.1, 6.5, 9.1
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch, AsyncMock

import pytest

import isolated_agents_sdk as sdk
from isolated_agents_sdk import (
    AgentResult,
    Policy,
    NetworkPolicy,
    PolicyValidationError,
    PodmanNotFoundError,
    WorkingDirectoryError,
    run_agent,
    async_run_agent,
)
from isolated_agents_sdk.session_manager import SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trivial_agent():
    """A trivial agent callable that does nothing and returns None."""
    return None


async def _make_mock_proc(exit_code: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    """Return a mock asyncio subprocess that finishes immediately."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.wait = AsyncMock(return_value=exit_code)
    proc.returncode = exit_code

    # Mock stdout/stderr as stream readers
    proc.stdout = AsyncMock()
    proc.stdout.read = AsyncMock(side_effect=[stdout, b""])
    proc.stderr = AsyncMock()
    proc.stderr.read = AsyncMock(side_effect=[stderr, b""])

    return proc


def _make_fake_podman_exec(container_id: str = "test-container-abc123"):
    """Return a side_effect function for asyncio.create_subprocess_exec that simulates Podman.

    The new OutputCollector calls:
      1. ``podman exec … test -d /output``   — existence check
      2. ``podman exec … find /output -type f``  — file listing
      3. ``podman cp <container>:/output/result.txt <host_path>``  — per-file copy
    """
    # The fake output file that the "container" exposes.
    _FAKE_FILE = "result.txt"
    _FAKE_CONTENT = b"hello from agent"
    _OUTPUT_PATH = "/output"

    async def fake_exec(*args, **kwargs):
        cmd = list(args)
        exit_code = 0
        stdout = b""
        stderr = b""

        if not cmd:
            return await _make_mock_proc(exit_code, stdout, stderr)

        if cmd[0] == "podman":
            subcmd = cmd[1] if len(cmd) > 1 else ""

            if subcmd == "run":
                stdout = (container_id + "\n").encode()

            elif subcmd == "exec":
                if "test" in cmd:
                    # Output path existence check — path exists.
                    exit_code = 0
                elif "find" in cmd:
                    # File listing — return one regular file.
                    stdout = f"{_OUTPUT_PATH}/{_FAKE_FILE}\n".encode()
                # All other exec calls (id -u for priv-esc monitor, etc.) succeed.

            elif subcmd == "cp":
                # Per-file copy: ``podman cp container:/output/result.txt /host/path``
                src = cmd[2]  # "container_id:/output/result.txt"
                dest_str = cmd[3]
                src_is_container = ":" in src and src.index(":") != 1
                if src_is_container:
                    dest = Path(dest_str)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(_FAKE_CONTENT)

            elif subcmd == "rm":
                exit_code = 0

        return await _make_mock_proc(exit_code, stdout, stderr)

    return fake_exec


def _make_fake_podman_exec_no_output(container_id: str = "test-container-abc123"):
    """Variant where the output path does NOT exist in the container."""
    async def fake_exec(*args, **kwargs):
        cmd = list(args)
        exit_code = 0
        stdout = b""
        stderr = b""

        if cmd and cmd[0] == "podman":
            subcmd = cmd[1] if len(cmd) > 1 else ""

            if subcmd == "run":
                stdout = (container_id + "\n").encode()

            elif subcmd == "exec" and "test" in cmd:
                # output path does NOT exist
                exit_code = 1

            elif subcmd == "rm":
                exit_code = 0

        return await _make_mock_proc(exit_code, stdout, stderr)

    return fake_exec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def working_dir(tmp_path):
    """A temporary working directory with a sample file."""
    (tmp_path / "input.txt").write_text("test input")
    return tmp_path


@pytest.fixture(autouse=True)
def reset_session_manager():
    """Reset the module-level SessionManager between tests to avoid state leakage."""
    # Patch atexit and signal so handlers don't accumulate across tests
    with patch("atexit.register"), patch("signal.signal"):
        yield
    # Clear the shared session manager registry
    sdk._session_manager._registry.clear()
    sdk._session_manager._handlers_registered = False


# ---------------------------------------------------------------------------
# 1. End-to-end happy path — run_agent() returns AgentResult (Req 6.1, 6.5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunAgentHappyPath:
    """run_agent() should complete successfully and return an AgentResult."""

    async def test_returns_agent_result(self, working_dir):
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        assert isinstance(result, AgentResult)

    async def test_exit_code_zero_on_success(self, working_dir):
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        assert result.exit_code == 0

    async def test_session_id_is_set_in_result(self, working_dir):
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        assert result.session_id
        assert isinstance(result.session_id, str)

    async def test_artifacts_returned_from_output_path(self, working_dir):
        """Output files from the container's /output path appear in AgentResult.artifacts."""
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        assert "result.txt" in result.artifacts
        # artifacts[filename] is now the host path as a string
        artifact_path = Path(result.artifacts["result.txt"])
        assert artifact_path.exists()
        assert artifact_path.read_bytes() == b"hello from agent"

    async def test_run_agent_with_explicit_policy(self, working_dir):
        """run_agent() accepts an explicit Policy and completes successfully."""
        policy = Policy(cpu_cores=2.0, memory_mb=1024)
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir, policy=policy)

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0

    async def test_artifacts_written_to_host_output_path(self, working_dir, tmp_path):
        """When host_output_path is provided, artifact files persist on disk after the call."""
        host_out = tmp_path / "agent_output"
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir, host_output_path=host_out)

        # Artifacts in memory (now as paths)
        assert "result.txt" in result.artifacts
        artifact_path = Path(result.artifacts["result.txt"])
        assert artifact_path.exists()
        assert artifact_path.read_bytes() == b"hello from agent"
        # Files also present on disk at the caller-specified path
        assert (host_out / "result.txt").exists()
        assert (host_out / "result.txt").read_bytes() == b"hello from agent"


# ---------------------------------------------------------------------------
# 2. Output artifacts returned correctly (Req 6.5, 7.1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOutputArtifacts:
    """AgentResult.artifacts must reflect files at the container output path."""

    async def test_empty_artifacts_when_output_path_missing(self, working_dir):
        """When the container output path doesn't exist, artifacts is empty (Req 7.2)."""
        fake_exec = _make_fake_podman_exec_no_output()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        assert result.artifacts == {}

    async def test_artifacts_contain_file_paths(self, working_dir):
        """Artifact values are the host file paths of the output files."""
        fake_exec = _make_fake_podman_exec()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        for name, path in result.artifacts.items():
            assert isinstance(name, str)
            assert isinstance(path, str)
            assert Path(path).exists()

    async def test_non_zero_exit_code_still_returns_result(self, working_dir):
        """A non-zero exit code is propagated; result is still returned (Req 6.5)."""
        async def fake_exec_fail(*args, **kwargs):
            cmd = list(args)
            if "podman" in cmd and "run" in cmd:
                 return await _make_mock_proc(0, b"cid\n")
            return await _make_mock_proc(1)

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec_fail), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            result = await async_run_agent(_trivial_agent, working_dir)

        assert isinstance(result, AgentResult)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# 3. Session cleanup after completion (Req 9.1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSessionCleanup:
    """The container must be destroyed and the session removed after every run."""

    async def test_container_destroyed_after_successful_run(self, working_dir):
        """podman rm -f is called after a successful agent run."""
        rm_calls: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            cmd = list(args)
            exit_code = 0
            stdout = b""
            if cmd and cmd[0] == "podman":
                if cmd[1] == "run":
                    stdout = b"container-cleanup-test\n"
                elif cmd[1] == "exec" and "test" in cmd:
                    exit_code = 1  # no output path
                elif cmd[1] == "rm":
                    rm_calls.append(list(cmd))
            return await _make_mock_proc(exit_code, stdout)

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            await async_run_agent(_trivial_agent, working_dir)

        assert any("rm" in cmd for cmd in rm_calls), "podman rm should have been called"
        assert any("container-cleanup-test" in cmd for cmd in rm_calls)

    async def test_container_destroyed_after_failed_run(self, working_dir):
        """podman rm -f is called even when the agent exits with a non-zero code."""
        rm_calls: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            cmd = list(args)
            exit_code = 0
            stdout = b""
            if cmd and cmd[0] == "podman":
                if cmd[1] == "run":
                    stdout = b"container-fail-test\n"
                elif cmd[1] == "exec" and "test" in cmd:
                    exit_code = 1
                elif cmd[1] == "rm":
                    rm_calls.append(list(cmd))
            # Simulate failure for runner
            if "podman" in cmd and "exec" in cmd and "python3" in cmd:
                exit_code = 1
            return await _make_mock_proc(exit_code, stdout)

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            await async_run_agent(_trivial_agent, working_dir)

        assert any("container-fail-test" in cmd for cmd in rm_calls)

    async def test_session_removed_from_registry_after_completion(self, working_dir):
        """After run_agent() returns, list_sessions() should not include the session."""
        fake_exec = _make_fake_podman_exec_no_output()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            await async_run_agent(_trivial_agent, working_dir)

        assert sdk.list_sessions() == []

    async def test_container_destroyed_even_when_output_collection_raises(self, working_dir):
        """Container cleanup happens in the finally block even if OutputCollector raises."""
        rm_calls: list[list[str]] = []

        async def fake_exec(*args, **kwargs):
            cmd = list(args)
            exit_code = 0
            stdout = b""
            if cmd and cmd[0] == "podman":
                if cmd[1] == "run":
                    stdout = b"container-exc-test\n"
                elif cmd[1] == "exec" and "test" in cmd:
                    exit_code = 1  # no output path → empty artifacts, no raise
                elif cmd[1] == "rm":
                    rm_calls.append(list(cmd))
            return await _make_mock_proc(exit_code, stdout)

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            await async_run_agent(_trivial_agent, working_dir)

        assert any("container-exc-test" in cmd for cmd in rm_calls)


# ---------------------------------------------------------------------------
# 4. Error paths — pre-launch failures (Req 6.1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPreLaunchErrors:
    """Errors before container creation must propagate cleanly."""

    async def test_podman_not_found_raises_before_execution(self, working_dir):
        """PodmanNotFoundError is raised when Podman is absent from PATH."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(PodmanNotFoundError):
                await async_run_agent(_trivial_agent, working_dir)

    async def test_missing_working_dir_raises_working_directory_error(self, tmp_path):
        """WorkingDirectoryError is raised for a non-existent working directory."""
        missing = tmp_path / "does_not_exist"
        with patch("shutil.which", return_value="/usr/bin/podman"):
            with pytest.raises(WorkingDirectoryError):
                await async_run_agent(_trivial_agent, missing)

    async def test_invalid_policy_raises_policy_validation_error(self, working_dir):
        """PolicyValidationError is raised for a policy with an unknown field."""
        with pytest.raises((PolicyValidationError, TypeError)):
            # Passing a dict with an unknown field via from_json
            bad_policy_json = '{"unknown_field": 42}'
            bad_policy = Policy.from_json(bad_policy_json)
            await async_run_agent(_trivial_agent, working_dir, policy=bad_policy)

    async def test_no_container_created_when_working_dir_missing(self, tmp_path):
        """No podman run is called when the working directory doesn't exist."""
        missing = tmp_path / "no_such_dir"
        run_calls: list = []

        async def fake_exec(*args, **kwargs):
            cmd = list(args)
            run_calls.append(cmd)
            return await _make_mock_proc(0, b"cid\n")

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            with pytest.raises(WorkingDirectoryError):
                await async_run_agent(_trivial_agent, missing)

        podman_run_calls = [c for c in run_calls if len(c) > 1 and c[:2] == ["podman", "run"]]
        assert podman_run_calls == [], "podman run should not be called when working dir is missing"


# ---------------------------------------------------------------------------
# 5. list_sessions() reflects active sessions (Req 9.3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListSessions:
    """list_sessions() must return an empty list when no sessions are active."""

    async def test_list_sessions_empty_initially(self):
        assert sdk.list_sessions() == []

    async def test_list_sessions_empty_after_run_completes(self, working_dir):
        """After run_agent() returns, list_sessions() is empty."""
        fake_exec = _make_fake_podman_exec_no_output()

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            mock_cp.dumps.return_value = b"serialised"
            await async_run_agent(_trivial_agent, working_dir)

        assert sdk.list_sessions() == []
