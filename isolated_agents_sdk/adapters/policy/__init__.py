"""Policy validator adapters for the Isolated Agents SDK.

This package provides pluggable policy validator adapters for:
- Default schema-based validation
- OPA (Open Policy Agent) integration
- Custom validation strategies
- Policy composition and inheritance

Example usage:
    from isolated_agents_sdk.adapters.policy import DefaultPolicyValidator
    from isolated_agents_sdk.adapters.factory import AdapterFactory
    
    # Create default validator
    adapter = AdapterFactory.create_policy_adapter("default")
    await adapter.initialize()
    
    # Validate policy
    result = await adapter.validate_policy(policy)
    if not result.is_valid:
        print(f"Validation errors: {result.errors}")
"""

from isolated_agents_sdk.adapters.policy.base import PolicyValidator
from isolated_agents_sdk.adapters.policy.default import DefaultPolicyValidator
from isolated_agents_sdk.adapters.policy.types import (
    PolicyValidationResult,
    ValidationError,
    ValidationSeverity,
)

__all__ = [
    "PolicyValidator",
    "DefaultPolicyValidator",
    "PolicyValidationResult",
    "ValidationError",
    "ValidationSeverity",
]

# Made with Bob