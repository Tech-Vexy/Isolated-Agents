"""Base interface for policy validator adapters."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Optional

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.policy.types import (
    PolicyConstraints,
    PolicyValidationResult,
)


class PolicyValidator(BaseAdapter):
    """Abstract base class for policy validator adapters.

    Implementations must provide methods for validating policies against
    constraints, schemas, or custom rules.

    Lifecycle:
        1. Initialize adapter
        2. Validate policies
        3. Cleanup adapter

    Example:
        >>> adapter = DefaultPolicyValidator()
        >>> await adapter.initialize()
        >>>
        >>> from isolated_agents_sdk.models import Policy
        >>> policy = Policy(memory_mb=512, cpu_cores=1.0)
        >>>
        >>> result = await adapter.validate_policy(policy)
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(f"{error.field}: {error.message}")
        >>>
        >>> await adapter.cleanup()
    """

    @abstractmethod
    async def validate_policy(
        self,
        policy: Any,  # Should be Policy type from models
        constraints: PolicyConstraints | None = None,
    ) -> PolicyValidationResult:
        """Validate a policy.

        Args:
            policy: Policy to validate
            constraints: Optional validation constraints

        Returns:
            Validation result with errors and warnings

        Raises:
            AdapterOperationError: If validation fails unexpectedly
        """
        pass

    async def validate_batch(
        self,
        policies: list[Any],
        constraints: PolicyConstraints | None = None,
    ) -> list[PolicyValidationResult]:
        """Validate multiple policies.

        This is an optional method that may be implemented by adapters
        for batch validation optimization.

        Args:
            policies: List of policies to validate
            constraints: Optional validation constraints

        Returns:
            List of validation results
        """
        results = []
        for policy in policies:
            result = await self.validate_policy(policy, constraints)
            results.append(result)
        return results

    async def get_constraints(self) -> PolicyConstraints:
        """Get default validation constraints.

        This is an optional method that may be implemented by adapters
        to provide default constraints.

        Returns:
            Default policy constraints
        """
        return PolicyConstraints()


# Made with Bob
