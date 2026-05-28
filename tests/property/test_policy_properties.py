"""Property-based tests for Policy serialisation.

Feature: isolated-agents-sdk
"""

from hypothesis import given, settings
from hypothesis import strategies as st

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
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=".-:/"
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
# Property 14: Policy serialization round-trip
# ---------------------------------------------------------------------------


# Feature: isolated-agents-sdk, Property 14: Policy serialization round-trip
@given(policy_strategy)
@settings(max_examples=100)
def test_policy_round_trip(policy: Policy) -> None:
    """For any valid Policy, serialising to JSON then deserialising SHALL produce
    an equivalent Policy object (all fields equal).

    Validates: Requirements 10.2, 10.3, 10.4
    """
    restored = Policy.from_json(policy.to_json())

    assert restored.cpu_cores == policy.cpu_cores
    assert restored.memory_mb == policy.memory_mb
    assert restored.network.disabled == policy.network.disabled
    assert restored.network.allowed_endpoints == policy.network.allowed_endpoints
    assert restored.readonly_mounts == policy.readonly_mounts
    assert restored.allowed_env_vars == policy.allowed_env_vars
    assert restored.output_path_in_container == policy.output_path_in_container
    assert restored.max_output_bytes == policy.max_output_bytes
    assert restored.timeout_seconds == policy.timeout_seconds
    assert restored.log_output_path == policy.log_output_path


# ---------------------------------------------------------------------------
# Property 15: Unknown policy fields are rejected
# ---------------------------------------------------------------------------

# Known top-level Policy field names — extra keys must not collide with these.
# This set must stay in sync with _POLICY_FIELD_TYPES in models.py.
_KNOWN_POLICY_FIELDS = frozenset(
    {
        "cpu_cores",
        "memory_mb",
        "network",
        "readonly_mounts",
        "allowed_env_vars",
        "pip_packages",
        "output_path_in_container",
        "max_output_bytes",
        "timeout_seconds",
        "log_output_path",
        "entrypoint",
        "base_image",
        "requires_display",
        "tmpfs_secrets",
        "proxy_url",
        "proxy_ca_cert",
        "enable_session_replay",
        "cap_drop",
        "cap_add",
        "seccomp_profile",
        "read_only_rootfs",
        "resource_monitor_interval",
        "cpu_threshold_percent",
        "memory_threshold_percent",
        "container_user",
        "pip_index_url",
        "pip_require_hashes",
        "max_sub_agent_depth",
        "max_sub_agents",
    }
)

# Strategy: text keys that are not existing Policy fields
unknown_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=30,
).filter(lambda k: k not in _KNOWN_POLICY_FIELDS)


# Feature: isolated-agents-sdk, Property 15: Unknown policy fields are rejected
@given(
    policy=policy_strategy,
    extra_key=unknown_key_strategy,
    extra_value=st.one_of(st.integers(), st.text(), st.booleans(), st.none()),
)
@settings(max_examples=100)
def test_unknown_policy_fields_rejected(
    policy: Policy, extra_key: str, extra_value: object
) -> None:
    """For any valid Policy JSON with at least one unknown top-level field,
    ``Policy.from_json()`` SHALL raise ``PolicyValidationError``.

    Validates: Requirements 10.5
    """
    import json

    from isolated_agents_sdk.exceptions import PolicyValidationError

    raw: dict = json.loads(policy.to_json())
    raw[extra_key] = extra_value
    json_with_unknown = json.dumps(raw)

    try:
        Policy.from_json(json_with_unknown)
        raise AssertionError(
            f"Expected PolicyValidationError for unknown field '{extra_key}', but no exception was raised"
        )
    except PolicyValidationError:
        pass  # expected


# ---------------------------------------------------------------------------
# Property 16: Invalid policy field types are rejected
# ---------------------------------------------------------------------------

import json as _json

from isolated_agents_sdk.exceptions import PolicyValidationError

# Map each known Policy field to strategies that produce WRONG types for it.
# cpu_cores expects float/int (not bool) → wrong types: str, list, dict, bool
# memory_mb expects int (not bool)       → wrong types: str, float, list, dict, bool
# network expects dict                   → wrong types: str, int, list, bool
# readonly_mounts expects list           → wrong types: str, int, dict, bool
# allowed_env_vars expects list          → wrong types: str, int, dict, bool
# output_path_in_container expects str   → wrong types: int, list, dict, bool
# max_output_bytes expects int/None      → wrong types: str, float, list, dict, bool
# timeout_seconds expects int/None       → wrong types: str, float, list, dict, bool
# log_output_path expects str/None       → wrong types: int, list, dict, bool

_wrong_type_strategies: dict[str, st.SearchStrategy] = {
    "cpu_cores": st.one_of(
        st.text(min_size=1),
        st.lists(st.integers()),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "memory_mb": st.one_of(
        st.text(min_size=1),
        st.floats(allow_nan=False, allow_infinity=False).filter(
            lambda x: x != int(x) if x == x else True
        ),
        st.lists(st.integers()),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "network": st.one_of(
        st.text(min_size=1),
        st.integers(),
        st.lists(st.integers()),
        st.booleans(),
    ),
    "readonly_mounts": st.one_of(
        st.text(min_size=1),
        st.integers(),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "allowed_env_vars": st.one_of(
        st.text(min_size=1),
        st.integers(),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "output_path_in_container": st.one_of(
        st.integers(),
        st.lists(st.integers()),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "max_output_bytes": st.one_of(
        st.text(min_size=1),
        st.floats(allow_nan=False, allow_infinity=False).filter(
            lambda x: x != int(x) if x == x else True
        ),
        st.lists(st.integers()),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "timeout_seconds": st.one_of(
        st.text(min_size=1),
        st.floats(allow_nan=False, allow_infinity=False).filter(
            lambda x: x != int(x) if x == x else True
        ),
        st.lists(st.integers()),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
    "log_output_path": st.one_of(
        st.integers(),
        st.lists(st.integers()),
        st.fixed_dictionaries({}),
        st.booleans(),
    ),
}

_field_name_strategy = st.sampled_from(sorted(_wrong_type_strategies.keys()))


# Feature: isolated-agents-sdk, Property 16: Invalid policy field types are rejected
@given(
    policy=policy_strategy,
    field_name=_field_name_strategy,
    data=st.data(),
)
@settings(max_examples=100)
def test_invalid_policy_field_types_rejected(
    policy: Policy, field_name: str, data: st.DataObject
) -> None:
    """For any valid Policy JSON where a known field is set to a wrong type,
    ``Policy.from_json()`` SHALL raise ``PolicyValidationError`` that identifies
    the offending field name.

    Validates: Requirements 10.6
    """
    wrong_value = data.draw(_wrong_type_strategies[field_name], label="wrong_value")

    raw: dict = _json.loads(policy.to_json())
    raw[field_name] = wrong_value
    bad_json = _json.dumps(raw)

    try:
        Policy.from_json(bad_json)
        raise AssertionError(
            f"Expected PolicyValidationError for field '{field_name}' with wrong type "
            f"{type(wrong_value).__name__}, but no exception was raised"
        )
    except PolicyValidationError as exc:
        # The error must identify the offending field
        assert exc.field_name is not None, (
            f"PolicyValidationError for field '{field_name}' must set field_name, got None"
        )
        assert field_name in exc.field_name, (
            f"PolicyValidationError.field_name should contain '{field_name}', got '{exc.field_name}'"
        )
