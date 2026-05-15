"""Tests for Polyglot support and Interactive Workspace features.

Verifies:
- Language Agnosticism (custom entrypoints and base images)
- Iterative Execution (exec_in_session)
- Long-Running Agents (start_agent_daemon and sync_artifact)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from isolated_agents_sdk import (
    Policy,
    async_run_agent,
    start_agent_daemon,
    exec_in_session,
    sync_artifact,
)

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

def _make_fake_podman_exec(container_id: str = "test-container-abc123"):
    """Return a side_effect function for asyncio.create_subprocess_exec that simulates Podman."""
    async def fake_exec(*args, **kwargs):
        cmd = list(args)
        exit_code = 0
        stdout = b""
        stderr = b""

        if cmd[0] == "podman":
            subcmd = cmd[1] if len(cmd) > 1 else ""

            if subcmd == "run":
                stdout = (container_id + "\n").encode()
            elif subcmd == "exec":
                if "node" in cmd:
                    stdout = b"hello from node"
                elif "test" in cmd:
                    exit_code = 0
            elif subcmd == "cp":
                # Simulate artifact sync
                if ":" in cmd[2]: # src is container
                    try:
                        dest = Path(cmd[3])
                        if not dest.parent.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(b"synced artifact")
                    except Exception:
                        pass
            elif subcmd == "rm":
                exit_code = 0

        return await _make_mock_proc(exit_code, stdout, stderr)

    return fake_exec

@pytest.fixture
def working_dir(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return d

@pytest.fixture(autouse=True)
def mock_podman():
    """Automatically mock podman for all tests in this file."""
    fake_exec = _make_fake_podman_exec()
    with patch("shutil.which", return_value="/usr/bin/podman"), \
         patch("asyncio.create_subprocess_exec", side_effect=fake_exec), \
         patch("isolated_agents_sdk.agent_runner.AgentRunner._stream_output", new_callable=AsyncMock):
        yield

# ---------------------------------------------------------------------------
# Polyglot Support
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPolyglotSupport:
    """SDK must support custom entrypoints and base images."""

    async def test_run_agent_with_custom_entrypoint(self, working_dir):
        policy = Policy(
            entrypoint=["node", "agent.js"],
            base_image="node:18-alpine"
        )
        # When entrypoint is set, agent callable can be None
        result = await async_run_agent(None, working_dir, policy)
        assert result.exit_code == 0

    async def test_fails_if_no_agent_and_no_entrypoint(self, working_dir):
        policy = Policy() # No entrypoint
        with pytest.raises(ValueError, match="Agent callable must be provided"):
            await async_run_agent(None, working_dir, policy)

# ---------------------------------------------------------------------------
# Iterative Execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestIterativeExecution:
    """SDK must allow executing commands in an existing session."""

    async def test_exec_in_session(self, working_dir):
        # 1. Start a daemon session
        session = await start_agent_daemon(None, working_dir, Policy(entrypoint=["sleep", "infinity"]))
        
        # 2. Run a command inside it
        exit_code, stdout, stderr = await exec_in_session(session.session_id, ["ls", "-l"])

        assert exit_code == 0
        assert isinstance(stdout, str)

# ---------------------------------------------------------------------------
# Long-Running Agents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestLongRunningAgents:
    """SDK must support background daemons and real-time artifact sync."""

    async def test_start_agent_daemon(self, working_dir):
        session = await start_agent_daemon(None, working_dir, Policy(entrypoint=["sleep", "3600"]))
        assert session.status == "running"
        assert session.container_id == "test-container-abc123"

    async def test_sync_artifact(self, working_dir, tmp_path):
        local_artifact = tmp_path / "synced.txt"
        
        # 1. Start a session
        session = await start_agent_daemon(None, working_dir, Policy(entrypoint=["sleep", "3600"]))
        
        # 2. Sync an artifact
        await sync_artifact(session.session_id, "/workspace/log.txt", local_artifact)

        assert local_artifact.exists()
        assert local_artifact.read_bytes() == b"synced artifact"
