"""Property-based tests for ContainerProvisioner.

Feature: isolated-agents-sdk
"""

from pathlib import Path

from hypothesis import given, settings, strategies as st

from isolated_agents_sdk.container_provisioner import ContainerProvisioner
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
# Property 1: Container isolation flags are always applied
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 1: Container isolation flags are always applied
@given(policy=policy_strategy)
@settings(max_examples=100)
def test_container_isolation_flags_always_applied(policy: Policy) -> None:
    """For any policy, the podman run command built by ContainerProvisioner SHALL
    always include required isolation flags and SHALL never include --privileged.

    Required flags:
    - ``--userns=keep-id``  (rootless user namespace)
    - ``--pid=private``     (PID namespace isolation)
    - No ``--privileged``   (must never be present)

    Validates: Requirements 1.1, 1.3, 2.1, 2.2
    """
    provisioner = ContainerProvisioner()
    working_dir = Path("/tmp/workspace")

    cmd = provisioner.build_command(working_dir, policy)

    assert "--userns=keep-id" in cmd, (
        f"Expected '--userns=keep-id' in command, got: {cmd}"
    )
    assert "--pid=private" in cmd, (
        f"Expected '--pid=private' in command, got: {cmd}"
    )
    assert "--privileged" not in cmd, (
        f"'--privileged' must never appear in command, got: {cmd}"
    )


# ---------------------------------------------------------------------------
# Property 4: Filesystem isolation configuration matches policy
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 4: Filesystem isolation configuration matches policy
@given(policy=policy_strategy)
@settings(max_examples=100)
def test_filesystem_isolation_matches_policy(policy: Policy) -> None:
    """For any policy, the container's volume mounts SHALL include exactly the
    working directory copy and any ``readonly_mounts`` specified in the policy
    (each mounted ``:ro``), and no other host paths.

    Validates: Requirements 3.1, 3.2, 3.4
    """
    provisioner = ContainerProvisioner()
    working_dir = Path("/tmp/workspace")

    cmd = provisioner.build_command(working_dir, policy)

    # Collect all -v mount specs from the command list
    mounts = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-v"]

    # Working directory must be mounted as /workspace:rw
    assert f"{working_dir}:/workspace:rw" in mounts, (
        f"Expected '{working_dir}:/workspace:rw' in mounts, got: {mounts}"
    )

    # Every readonly_mount in the policy must appear as mount:mount:ro
    for mount in policy.readonly_mounts:
        assert f"{mount}:{mount}:ro" in mounts, (
            f"Expected '{mount}:{mount}:ro' in mounts, got: {mounts}"
        )

    # No extra -v entries beyond working dir + readonly_mounts
    expected_mounts = {f"{working_dir}:/workspace:rw"} | {
        f"{mount}:{mount}:ro" for mount in policy.readonly_mounts
    }
    assert set(mounts) == expected_mounts, (
        f"Unexpected mounts found. Expected: {expected_mounts}, got: {set(mounts)}"
    )


# ---------------------------------------------------------------------------
# Property 5: Network configuration matches policy
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 5: Network configuration matches policy
@given(policy=policy_strategy)
@settings(max_examples=100)
def test_network_configuration_matches_policy(policy: Policy) -> None:
    """For any policy, the container's network configuration SHALL match the policy:
    if ``network.disabled`` is True (or no policy is provided), the command SHALL
    include ``--network=none``; if an allowlist is specified, the command SHALL use
    slirp4netns and each allowed host SHALL appear as an ``--add-host`` entry.

    Validates: Requirements 4.1, 4.2, 4.4
    """
    provisioner = ContainerProvisioner()
    working_dir = Path("/tmp/workspace")

    cmd = provisioner.build_command(working_dir, policy)

    if policy.network.disabled:
        # Must include --network=none and no other --network flags
        assert "--network=none" in cmd, (
            f"Expected '--network=none' when network.disabled=True, got: {cmd}"
        )
        # No bare '--network <value>' tokens (only --network=none is allowed)
        bare_network_values = [
            cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--network"
        ]
        assert bare_network_values == [], (
            f"Expected no bare '--network <endpoint>' flags when disabled, got: {bare_network_values}"
        )
    else:
        # Must NOT include --network=none
        assert "--network=none" not in cmd, (
            f"'--network=none' must not appear when network.disabled=False, got: {cmd}"
        )
        if policy.network.allowed_endpoints:
            # Endpoints are expressed via slirp4netns + --add-host, not raw --network values.
            # The network mode must be the slirp4netns flag (as --network=slirp4netns:...).
            network_eq_flags = [arg for arg in cmd if arg.startswith("--network=")]
            assert any("slirp4netns" in f for f in network_eq_flags), (
                f"Expected '--network=slirp4netns:...' when endpoints are specified, got: {cmd}"
            )
            # Each allowed host (the part before the first ':') must appear in an --add-host entry.
            add_host_values = [
                cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--add-host"
            ]
            for endpoint in policy.network.allowed_endpoints:
                host = endpoint.split(":")[0]
                assert any(host in v for v in add_host_values), (
                    f"Expected host '{host}' from endpoint '{endpoint}' in --add-host entries, "
                    f"got: {add_host_values}"
                )
        else:
            # Network enabled, no specific endpoints — slirp4netns without restrictions.
            assert "--network=slirp4netns" in cmd, (
                f"Expected '--network=slirp4netns' when network enabled with no endpoints, got: {cmd}"
            )


# ---------------------------------------------------------------------------
# Property 6: Resource limits are always applied
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 6: Resource limits are always applied
@given(policy=policy_strategy)
@settings(max_examples=100)
def test_resource_limits_always_applied(policy: Policy) -> None:
    """For any policy (including the default), the podman run command SHALL include
    ``--cpus`` and ``--memory`` flags whose values match the policy's ``cpu_cores``
    and ``memory_mb`` fields (defaulting to 1.0 and 512 respectively).

    Validates: Requirements 5.1, 5.2
    """
    provisioner = ContainerProvisioner()
    working_dir = Path("/tmp/workspace")

    cmd = provisioner.build_command(working_dir, policy)

    expected_cpus = f"--cpus={policy.cpu_cores}"
    expected_memory = f"--memory={policy.memory_mb}m"

    assert expected_cpus in cmd, (
        f"Expected '{expected_cpus}' in command, got: {cmd}"
    )
    assert expected_memory in cmd, (
        f"Expected '{expected_memory}' in command, got: {cmd}"
    )


# ---------------------------------------------------------------------------
# Property 7: Only allowed environment variables are forwarded
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 7: Only allowed environment variables are forwarded

# Uppercase-only ASCII identifier characters — avoids Windows case-folding where
# os.environ normalises all keys to uppercase, which would cause 'o' and 'O' to
# collide and produce unexpected forwarding behaviour in the property test.
_env_var_name_strategy = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
    min_size=1,
    max_size=30,
)
_env_var_value_strategy = st.text(
    alphabet=st.characters(blacklist_characters="\x00", blacklist_categories=("Cs",)),
    max_size=100,
)


@given(
    policy=st.builds(
        Policy,
        cpu_cores=st.floats(min_value=0.1, max_value=64.0, allow_nan=False, allow_infinity=False),
        memory_mb=st.integers(min_value=1, max_value=65536),
        network=network_policy_strategy,
        readonly_mounts=st.lists(st.text(min_size=1, max_size=100), max_size=5),
        allowed_env_vars=st.lists(_env_var_name_strategy, max_size=10),
        output_path_in_container=st.text(min_size=1, max_size=200),
        max_output_bytes=st.one_of(st.none(), st.integers(min_value=1, max_value=10**9)),
        timeout_seconds=st.one_of(st.none(), st.integers(min_value=1, max_value=86400)),
        log_output_path=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    ),
    host_env=st.dictionaries(
        keys=_env_var_name_strategy,
        values=_env_var_value_strategy,
        max_size=20,
    ),
)
@settings(max_examples=100)
def test_only_allowed_env_vars_forwarded(policy: Policy, host_env: dict) -> None:
    """For any policy with an ``allowed_env_vars`` list and any host environment,
    the constructed ``podman run`` command SHALL contain ``-e VAR=VALUE`` entries
    only for variables whose names appear in ``policy.allowed_env_vars`` AND are
    present in the host environment. No other environment variables SHALL be
    forwarded.

    Validates: Requirements 6.4
    """
    import os
    import unittest.mock

    provisioner = ContainerProvisioner()
    working_dir = Path("/tmp/workspace")

    # Patch os.environ with the generated host environment for this test.
    # Using unittest.mock.patch avoids mutating the real process environment and
    # sidesteps Windows case-insensitive env-var semantics.
    with unittest.mock.patch.dict(os.environ, host_env, clear=True):
        cmd = provisioner.build_command(working_dir, policy)

    # Collect all forwarded env var names from -e VAR=VALUE entries
    forwarded_vars: set[str] = set()
    for i, arg in enumerate(cmd):
        if arg == "-e" and i + 1 < len(cmd):
            var_name = cmd[i + 1].split("=", 1)[0]
            forwarded_vars.add(var_name)

    allowed_set = set(policy.allowed_env_vars)
    host_keys = set(host_env.keys())

    # Only vars present in both allowed_env_vars AND the host environment should be forwarded
    expected_forwarded = allowed_set & host_keys
    assert forwarded_vars == expected_forwarded, (
        f"Forwarded vars mismatch. "
        f"Expected: {expected_forwarded}, got: {forwarded_vars}. "
        f"allowed_env_vars={policy.allowed_env_vars}, host_env keys={host_keys}"
    )

    # No var outside the allowed list should ever be forwarded
    disallowed_forwarded = forwarded_vars - allowed_set
    assert not disallowed_forwarded, (
        f"Disallowed env vars were forwarded: {disallowed_forwarded}"
    )
