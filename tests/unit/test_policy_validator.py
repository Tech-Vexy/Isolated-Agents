"""Unit tests for PolicyValidator.

Covers:
- Default values applied when None is passed (Requirement 5.2)
- Specific error messages for unknown fields (Requirement 10.5)
- Specific error messages for invalid field types (Requirement 10.6)
"""

import json
import pytest

from isolated_agents_sdk.exceptions import PolicyValidationError
from isolated_agents_sdk.models import Policy
from isolated_agents_sdk.policy_validator import PolicyValidator


@pytest.fixture
def validator() -> PolicyValidator:
    return PolicyValidator()


# ---------------------------------------------------------------------------
# Default values when None is passed
# ---------------------------------------------------------------------------

class TestDefaultPolicy:
    @pytest.mark.asyncio
    async def test_returns_policy_instance(self, validator):
        result = await validator.validate(None)
        assert isinstance(result, Policy)

    @pytest.mark.asyncio
    async def test_default_cpu_cores(self, validator):
        result = await validator.validate(None)
        assert result.cpu_cores == 1.0

    @pytest.mark.asyncio
    async def test_default_memory_mb(self, validator):
        result = await validator.validate(None)
        assert result.memory_mb == 512

    @pytest.mark.asyncio
    async def test_default_network_disabled(self, validator):
        result = await validator.validate(None)
        assert result.network.disabled is True

    @pytest.mark.asyncio
    async def test_default_network_no_endpoints(self, validator):
        result = await validator.validate(None)
        assert result.network.allowed_endpoints == []

    @pytest.mark.asyncio
    async def test_default_readonly_mounts_empty(self, validator):
        result = await validator.validate(None)
        assert result.readonly_mounts == []

    @pytest.mark.asyncio
    async def test_default_allowed_env_vars_empty(self, validator):
        result = await validator.validate(None)
        assert result.allowed_env_vars == []

    @pytest.mark.asyncio
    async def test_default_output_path(self, validator):
        result = await validator.validate(None)
        assert result.output_path_in_container == "/output"

    @pytest.mark.asyncio
    async def test_default_max_output_bytes_none(self, validator):
        result = await validator.validate(None)
        assert result.max_output_bytes is None

    @pytest.mark.asyncio
    async def test_default_timeout_seconds_none(self, validator):
        result = await validator.validate(None)
        assert result.timeout_seconds is None

    @pytest.mark.asyncio
    async def test_default_log_output_path_none(self, validator):
        result = await validator.validate(None)
        assert result.log_output_path is None

    @pytest.mark.asyncio
    async def test_valid_policy_returned_unchanged(self, validator):
        policy = Policy(cpu_cores=2.0, memory_mb=1024)
        result = await validator.validate(policy)
        assert result is policy

    @pytest.mark.asyncio
    async def test_non_policy_non_none_raises_type_error(self, validator):
        with pytest.raises(TypeError):
            await validator.validate({"cpu_cores": 1.0})


# ---------------------------------------------------------------------------
# Unknown field rejection (Requirement 10.5)
# ---------------------------------------------------------------------------

class TestUnknownFieldRejection:
    def _from_json_with_extra(self, extra: dict) -> None:
        data = {"cpu_cores": 1.0, **extra}
        Policy.from_json(json.dumps(data))

    def test_unknown_field_raises_policy_validation_error(self):
        with pytest.raises(PolicyValidationError):
            self._from_json_with_extra({"unknown_field": "value"})

    def test_error_message_contains_field_name(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json_with_extra({"bad_field": 42})
        assert "bad_field" in str(exc_info.value)

    def test_field_name_attribute_set(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json_with_extra({"extra_key": True})
        assert exc_info.value.field_name == "extra_key"

    def test_multiple_unknown_fields_raises(self):
        # First unknown field encountered should raise
        with pytest.raises(PolicyValidationError):
            self._from_json_with_extra({"foo": 1, "bar": 2})

    def test_known_fields_do_not_raise(self):
        data = json.dumps({"cpu_cores": 2.0, "memory_mb": 256})
        policy = Policy.from_json(data)
        assert policy.cpu_cores == 2.0

    def test_unknown_network_subfield_raises(self):
        data = json.dumps({"network": {"disabled": True, "mystery": "value"}})
        with pytest.raises(PolicyValidationError) as exc_info:
            Policy.from_json(data)
        assert "mystery" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Invalid field type rejection (Requirement 10.6)
# ---------------------------------------------------------------------------

class TestInvalidFieldTypeRejection:
    def _from_json(self, data: dict) -> None:
        Policy.from_json(json.dumps(data))

    def test_cpu_cores_string_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"cpu_cores": "fast"})
        assert "cpu_cores" in str(exc_info.value)

    def test_memory_mb_string_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"memory_mb": "lots"})
        assert "memory_mb" in str(exc_info.value)

    def test_memory_mb_bool_raises(self):
        # bool is a subclass of int; must be rejected explicitly
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"memory_mb": True})
        assert "memory_mb" in str(exc_info.value)

    def test_readonly_mounts_string_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"readonly_mounts": "/some/path"})
        assert "readonly_mounts" in str(exc_info.value)

    def test_allowed_env_vars_int_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"allowed_env_vars": 99})
        assert "allowed_env_vars" in str(exc_info.value)

    def test_output_path_int_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"output_path_in_container": 123})
        assert "output_path_in_container" in str(exc_info.value)

    def test_max_output_bytes_string_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"max_output_bytes": "big"})
        assert "max_output_bytes" in str(exc_info.value)

    def test_timeout_seconds_float_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"timeout_seconds": 30.5})
        assert "timeout_seconds" in str(exc_info.value)

    def test_log_output_path_list_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"log_output_path": ["/var/log"]})
        assert "log_output_path" in str(exc_info.value)

    def test_error_contains_expected_type(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"memory_mb": "oops"})
        assert exc_info.value.expected_type == "int"

    def test_field_name_attribute_set_on_type_error(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"cpu_cores": "nope"})
        assert exc_info.value.field_name == "cpu_cores"

    def test_network_disabled_wrong_type_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"network": {"disabled": "yes"}})
        assert "disabled" in str(exc_info.value)

    def test_network_allowed_endpoints_wrong_type_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"network": {"allowed_endpoints": "8.8.8.8"}})
        assert "allowed_endpoints" in str(exc_info.value)

    def test_network_field_wrong_type_raises(self):
        with pytest.raises(PolicyValidationError) as exc_info:
            self._from_json({"network": "none"})
        assert "network" in str(exc_info.value)

    def test_optional_int_none_is_valid(self):
        # None is explicitly allowed for Optional fields
        policy = Policy.from_json(json.dumps({"max_output_bytes": None}))
        assert policy.max_output_bytes is None

    def test_optional_str_none_is_valid(self):
        policy = Policy.from_json(json.dumps({"log_output_path": None}))
        assert policy.log_output_path is None
