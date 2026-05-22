"""Policy validation and normalisation for the Isolated Agents SDK.

This module provides a PolicyValidator class that wraps PolicyValidator adapters.
"""

from __future__ import annotations

from typing import Optional

from isolated_agents_sdk.adapters.policy.base import PolicyValidator as IPolicyValidator
from isolated_agents_sdk.adapters.policy.default import DefaultPolicyValidator
from isolated_agents_sdk.models import Policy

# Detect if adapters are available
try:
    from isolated_agents_sdk.adapters.factory import AdapterFactory
    _ADAPTERS_AVAILABLE = True
except ImportError:
    _ADAPTERS_AVAILABLE = False


class PolicyValidator:
    """Validator for agent policies.

    The PolicyValidator ensures that an agent's requested execution environment
    adheres to organizational constraints and SDK requirements. It leverages
    pluggable adapters to support different validation backends (e.g. JSON Schema,
    OPA, or hardcoded defaults).

    Responsibilities:
    - Normalizes incoming policy objects.
    - Enforces required resource fields and security profiles.
    - Raises descriptive validation errors for malformed policies.
    """

    def __init__(self, adapter: Optional[IPolicyValidator] = None) -> None:
        if adapter:
            self._adapter = adapter
        elif _ADAPTERS_AVAILABLE:
            try:
                self._adapter = AdapterFactory.create_policy_adapter()
            except Exception:
                self._adapter = DefaultPolicyValidator()
        else:
            self._adapter = DefaultPolicyValidator()
            
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self._adapter.initialize()
            self._initialized = True

    async def validate(self, policy: Policy | None) -> Policy:
        """Return a validated, normalised ``Policy``.

        If *policy* is ``None`` a default ``Policy`` is returned.
        Validation is delegated to the underlying adapter.
        """
        await self._ensure_initialized()

        if policy is None:
            return Policy()
        
        if not isinstance(policy, Policy):
            raise TypeError(
                f"Expected a Policy instance or None, got {type(policy).__name__}"
            )

        result = await self._adapter.validate_policy(policy)
        
        if not result.is_valid and result.errors:
            from isolated_agents_sdk.exceptions import PolicyValidationError
            error = result.errors[0]
            raise PolicyValidationError(
                f"Policy validation failed: {error.message}",
                field_name=error.field,
                expected_type=error.code,
            )

        return policy
