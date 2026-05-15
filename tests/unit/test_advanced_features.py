"""Tests for Advanced SDK features: Xvfb, tmpfs secrets, proxy, and replay."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from isolated_agents_sdk import Policy, ContainerProvisioner, AgentRunner, ContainerHandle

class TestAdvancedFeatures:
    """Verify advanced architectural capabilities."""

    def test_provisioner_builds_tmpfs_mount(self):
        provisioner = ContainerProvisioner()
        policy = Policy(tmpfs_secrets={"API_KEY": "secret123"})
        
        cmd = provisioner.build_command("/tmp/work", policy)
        
        # Check for tmpfs mount
        assert "--mount" in cmd
        assert "type=tmpfs,destination=/run/secrets" in cmd

    @pytest.mark.asyncio
    async def test_agent_runner_injects_secrets(self):
        handle = ContainerHandle(container_id="test-container")
        runner = AgentRunner(handle=handle)
        policy = Policy(tmpfs_secrets={"S1": "V1", "S2": "V2"})
        
        # We need to mock create_subprocess_exec to check the 'podman cp' call
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc
            
            await runner._inject_secrets("test-container", policy.tmpfs_secrets)
            
            # Verify podman cp was called
            calls = mock_exec.call_args_list
            cp_call = next(c for c in calls if c.args[1] == "cp")
            assert cp_call.args[3] == "test-container:/run/secrets/credentials.env"

    @pytest.mark.asyncio
    async def test_agent_runner_sets_proxy_and_xvfb(self):
        handle = ContainerHandle(container_id="test-container")
        runner = AgentRunner(handle=handle)
        policy = Policy(
            proxy_url="http://proxy:8080",
            requires_display=True,
            entrypoint=["my-agent"]
        )
        
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.wait.return_value = 0
            mock_proc.stdout = AsyncMock()
            mock_proc.stdout.read.return_value = b""
            mock_proc.stderr = AsyncMock()
            mock_proc.stderr.read.return_value = b""
            mock_exec.return_value = mock_proc
            
            # Mock _stream_output to avoid hanging on read
            with patch.object(runner, "_stream_output", new_callable=AsyncMock):
                await runner.run(None, policy, "session-1", "agent-1")
            
            # Verify the final command contains proxy and xvfb setup
            calls = mock_exec.call_args_list
            exec_call = next(c for c in calls if c.args[0] == "podman" and c.args[1] == "exec")
            
            cmd_str = " ".join(exec_call.args)
            assert "HTTP_PROXY=http://proxy:8080" in cmd_str
            assert "Xvfb :99" in cmd_str
            assert "DISPLAY=:99" in cmd_str
            assert "sh -c" in cmd_str

    @pytest.mark.asyncio
    async def test_session_replay_recording(self, tmp_path):
        handle = ContainerHandle(container_id="test-container")
        runner = AgentRunner(handle=handle)
        policy = Policy(enable_session_replay=True, entrypoint=["ls"])
        
        # Mock subprocess to produce some output
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.wait = AsyncMock(return_value=0)
            
            # Mock stdout stream
            mock_proc.stdout = AsyncMock()
            mock_proc.stdout.read.side_effect = [b"hello", b" world", b""]
            mock_proc.stderr = AsyncMock()
            mock_proc.stderr.read.side_effect = [b"error", b""]
            
            mock_exec.return_value = mock_proc
            
            # Use a real stream output but mock sys.stdout to avoid polluting test output
            with patch("sys.stdout"), patch("sys.stderr"):
                result = await runner.run(None, policy, "session-replay", "agent-replay")
            
            assert "session_replay.cast" in result.artifacts
            replay_path = result.artifacts["session_replay.cast"]
            assert replay_path.exists()
            
            # Check content
            with open(replay_path, "r") as f:
                lines = f.readlines()
                header = json.loads(lines[0])
                assert header["version"] == 2
                
                # Check for recorded data
                data_found = False
                for line in lines[1:]:
                    entry = json.loads(line)
                    if entry[1] == "o" and "hello" in entry[2]:
                        data_found = True
                        break
                assert data_found
