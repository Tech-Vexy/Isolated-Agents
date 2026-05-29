"""Default policy validator adapter."""

from __future__ import annotations

from typing import Any, Optional

from isolated_agents_sdk.adapters.policy.base import PolicyValidator
from isolated_agents_sdk.adapters.policy.types import (
    PolicyConstraints,
    PolicyValidationResult,
)


class DefaultPolicyValidator(PolicyValidator):
    """Default schema-based policy validator.

    Validates policies against basic constraints and schema rules.

    Example:
        >>> adapter = DefaultPolicyValidator()
        >>> await adapter.initialize()
        >>>
        >>> from isolated_agents_sdk.models import Policy
        >>> policy = Policy(memory_mb=512, cpu_cores=1.0)
        >>>
        >>> constraints = PolicyConstraints(max_memory_mb=1024, max_cpu_cores=2.0)
        >>> result = await adapter.validate_policy(policy, constraints)
        >>>
        >>> if not result.is_valid:
        ...     for error in result.errors:
        ...         print(f"{error.field}: {error.message}")
    """

    def __init__(
        self,
        constraints: PolicyConstraints | None = None,
        strict_mode: bool = False,
        max_cpu_cores: float | None = None,
        max_memory_mb: int | None = None,
        max_timeout_seconds: int | None = None,
        **kwargs,
    ):
        """Initialize default policy validator.

        Args:
            constraints: Default validation constraints object
            strict_mode: Whether to reject policies with warnings
            max_cpu_cores: Maximum CPU cores allowed
            max_memory_mb: Maximum memory in MB allowed
            max_timeout_seconds: Maximum timeout in seconds allowed
            **kwargs: Additional configuration parameters
        """
        super().__init__()

        if constraints:
            self._constraints = constraints
        else:
            # Build constraints from individual parameters
            self._constraints = PolicyConstraints(
                max_cpu_cores=max_cpu_cores,
                max_memory_mb=max_memory_mb,
                max_timeout_seconds=max_timeout_seconds,
            )

        self._strict_mode = strict_mode
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the adapter."""
        self._initialized = True

    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._initialized = False

    async def health_check(self) -> bool:
        """Check if validator is ready."""
        return self._initialized

    async def validate_policy(
        self,
        policy: Any,
        constraints: PolicyConstraints | None = None,
    ) -> PolicyValidationResult:
        """Validate a policy against constraints."""
        if not self._initialized:
            await self.initialize()

        # Use provided constraints or default
        constraints = constraints or self._constraints

        result = PolicyValidationResult(is_valid=True)

        # Validate memory
        if hasattr(policy, "memory_mb"):
            memory_mb = getattr(policy, "memory_mb", None)
            if memory_mb is not None:
                if memory_mb <= 0:
                    result.add_error(
                        "memory_mb",
                        "Memory must be greater than 0",
                        code="INVALID_MEMORY",
                        suggestion="Set memory_mb to a positive value",
                    )
                elif constraints.max_memory_mb and memory_mb > constraints.max_memory_mb:
                    result.add_error(
                        "memory_mb",
                        f"Memory {memory_mb}MB exceeds maximum {constraints.max_memory_mb}MB",
                        code="MEMORY_EXCEEDED",
                        suggestion=f"Reduce memory_mb to {constraints.max_memory_mb} or less",
                    )

        # Validate CPU
        if hasattr(policy, "cpu_cores"):
            cpu_cores = getattr(policy, "cpu_cores", None)
            if cpu_cores is not None:
                if cpu_cores <= 0:
                    result.add_error(
                        "cpu_cores",
                        "CPU cores must be greater than 0",
                        code="INVALID_CPU",
                        suggestion="Set cpu_cores to a positive value",
                    )
                elif constraints.max_cpu_cores and cpu_cores > constraints.max_cpu_cores:
                    result.add_error(
                        "cpu_cores",
                        f"CPU {cpu_cores} cores exceeds maximum {constraints.max_cpu_cores} cores",
                        code="CPU_EXCEEDED",
                        suggestion=f"Reduce cpu_cores to {constraints.max_cpu_cores} or less",
                    )

        # Validate timeout
        if hasattr(policy, "timeout_seconds"):
            timeout = getattr(policy, "timeout_seconds", None)
            if timeout is not None:
                if timeout <= 0:
                    result.add_error(
                        "timeout_seconds",
                        "Timeout must be greater than 0",
                        code="INVALID_TIMEOUT",
                        suggestion="Set timeout_seconds to a positive value",
                    )
                elif constraints.max_timeout_seconds and timeout > constraints.max_timeout_seconds:
                    result.add_error(
                        "timeout_seconds",
                        f"Timeout {timeout}s exceeds maximum {constraints.max_timeout_seconds}s",
                        code="TIMEOUT_EXCEEDED",
                        suggestion=f"Reduce timeout_seconds to {constraints.max_timeout_seconds} or less",
                    )

        # Validate pip packages
        if hasattr(policy, "pip_packages"):
            pip_packages = getattr(policy, "pip_packages", [])
            if pip_packages:
                # Check blocked packages
                for package in pip_packages:
                    if package in constraints.blocked_pip_packages:
                        result.add_error(
                            "pip_packages",
                            f"Package '{package}' is blocked",
                            code="BLOCKED_PACKAGE",
                            suggestion=f"Remove '{package}' from pip_packages",
                        )

                # Check allowed packages
                if constraints.allowed_pip_packages is not None:
                    for package in pip_packages:
                        if package not in constraints.allowed_pip_packages:
                            result.add_error(
                                "pip_packages",
                                f"Package '{package}' is not in allowed list",
                                code="PACKAGE_NOT_ALLOWED",
                                suggestion=f"Only use packages from: {', '.join(constraints.allowed_pip_packages)}",
                            )

        # Validate network policy
        if constraints.require_network_policy:
            if not hasattr(policy, "network") or getattr(policy, "network", None) is None:
                result.add_error(
                    "network",
                    "Network policy is required but not specified",
                    code="MISSING_NETWORK_POLICY",
                    suggestion="Add a NetworkPolicy to the policy",
                )

        # Validate read-only rootfs
        if constraints.require_readonly_rootfs and hasattr(policy, "read_only_rootfs"):
            if not getattr(policy, "read_only_rootfs", False):
                result.add_error(
                    "read_only_rootfs",
                    "Read-only root filesystem is required",
                    code="READONLY_ROOTFS_REQUIRED",
                    suggestion="Set read_only_rootfs=True",
                )

        # Validate ingress ports
        if hasattr(policy, "network") and policy.network:
            ingress_ports = getattr(policy.network, "ingress_ports", [])
            if ingress_ports and constraints.allowed_ingress_ports is not None:
                for port in ingress_ports:
                    if port not in constraints.allowed_ingress_ports:
                        result.add_error(
                            "network.ingress_ports",
                            f"Port {port} is not in allowed list",
                            code="PORT_NOT_ALLOWED",
                            suggestion=f"Only use ports from: {constraints.allowed_ingress_ports}",
                        )

        # Validate Environment Variables (Protection)
        current_env_vars = getattr(policy, "env_vars", {})
        current_allowed_env_vars = getattr(policy, "allowed_env_vars", [])

        # Check against policy-level blocks
        if hasattr(policy, "blocked_env_vars") and policy.blocked_env_vars:
            for blocked in policy.blocked_env_vars:
                if blocked in current_env_vars:
                    result.add_error(
                        "env_vars",
                        f"Environment variable '{blocked}' is explicitly blocked by policy",
                        code="BLOCKED_ENV_VAR",
                        suggestion=f"Remove '{blocked}' from env_vars",
                    )
                if blocked in current_allowed_env_vars:
                    result.add_error(
                        "allowed_env_vars",
                        f"Forwarding environment variable '{blocked}' is explicitly blocked by policy",
                        code="BLOCKED_ENV_VAR",
                        suggestion=f"Remove '{blocked}' from allowed_env_vars",
                    )

        # Check against system-level constraints
        if constraints.blocked_env_vars:
            for blocked in constraints.blocked_env_vars:
                if blocked in current_env_vars:
                    result.add_error(
                        "env_vars",
                        f"Environment variable '{blocked}' is blocked by system constraints",
                        code="BLOCKED_ENV_VAR",
                    )
                if blocked in current_allowed_env_vars:
                    result.add_error(
                        "allowed_env_vars",
                        f"Forwarding environment variable '{blocked}' is blocked by system constraints",
                        code="BLOCKED_ENV_VAR",
                    )

        # Add warnings for best practices
        if hasattr(policy, "memory_mb"):
            memory_mb = getattr(policy, "memory_mb", None)
            if memory_mb and memory_mb < 128:
                result.add_warning(
                    "memory_mb",
                    f"Memory {memory_mb}MB is very low, may cause issues",
                    code="LOW_MEMORY",
                    suggestion="Consider increasing memory_mb to at least 128MB",
                )

        return result

    async def get_constraints(self) -> PolicyConstraints:
        """Get default validation constraints."""
        return self._constraints


# Made with Bob
