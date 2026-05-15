"""Property-based tests for SubAgentPolicy serialisation.

Feature: sub-agent-handling
"""

from hypothesis import given, settings, strategies as st

from isolated_agents_sdk.models import NetworkPolicy, SubAgentPolicy


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

sub_agent_policy_strategy = st.builds(
    SubAgentPolicy,
    cpu_cores=st.floats(min_value=0.1, max_value=64.0, allow_nan=False, allow_infinity=False),
    memory_mb=st.integers(min_value=1, max_value=65536),
    network=network_policy_strategy,
    readonly_mounts=st.lists(st.text(min_size=1, max_size=100), max_size=5),
    allowed_env_vars=st.lists(st.text(min_size=1, max_size=50), max_size=10),
    output_path_in_container=st.text(min_size=1, max_size=200),
    max_output_bytes=st.one_of(st.none(), st.integers(min_value=1, max_value=10**9)),
    timeout_seconds=st.one_of(st.none(), st.integers(min_value=1, max_value=86400)),
    log_output_path=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    max_sub_agent_depth=st.integers(min_value=1, max_value=20),
    max_sub_agents=st.integers(min_value=1, max_value=100),
)


# ---------------------------------------------------------------------------
# Property 12: SubAgentPolicy serialisation round-trip
# ---------------------------------------------------------------------------

# Feature: sub-agent-handling, Property 12: SubAgentPolicy serialisation round-trip
@given(sub_agent_policy_strategy)
@settings(max_examples=100)
def test_sub_agent_policy_round_trip(policy: SubAgentPolicy) -> None:
    """For any valid SubAgentPolicy, serialising to JSON then deserialising
    SHALL produce a SubAgentPolicy object equivalent to the original — all
    fields equal.

    Validates: Requirements 10.1, 10.2, 10.3
    """
    restored = SubAgentPolicy.from_json(policy.to_json())

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
    assert restored.max_sub_agent_depth == policy.max_sub_agent_depth
    assert restored.max_sub_agents == policy.max_sub_agents


# ---------------------------------------------------------------------------
# Property 13: SubAgentPolicy validation rejects invalid inputs
# ---------------------------------------------------------------------------

# Known field names in SubAgentPolicy schema
_KNOWN_SUB_AGENT_POLICY_FIELDS = frozenset({
    "cpu_cores",
    "memory_mb",
    "network",
    "readonly_mounts",
    "allowed_env_vars",
    "output_path_in_container",
    "max_output_bytes",
    "timeout_seconds",
    "log_output_path",
    "max_sub_agent_depth",
    "max_sub_agents",
})

# Strategy for generating unknown field names (non-empty text, not a known field)
unknown_field_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_"),
    min_size=1,
    max_size=30,
).filter(lambda name: name not in _KNOWN_SUB_AGENT_POLICY_FIELDS)

# Strategy for generating invalid values for max_sub_agent_depth / max_sub_agents:
# zero, negative integers, non-integer floats, strings, or None
invalid_limit_value_strategy = st.one_of(
    st.integers(max_value=0),                                          # zero or negative
    st.floats(min_value=0.1, max_value=1e6, allow_nan=False, allow_infinity=False),  # non-integer float
    st.text(min_size=0, max_size=20),                                  # string
    st.none(),                                                         # None
)


def _make_valid_sub_agent_policy_dict() -> dict:
    """Return a minimal valid SubAgentPolicy dict."""
    return {
        "cpu_cores": 1.0,
        "memory_mb": 512,
        "network": {"disabled": True, "allowed_endpoints": []},
        "readonly_mounts": [],
        "allowed_env_vars": [],
        "output_path_in_container": "/output",
        "max_output_bytes": None,
        "timeout_seconds": None,
        "log_output_path": None,
        "max_sub_agent_depth": 3,
        "max_sub_agents": 10,
    }


# Feature: sub-agent-handling, Property 13: SubAgentPolicy validation rejects invalid inputs
@given(
    unknown_field=unknown_field_name_strategy,
    unknown_value=st.integers() | st.text() | st.booleans() | st.none(),
)
@settings(max_examples=100)
def test_sub_agent_policy_rejects_unknown_fields(
    unknown_field: str,
    unknown_value: object,
) -> None:
    """For any JSON object that contains a field name not present in the
    SubAgentPolicy schema, SubAgentPolicy.from_json() SHALL raise a
    PolicyValidationError with a message identifying the offending field.

    Validates: Requirements 10.4
    """
    from isolated_agents_sdk.exceptions import PolicyValidationError
    import json

    policy_dict = _make_valid_sub_agent_policy_dict()
    policy_dict[unknown_field] = unknown_value

    json_str = json.dumps(policy_dict)

    try:
        SubAgentPolicy.from_json(json_str)
        raise AssertionError(
            f"Expected PolicyValidationError for unknown field '{unknown_field}', "
            "but from_json() succeeded."
        )
    except PolicyValidationError as exc:
        # The error message must mention the offending field
        assert unknown_field in str(exc), (
            f"PolicyValidationError message {str(exc)!r} does not mention "
            f"the offending field '{unknown_field}'"
        )


# Feature: sub-agent-handling, Property 13: SubAgentPolicy validation rejects invalid inputs
@given(
    limit_field=st.sampled_from(["max_sub_agent_depth", "max_sub_agents"]),
    invalid_value=invalid_limit_value_strategy,
)
@settings(max_examples=100)
def test_sub_agent_policy_rejects_invalid_limit_values(
    limit_field: str,
    invalid_value: object,
) -> None:
    """For any JSON object where max_sub_agent_depth or max_sub_agents is
    present but is not a positive integer (i.e. is zero, negative, a float,
    a string, or None), SubAgentPolicy.from_json() SHALL raise a
    PolicyValidationError with a message identifying the offending field.

    Validates: Requirements 10.5
    """
    from isolated_agents_sdk.exceptions import PolicyValidationError
    import json
    import math

    # Skip NaN/Inf floats — json.dumps cannot serialise them
    if isinstance(invalid_value, float) and (math.isnan(invalid_value) or math.isinf(invalid_value)):
        return

    policy_dict = _make_valid_sub_agent_policy_dict()
    policy_dict[limit_field] = invalid_value

    json_str = json.dumps(policy_dict)

    try:
        SubAgentPolicy.from_json(json_str)
        raise AssertionError(
            f"Expected PolicyValidationError for invalid value {invalid_value!r} "
            f"in field '{limit_field}', but from_json() succeeded."
        )
    except PolicyValidationError as exc:
        # The error message must mention the offending field
        assert limit_field in str(exc), (
            f"PolicyValidationError message {str(exc)!r} does not mention "
            f"the offending field '{limit_field}'"
        )
