"""Unit tests for AgentRunner.

Requirements: 2.3, 6.2
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import ContainerHandle, ExecResult
from isolated_agents_sdk.agent_runner import AgentRunner
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.models import (
    CONTAINER_BOOTSTRAP_PATH,
    CONTAINER_SOURCE_PATH,
    AgentResult,
    Policy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CapturingLogger(AuditLogger):
    """AuditLogger subclass that records emitted events for assertions."""

    def __init__(self):
        super().__init__()
        self.events: list[dict] = []

    async def log_event(self, event_type, session_id, agent_id, payload):
        self.events.append(
            {
                "event_type": event_type,
                "session_id": session_id,
                "agent_id": agent_id,
                "payload": payload,
            }
        )


async def _make_mock_adapter():
    adapter = MagicMock(spec=ContainerRuntimeAdapter)
    adapter.exec_in_container = AsyncMock(
        return_value=ExecResult(exit_code=0, stdout="", stderr="")
    )
    adapter.copy_to_container = AsyncMock()
    adapter.get_adapter_name = MagicMock(return_value="MockAdapter")
    return adapter


def _make_runner(
    container_id: str = "cid123", logger: AuditLogger | None = None, adapter=None
) -> AgentRunner:
    handle = ContainerHandle(container_id=container_id)
    return AgentRunner(handle, audit_logger=logger or CapturingLogger(), adapter=adapter)


def _simple_agent():
    return None


# ---------------------------------------------------------------------------
# Source serialisation (_inject_source)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInjectSource:
    async def test_cloudpickle_dump_called_with_agent(self):
        adapter = await _make_mock_adapter()
        runner = _make_runner(adapter=adapter)
        agent = _simple_agent

        with patch("isolated_agents_sdk.agent_runner.cloudpickle.dump") as mock_dump:
            await runner._inject_source(agent, "cid123")

        mock_dump.assert_called_once()
        payload = mock_dump.call_args[0][0]
        assert isinstance(payload, dict)
        assert payload["fn"] is agent

    async def test_adapter_copy_called_with_correct_destination(self):
        adapter = await _make_mock_adapter()
        runner = _make_runner(adapter=adapter)
        agent = _simple_agent

        with patch("isolated_agents_sdk.agent_runner.cloudpickle.dump"):
            await runner._inject_source(agent, "cid123")

        adapter.copy_to_container.assert_called_once()
        args = adapter.copy_to_container.call_args.args
        assert args[0] == "cid123"
        assert args[2] == CONTAINER_SOURCE_PATH

    async def test_temp_file_cleaned_up_after_copy(self):
        adapter = await _make_mock_adapter()
        runner = _make_runner(adapter=adapter)
        agent = _simple_agent

        with patch("isolated_agents_sdk.agent_runner.cloudpickle.dump"):
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
        adapter = await _make_mock_adapter()
        runner = _make_runner(adapter=adapter)
        captured_script: list[str] = []

        with patch("tempfile.NamedTemporaryFile") as mock_ntf:
            tmp_mock = MagicMock()
            tmp_mock.__enter__ = lambda s: s
            tmp_mock.__exit__ = MagicMock(return_value=False)
            tmp_mock.name = "/tmp/fake_bootstrap.py"
            tmp_mock.write = lambda c: captured_script.append(
                c if isinstance(c, str) else c.decode()
            )
            mock_ntf.return_value = tmp_mock

            await runner._inject_bootstrap("cid123")

        script = "".join(captured_script)
        assert repr(CONTAINER_SOURCE_PATH) in script

    async def test_adapter_copy_called_with_correct_destination(self):
        adapter = await _make_mock_adapter()
        runner = _make_runner(adapter=adapter)

        with patch("tempfile.NamedTemporaryFile") as mock_ntf:
            tmp_mock = MagicMock()
            tmp_mock.__enter__ = lambda s: s
            tmp_mock.__exit__ = MagicMock(return_value=False)
            tmp_mock.name = "/tmp/fake_bootstrap.py"
            tmp_mock.write = lambda c: None
            mock_ntf.return_value = tmp_mock

            await runner._inject_bootstrap("cid123")

        adapter.copy_to_container.assert_called_once()
        args = adapter.copy_to_container.call_args.args
        assert args[0] == "cid123"
        assert args[2] == CONTAINER_BOOTSTRAP_PATH


# ---------------------------------------------------------------------------
# run() — audit event on launch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRunAuditEvent:
    async def test_agent_launched_event_emitted(self):
        logger = CapturingLogger()
        adapter = await _make_mock_adapter()
        runner = _make_runner(container_id="cid42", logger=logger, adapter=adapter)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
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
        adapter = await _make_mock_adapter()
        runner = _make_runner(container_id="cid1", logger=logger, adapter=adapter)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                result = await runner.run(_simple_agent, Policy(), "sess-ok", "agent-ok")

        assert isinstance(result, AgentResult)
        assert result.exit_code == 0
        assert result.session_id == "sess-ok"

    async def test_result_artifacts_is_empty_dict(self):
        adapter = await _make_mock_adapter()
        runner = _make_runner(adapter=adapter)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                result = await runner.run(_simple_agent, Policy(), "s", "a")

        assert result.artifacts == {}


# ---------------------------------------------------------------------------
# run() — non-zero exit code
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRunNonZeroExitCode:
    async def test_exit_code_one_propagated(self):
        adapter = await _make_mock_adapter()

        async def fake_exec(container_id, command, **kwargs):
            if "pip" in command:
                return ExecResult(exit_code=0, stdout="", stderr="")
            return ExecResult(exit_code=1, stdout="", stderr="")

        adapter.exec_in_container.side_effect = fake_exec
        runner = _make_runner(adapter=adapter)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                result = await runner.run(_simple_agent, Policy(), "s", "a")

        assert result.exit_code == 1

    async def test_non_zero_exit_code_propagated(self):
        adapter = await _make_mock_adapter()

        async def fake_exec(container_id, command, **kwargs):
            if "pip" in command:
                return ExecResult(exit_code=0, stdout="", stderr="")
            return ExecResult(exit_code=42, stdout="", stderr="")

        adapter.exec_in_container.side_effect = fake_exec
        runner = _make_runner(adapter=adapter)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                result = await runner.run(_simple_agent, Policy(), "s", "a")

        assert result.exit_code == 42

    async def test_oom_kill_detection(self):
        logger = CapturingLogger()
        adapter = await _make_mock_adapter()

        async def fake_exec(container_id, command, **kwargs):
            if "pip" in command:
                return ExecResult(exit_code=0, stdout="", stderr="")
            return ExecResult(exit_code=137, stdout="", stderr="")

        adapter.exec_in_container.side_effect = fake_exec
        runner = _make_runner(logger=logger, adapter=adapter)

        with patch.object(runner, "_inject_source"):
            with patch.object(runner, "_inject_bootstrap"):
                await runner.run(_simple_agent, Policy(), "s-oom", "a-oom")

        oom_events = [e for e in logger.events if e["event_type"] == "resource_limit_exceeded"]
        assert len(oom_events) == 1
        payload = oom_events[0]["payload"]
        assert payload["violation_type"] == "oom_kill"
        assert "OOM Kill" in payload["reason"]
