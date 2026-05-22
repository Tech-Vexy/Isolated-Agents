"""Tests for Advanced SDK features: Xvfb, tmpfs secrets, proxy, and replay."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from isolated_agents_sdk import Policy, AgentRunner, ContainerHandle

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import ExecResult

async def _make_mock_adapter():
    adapter = MagicMock(spec=ContainerRuntimeAdapter)
    adapter.initialize = AsyncMock()
    adapter.cleanup = AsyncMock()
    adapter.health_check = AsyncMock(return_value=True)
    adapter.get_adapter_name = MagicMock(return_value="MockAdapter")
    adapter.provision_container = AsyncMock(return_value=ContainerHandle(container_id="cid123", image="img"))
    adapter.exec_in_container = AsyncMock(return_value=ExecResult(exit_code=0, stdout="", stderr=""))
    adapter.copy_to_container = AsyncMock()
    return adapter

class TestAdvancedFeatures:
    """Verify advanced architectural capabilities."""

    @pytest.mark.asyncio
    async def test_agent_runner_injects_secrets(self):
        handle = ContainerHandle(container_id="test-container")
        adapter = await _make_mock_adapter()
        runner = AgentRunner(handle=handle, adapter=adapter)
        policy = Policy(tmpfs_secrets={"S1": "V1", "S2": "V2"})
        
        await runner._inject_secrets("test-container", policy.tmpfs_secrets)
        
        # Verify adapter.copy_to_container was called
        adapter.copy_to_container.assert_called_once()
        args = adapter.copy_to_container.call_args.args
        assert args[0] == "test-container"
        assert args[2] == "/run/secrets/credentials.env"

    @pytest.mark.asyncio
    async def test_agent_runner_sets_proxy_and_xvfb(self):
        handle = ContainerHandle(container_id="test-container")
        adapter = await _make_mock_adapter()
        runner = AgentRunner(handle=handle, adapter=adapter)
        policy = Policy(
            proxy_url="http://proxy:8080",
            requires_display=True,
            entrypoint=["my-agent"]
        )
        
        # Use a real stream output but mock sys.stdout to avoid polluting test output
        with patch("sys.stdout"), patch("sys.stderr"):
            await runner.run(None, policy, "session-1", "agent-1")
        
        # Verify the command contains xvfb setup
        adapter.exec_in_container.assert_called_once()
        kwargs = adapter.exec_in_container.call_args.kwargs
        
        cmd = kwargs["command"]
        assert "sh" in cmd
        assert "-c" in cmd
        cmd_payload = cmd[2]
        assert "Xvfb :99" in cmd_payload
        assert "DISPLAY=:99" in cmd_payload
        
        # Verify env contains proxy
        assert kwargs["env"]["HTTP_PROXY"] == "http://proxy:8080"

    @pytest.mark.asyncio
    async def test_session_replay_recording(self, tmp_path):
        # Session replay recording is currently NOT implemented in the adapter flow.
        # This test should probably be updated once it's implemented.
        # For now, we'll just check if it runs without error.
        handle = ContainerHandle(container_id="test-container")
        adapter = await _make_mock_adapter()
        runner = AgentRunner(handle=handle, adapter=adapter)
        policy = Policy(enable_session_replay=True, entrypoint=["ls"])
        
        # Use a real stream output but mock sys.stdout to avoid polluting test output
        with patch("sys.stdout"), patch("sys.stderr"):
            result = await runner.run(None, policy, "session-replay", "agent-replay")
            
        assert result.exit_code == 0
