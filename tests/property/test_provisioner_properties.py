"""Property-based tests for ContainerProvisioner and adapter mapping.

Feature: isolated-agents-sdk
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from isolated_agents_sdk.adapters.container.types import (
    NetworkConfig,
    ResourceLimits,
    SecurityConfig,
)
from isolated_agents_sdk.models import NetworkPolicy, Policy

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

network_policy_strategy = st.builds(
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

policy_strategy = st.builds(
    Policy,
    cpu_cores=st.floats(min_value=0.1, max_value=64.0, allow_nan=False, allow_infinity=False),
    memory_mb=st.integers(min_value=1, max_value=65536),
    network=network_policy_strategy,
    readonly_mounts=st.lists(st.text(min_size=1, max_size=100), max_size=5),
    allowed_env_vars=st.lists(st.text(min_size=1, max_size=50), max_size=10),
    output_path_in_container=st.text(min_size=1, max_size=200),
    max_output_bytes=st.one_of(st.none(), st.integers(min_value=1, max_value=10**9)),
    timeout_seconds=st.one_of(st.none(), st.integers(min_value=1, max_value=86400)),
    log_output_path=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
)


# ---------------------------------------------------------------------------
# Property: Policy to Adapter Mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(policy=policy_strategy)
@settings(max_examples=50, deadline=None)
async def test_policy_to_adapter_mapping(policy: Policy) -> None:
    """Verifies that ContainerProvisioner correctly maps Policy to adapter types."""
    mock_adapter = AsyncMock()
    mock_adapter.initialize = AsyncMock()
    mock_adapter.provision_container = AsyncMock(
        return_value=MagicMock(container_id="cid", image="img")
    )
    mock_adapter.get_adapter_name = MagicMock(return_value="mock")

    import tempfile

    from isolated_agents_sdk.container_provisioner import ContainerProvisioner

    with tempfile.TemporaryDirectory() as tmp_dir:
        working_dir = Path(tmp_dir)

        provisioner = ContainerProvisioner(adapter=mock_adapter)
        await provisioner.provision(
            working_dir=working_dir, policy=policy, session_id="session-123", agent_id="agent-456"
        )

    # Check that provision_container was called with correctly mapped arguments
    args, kwargs = mock_adapter.provision_container.call_args

    resources = kwargs.get("resources")
    assert isinstance(resources, ResourceLimits)
    assert resources.cpu_cores == policy.cpu_cores
    assert resources.memory_mb == policy.memory_mb

    network = kwargs.get("network")
    assert isinstance(network, NetworkConfig)
    assert network.disabled == policy.network.disabled
    assert network.allowed_endpoints == policy.network.allowed_endpoints

    security = kwargs.get("security")
    assert isinstance(security, SecurityConfig)
    # Default security settings
    assert security.read_only_rootfs is True

    mounts = kwargs.get("mounts")
    # Should include working dir and readonly mounts
    mount_paths = [m.source for m in mounts]
    assert str(working_dir) in mount_paths
    for rm in policy.readonly_mounts:
        assert str(rm) in mount_paths
