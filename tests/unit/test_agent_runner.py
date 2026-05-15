"""Unit tests for AgentRunner.

Requirements: 2.3, 6.2
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Callable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import cloudpickle

from isolated_agents_sdk.agent_runner import (
    AgentRunner,
    _CONTAINER_BOOTSTRAP_PATH,
    _CONTAINER_OUTPUT_PATH,
    _CONTAINER_SOURCE_PATH,
)
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.container_provisioner import ContainerHandle
from isolated_agents_sdk.models import AgentResult, Policy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class CapturingLogger(AuditLogger):
    """AuditLogger subclass that records emitted events for assertions."""

    def __init__(self):
        super().__init__()
        self.events: list[dict] = []

    def log_event(self, event_type, session_id, agent_id, payload):
        self.events.append(
            {
                "event_type": event_type,
                "session_id": session_id,
                "agent_id": agent_id,
                "payload": payload,
            }
        )


def _make_runner(container_id: str = "cid123", logger: AuditLogger | None = None) -> AgentRunner:
    handle = ContainerHandle(container_id=container_id)
    return AgentRunner(handle, audit_logger=logger or CapturingLogger())


async def _make_mock_proc(exit_code: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    """Return a mock asyncio subprocess that finishes immediately."""
    proc = MagicMock()
    
    # Make communicate() awaitable
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    
    # Make wait() awaitable
    proc.wait = AsyncMock(return_value=exit_code)
    
    proc.returncode = exit_code
    
    # Mock stream readers for stdout/stderr
    mock_stdout = MagicMock(spec=asyncio.StreamReader)
    mock_stdout.read = AsyncMock()
    mock_stdout.read.side_effect = [stdout, b""]
    proc.stdout = mock_stdout
    
    mock_stderr = MagicMock(spec=asyncio.StreamReader)
    mock_stderr.read = AsyncMock()
    mock_stderr.read.side_effect = [stderr, b""]
    proc.stderr = mock_stderr
    
    return proc


def _simple_agent():
    return None


# ---------------------------------------------------------------------------
# Source serialisation (_inject_source)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestInjectSource:
    async def test_cloudpickle_dump_called_with_agent(self):
        runner = _make_runner()
        agent = _simple_agent

        with patch("isolated_agents_sdk.agent_runner.cloudpickle.dump") as mock_dump:
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = await _make_mock_proc(exit_code=0)
                await runner._inject_source(agent, "cid123")

        mock_dump.assert_called_once()
        # _inject_source now serialises a payload dict {"fn": agent, "args": ..., "kwargs": ...}
        # so the first argument to dump is the dict, not the bare callable.
        payload = mock_dump.call_args[0][0]
        assert isinstance(payload, dict), f"Expected dict payload, got {type(payload)}"
        assert payload["fn"] is agent, "payload['fn'] must be the agent callable"
        assert "args" in payload
        assert "kwargs" in payload

    async def test_podman_cp_called_with_correct_destination(self):
        runner = _make_runner()
        agent = _simple_agent

        with patch("isolated_agents_sdk.agent_runner.cloudpickle.dump"):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = await _make_mock_proc(exit_code=0)
                await runner._inject_source(agent, "cid123")

        args = mock_exec.call_args[0]
        assert args[0] == "podman"
        assert args[1] == "cp"
        assert args[3] == f"cid123:{_CONTAINER_SOURCE_PATH}"

    async def test_temp_file_cleaned_up_after_copy(self):
        runner = _make_runner()
        agent = _simple_agent

        with patch("isolated_agents_sdk.agent_runner.cloudpickle.dump"):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = await _make_mock_proc(exit_code=0)
                with patch("tempfile.NamedTemporaryFile") as mock_ntf:
                    tmp_mock = MagicMock()
                    tmp_mock.__enter__ = lambda s: s
                    tmp_mock.__exit__ = MagicMock(return_value=False)
                    tmp_mock.name = "/tmp/fake_source.pkl"
                    mock_ntf.return_value = tmp_mock

                    with patch("isolated_agents_sdk.agent_runner.Path") as mock_path:
                        path_instance = MagicMock()
                        mock_path.return_value = path_instance
                        await runner._inject_source(agent, "cid123")

        path_instance.unlink.assert_called_once_with(missing_ok=True)


# ---------------------------------------------------------------------------
# Bootstrap script generation (_inject_bootstrap)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestInjectBootstrap:
    async def test_script_contains_correct_source_path(self):
        runner = _make_runner()
        captured_script: list[str] = []

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=0)
            with patch("tempfile.NamedTemporaryFile") as mock_ntf:
                tmp_mock = MagicMock()
                tmp_mock.__enter__ = lambda s: s
                tmp_mock.__exit__ = MagicMock(return_value=False)
                tmp_mock.name = "/tmp/fake_bootstrap.py"

                def capture_write(content):
                    if isinstance(content, str):
                        captured_script.append(content)
                    else:
                        captured_script.append(content.decode())

                tmp_mock.write = capture_write
                mock_ntf.return_value = tmp_mock

                with patch("isolated_agents_sdk.agent_runner.Path"):
                    await runner._inject_bootstrap("cid123")

        script = "".join(captured_script)
        assert repr(_CONTAINER_SOURCE_PATH) in script

    async def test_script_contains_correct_output_path(self):
        runner = _make_runner()
        captured_script: list[str] = []

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=0)
            with patch("tempfile.NamedTemporaryFile") as mock_ntf:
                tmp_mock = MagicMock()
                tmp_mock.__enter__ = lambda s: s
                tmp_mock.__exit__ = MagicMock(return_value=False)
                tmp_mock.name = "/tmp/fake_bootstrap.py"
                tmp_mock.write = lambda c: captured_script.append(c if isinstance(c, str) else c.decode())
                mock_ntf.return_value = tmp_mock

                with patch("isolated_agents_sdk.agent_runner.Path"):
                    await runner._inject_bootstrap("cid123")

        script = "".join(captured_script)
        assert repr(_CONTAINER_OUTPUT_PATH) in script

    async def test_podman_cp_called_with_correct_destination(self):
        runner = _make_runner()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=0)
            with patch("tempfile.NamedTemporaryFile") as mock_ntf:
                tmp_mock = MagicMock()
                tmp_mock.__enter__ = lambda s: s
                tmp_mock.__exit__ = MagicMock(return_value=False)
                tmp_mock.name = "/tmp/fake_bootstrap.py"
                tmp_mock.write = lambda c: None
                mock_ntf.return_value = tmp_mock

                with patch("isolated_agents_sdk.agent_runner.Path"):
                    await runner._inject_bootstrap("cid123")

        args = mock_exec.call_args[0]
        assert args[0] == "podman"
        assert args[1] == "cp"
        assert args[3] == f"cid123:{_CONTAINER_BOOTSTRAP_PATH}"

    async def test_temp_file_cleaned_up_after_copy(self):
        runner = _make_runner()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=0)
            with patch("tempfile.NamedTemporaryFile") as mock_ntf:
                tmp_mock = MagicMock()
                tmp_mock.__enter__ = lambda s: s
                tmp_mock.__exit__ = MagicMock(return_value=False)
                tmp_mock.name = "/tmp/fake_bootstrap.py"
                tmp_mock.write = lambda c: None
                mock_ntf.return_value = tmp_mock

                with patch("isolated_agents_sdk.agent_runner.Path") as mock_path:
                    path_instance = MagicMock()
                    mock_path.return_value = path_instance
                    await runner._inject_bootstrap("cid123")

        path_instance.unlink.assert_called_once_with(missing_ok=True)


# ---------------------------------------------------------------------------
# run() — audit event on launch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunAuditEvent:
    async def test_agent_launched_event_emitted(self):
        logger = CapturingLogger()
        runner = _make_runner(container_id="cid42", logger=logger)
        
        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    mock_exec.return_value = await _make_mock_proc(exit_code=0)
                    await runner.run(_simple_agent, Policy(), "sess1", "agent1")

        launched = [e for e in logger.events if e["event_type"] == "agent_launched"]
        assert len(launched) == 1
        evt = launched[0]
        assert evt["session_id"] == "sess1"
        assert evt["agent_id"] == "agent1"
        assert evt["payload"]["container_id"] == "cid42"


# ---------------------------------------------------------------------------
# run() — normal completion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunNormalCompletion:
    async def test_exit_code_zero_returns_correct_result(self):
        logger = CapturingLogger()
        runner = _make_runner(container_id="cid1", logger=logger)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    mock_exec.return_value = await _make_mock_proc(exit_code=0)
                    result = await runner.run(_simple_agent, Policy(), "sess-ok", "agent-ok")

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0
        assert result.session_id == "sess-ok"

    async def test_result_artifacts_is_empty_dict(self):
        runner = _make_runner()

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    mock_exec.return_value = await _make_mock_proc(exit_code=0)
                    result = await runner.run(_simple_agent, Policy(), "s", "a")

        assert result.artifacts == {}


# ---------------------------------------------------------------------------
# run() — non-zero exit code
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunNonZeroExitCode:
    async def test_exit_code_one_propagated(self):
        runner = _make_runner()

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    mock_exec.return_value = await _make_mock_proc(exit_code=1)
                    result = await runner.run(_simple_agent, Policy(), "s", "a")

        assert result.exit_code == 1

    async def test_non_zero_exit_code_propagated(self):
        runner = _make_runner()

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    mock_exec.return_value = await _make_mock_proc(exit_code=42)
                    result = await runner.run(_simple_agent, Policy(), "s", "a")

        assert result.exit_code == 42

    async def test_oom_kill_detection(self):
        logger = CapturingLogger()
        runner = _make_runner(logger=logger)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    # Exit code 137 is standard for OOM Kill (128 + 9)
                    mock_exec.return_value = await _make_mock_proc(exit_code=137)
                    await runner.run(_simple_agent, Policy(), "s-oom", "a-oom")

        oom_events = [e for e in logger.events if e["event_type"] == "resource_limit_exceeded"]
        assert len(oom_events) == 1
        payload = oom_events[0]["payload"]
        assert payload["violation_type"] == "oom_kill"
        assert "OOM Kill" in payload["reason"]
