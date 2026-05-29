"""Unit tests for ContainerProvisioner."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.container_provisioner import ContainerHandle, ContainerProvisioner
from isolated_agents_sdk.exceptions import ContainerError, WorkingDirectoryError
from isolated_agents_sdk.models import Policy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_mock_adapter():
    adapter = MagicMock(spec=ContainerRuntimeAdapter)
    adapter.initialize = AsyncMock()
    adapter.cleanup = AsyncMock()
    adapter.health_check = AsyncMock(return_value=True)
    adapter.get_adapter_name = MagicMock(return_value="MockAdapter")
    adapter.provision_container = AsyncMock(
        return_value=ContainerHandle(container_id="cid123", image="img")
    )
    return adapter


def _provisioner(adapter=None) -> ContainerProvisioner:
    return ContainerProvisioner(adapter=adapter)


def _default_policy() -> Policy:
    return Policy()


# ---------------------------------------------------------------------------
# _check_podman
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCheckPodman:
    async def test_raises_when_adapter_init_fails(self, tmp_path):
        adapter = await _make_mock_adapter()
        adapter.initialize.side_effect = Exception("Init failed")
        p = _provisioner(adapter=adapter)
        with pytest.raises(ContainerError):
            await p.provision(tmp_path, _default_policy(), "s1", "a1")

    async def test_no_error_when_adapter_healthy(self, tmp_path):
        adapter = await _make_mock_adapter()
        p = _provisioner(adapter=adapter)
        handle = await p.provision(tmp_path, _default_policy(), "s1", "a1")
        assert handle.container_id == "cid123"
        adapter.provision_container.assert_called_once()


# ---------------------------------------------------------------------------
# Working directory validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWorkingDirectory:
    async def test_raises_for_nonexistent_directory(self, tmp_path):
        p = _provisioner()
        missing = tmp_path / "does_not_exist"
        with pytest.raises(WorkingDirectoryError):
            await p.provision(missing, _default_policy(), "s1", "a1")

    async def test_accepts_existing_directory(self, tmp_path):
        adapter = await _make_mock_adapter()
        p = _provisioner(adapter=adapter)
        handle = await p.provision(tmp_path, _default_policy(), "s1", "a1")
        assert isinstance(handle, ContainerHandle)


# ---------------------------------------------------------------------------
# build_command — isolation flags
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Provision Delegation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestProvisionDelegation:
    async def test_delegates_to_adapter_with_correct_params(self, tmp_path):
        adapter = await _make_mock_adapter()
        p = _provisioner(adapter=adapter)

        policy = Policy(
            cpu_cores=2.0, memory_mb=1024, readonly_mounts=["/etc/test"], allowed_env_vars=["VAR1"]
        )

        with patch.dict(os.environ, {"VAR1": "val1"}):
            await p.provision(tmp_path, policy, "s1", "a1")

        adapter.provision_container.assert_called_once()
        kwargs = adapter.provision_container.call_args.kwargs

        assert kwargs["resources"].cpu_cores == 2.0
        assert kwargs["resources"].memory_mb == 1024
        assert any(m.source == "/etc/test" and m.readonly for m in kwargs["mounts"])
        assert kwargs["env"]["VAR1"] == "val1"
        assert kwargs["working_dir"] == "/workspace"


# ---------------------------------------------------------------------------
# ContainerHandle
# ---------------------------------------------------------------------------


class TestContainerHandle:
    def test_has_container_id(self):
        handle = ContainerHandle(container_id="abc123")
        assert handle.container_id == "abc123"


# ---------------------------------------------------------------------------
# Audit event on provision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuditEvent:
    async def test_container_created_event_emitted(self, tmp_path):
        from isolated_agents_sdk.audit_logger import AuditLogger

        emitted = []

        class CapturingLogger(AuditLogger):
            async def log_event(self, event_type, session_id, agent_id, payload):
                emitted.append((event_type, session_id, agent_id, payload))

        adapter = await _make_mock_adapter()
        p = ContainerProvisioner(adapter=adapter, audit_logger=CapturingLogger())
        await p.provision(tmp_path, _default_policy(), "sess1", "agent1")

        assert len(emitted) == 1
        event_type, session_id, agent_id, payload = emitted[0]
        assert event_type == "container_created"
        assert session_id == "sess1"
        assert agent_id == "agent1"
        assert payload["container_id"] == "cid123"
