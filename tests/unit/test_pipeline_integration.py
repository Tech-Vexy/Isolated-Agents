"""Integration tests for the Isolated Agents SDK pipeline.

Verifies:
- Happy path execution
- Artifact collection
- Resource limiting
- Session lifecycle
- Error handling
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

import isolated_agents_sdk as sdk
from isolated_agents_sdk import (
    AgentResult,
    Policy,
    async_run_agent,
    get_adapter_registry,
    configure_adapters,
)
from isolated_agents_sdk.adapters import AdapterRegistry
from isolated_agents_sdk.exceptions import PodmanNotFoundError, WorkingDirectoryError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_mock_proc(exit_code: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    """Return a mock asyncio subprocess that finishes immediately."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.wait = AsyncMock(return_value=exit_code)
    proc.returncode = exit_code

    # Mock stdout/stderr as stream readers
    proc.stdout = MagicMock()
    proc.stdout.read = AsyncMock(side_effect=[stdout, b""])
    proc.stderr = MagicMock()
    proc.stderr.read = AsyncMock(side_effect=[stderr, b""])

    return proc


def _make_fake_podman_exec(container_id: str = "cid", exit_code_on_exec: int = 0):
    """Return a side_effect function for asyncio.create_subprocess_exec that simulates Podman."""
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
                    exit_code = 0
                elif "find" in cmd:
                    stdout = b"/output/result.txt\n"
                elif "id" in cmd and "-u" in cmd:
                    stdout = b"1000\n"
                else:
                    exit_code = exit_code_on_exec
            elif subcmd == "cp":
                if ":" in cmd[2]: # src is container
                    try:
                        dest = Path(cmd[3])
                        if not dest.parent.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(b"hello from agent")
                    except Exception:
                        pass
                else: # src is host
                    exit_code = 0
            elif subcmd == "rm":
                exit_code = 0
            elif subcmd == "--version":
                stdout = b"podman version 4.6.0\n"
            elif subcmd == "version":
                 stdout = b"podman version 4.6.0\n"

        return await _make_mock_proc(exit_code, stdout, stderr)

    return fake_exec


fake_exec = _make_fake_podman_exec()


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
                exit_code = 1

            elif subcmd == "rm":
                exit_code = 0
            
            elif subcmd == "--version":
                stdout = b"podman version 4.6.0\n"

        return await _make_mock_proc(exit_code, stdout, stderr)

    return fake_exec


@pytest.fixture
def working_dir(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d


def _trivial_agent():
    return 0


@pytest.fixture(autouse=True)
def mock_monitor():
    """Mock the privilege escalation monitor to avoid background hangs."""
    with patch("isolated_agents_sdk.agent_runner.AgentRunner._monitor_privilege_escalation", new_callable=AsyncMock):
        yield


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the global AdapterRegistry between tests."""
    AdapterRegistry.reset_instance()
    yield
    AdapterRegistry.reset_instance()


# ---------------------------------------------------------------------------
# Happy Path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunAgentHappyPath:
    """run_agent() should complete successfully and return an AgentResult."""

    async def test_returns_agent_result(self, working_dir):
        """Happy path: async_run_agent returns an AgentResult (Req 1.1)."""
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0
        assert result.session_id
        assert "result.txt" in result.artifacts

    async def test_exit_code_zero_on_success(self, working_dir):
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        assert result.exit_code == 0

    async def test_session_id_is_set_in_result(self, working_dir):
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        assert result.session_id

    async def test_artifacts_returned_from_output_path(self, working_dir):
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        assert "result.txt" in result.artifacts

    async def test_run_agent_with_explicit_policy(self, working_dir):
        policy = Policy(cpu_cores=0.5, memory_mb=256)
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir, policy=policy)

        assert isinstance(result, AgentResult)

    async def test_artifacts_written_to_host_output_path(self, working_dir, tmp_path):
        host_out = tmp_path / "agent_output"
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir, host_output_path=host_out)

        # Artifacts in memory (now as paths)
        assert "result.txt" in result.artifacts
        artifact_path = Path(result.artifacts["result.txt"])
        assert artifact_path.exists()
        assert artifact_path.read_bytes() == b"hello from agent"
        # Files are present on disk at the location returned in artifacts
        assert str(host_out) in str(artifact_path)


# ---------------------------------------------------------------------------
# Output Artifacts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOutputArtifacts:
    """Artifact collection logic and constraints."""

    async def test_no_artifacts_if_output_dir_missing(self, working_dir):
        """Result artifacts are empty if the container's output dir is missing."""
        fake_exec_no_out = _make_fake_podman_exec_no_output()
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec_no_out), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        assert result.artifacts == {}

    async def test_artifacts_contain_file_paths(self, working_dir):
        """Returned artifacts map names to local file paths (Req 6.1)."""
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        for name, path in result.artifacts.items():
            assert os.path.isabs(path)
            assert os.path.exists(path)

    async def test_non_zero_exit_code_still_returns_result(self, working_dir):
        """A non-zero exit code is propagated; result is still returned (Req 6.5)."""
        fake_exec_fail = _make_fake_podman_exec(exit_code_on_exec=1)

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec_fail), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            result = await async_run_agent(_trivial_agent, working_dir)

        assert isinstance(result, AgentResult)
        assert result.exit_code == 1
        assert result.session_id


# ---------------------------------------------------------------------------
# Session Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSessionCleanup:
    """Ensuring containers are removed even on failure."""

    async def test_container_destroyed_after_successful_run(self, working_dir):
        rm_calls = []
        async def spy_exec(*args, **kwargs):
            if "rm" in args:
                rm_calls.append(args)
            return await fake_exec(*args, **kwargs)

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=spy_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            await async_run_agent(_trivial_agent, working_dir)

        assert any("rm" in cmd for cmd in rm_calls), "podman rm should have been called"

    async def test_container_destroyed_after_failed_run(self, working_dir):
        rm_calls = []
        async def spy_exec(*args, **kwargs):
            if "rm" in args:
                rm_calls.append(args)
            return await fake_exec(*args, **kwargs)

        def failing_agent():
            raise RuntimeError("Agent failed")

        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=spy_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            try:
                await async_run_agent(failing_agent, working_dir)
            except RuntimeError:
                pass

        assert any("rm" in cmd for cmd in rm_calls)

    async def test_session_removed_from_registry_after_completion(self, working_dir):
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            await async_run_agent(_trivial_agent, working_dir)

        assert sdk.list_sessions() == []

    async def test_container_destroyed_even_when_output_collection_raises(self, working_dir):
        rm_calls = []
        async def spy_exec(*args, **kwargs):
            if "rm" in args:
                rm_calls.append(args)
            return await fake_exec(*args, **kwargs)

        # Patch OutputCollector.collect to raise an exception
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=spy_exec), \
             patch("isolated_agents_sdk.output_collector.OutputCollector.collect", side_effect=Exception("Collect error")), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            try:
                await async_run_agent(_trivial_agent, working_dir)
            except Exception:
                pass

        assert any("rm" in cmd for cmd in rm_calls)


# ---------------------------------------------------------------------------
# Pre-launch Errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPreLaunchErrors:
    """Errors that occur before the container starts."""

    async def test_podman_not_found_raises_before_execution(self, working_dir):
        """PodmanNotFoundError is raised when Podman is absent from PATH."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(PodmanNotFoundError):
                await async_run_agent(_trivial_agent, working_dir)

    async def test_missing_working_dir_raises_working_directory_error(self, tmp_path):
        """WorkingDirectoryError is raised if the provided path doesn't exist."""
        missing_dir = tmp_path / "non-existent"
        with pytest.raises(WorkingDirectoryError):
            await async_run_agent(_trivial_agent, missing_dir)

    async def test_no_container_created_when_working_dir_missing(self, tmp_path):
        """No podman commands should be run if basic validation fails."""
        missing_dir = tmp_path / "non-existent"
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            try:
                await async_run_agent(_trivial_agent, missing_dir)
            except WorkingDirectoryError:
                pass
            assert not mock_exec.called


# ---------------------------------------------------------------------------
# List Sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListSessions:
    """Listing active sessions."""

    async def test_list_sessions_empty_initially(self):
        assert sdk.list_sessions() == []

    async def test_list_sessions_empty_after_run_completes(self, working_dir):
        with patch("shutil.which", return_value="/usr/bin/podman"), \
             patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("isolated_agents_sdk.agent_runner.cloudpickle") as mock_cp:
            await async_run_agent(_trivial_agent, working_dir)

        assert sdk.list_sessions() == []
