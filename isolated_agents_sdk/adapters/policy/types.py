"""Type definitions for policy validator adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ValidationSeverity(str, Enum):
    """Validation error severity levels."""
    
    ERROR = "error"  # Policy is invalid, cannot proceed
    WARNING = "warning"  # Policy has issues but can proceed
    INFO = "info"  # Informational message


@dataclass
class ValidationError:
    """Policy validation error.
    
    Attributes:
        field: Field name that failed validation
        message: Error message
        severity: Error severity
        code: Optional error code
        suggestion: Optional suggestion for fixing the error
    """
    field: str
    message: str
    severity: ValidationSeverity
    code: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class PolicyValidationResult:
    """Result of policy validation.
    
    Attributes:
        is_valid: Whether the policy is valid
        errors: List of validation errors
        warnings: List of validation warnings
        metadata: Optional metadata about validation
    """
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def add_error(
        self,
        field: str,
        message: str,
        code: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a validation error."""
        self.errors.append(
            ValidationError(
                field=field,
                message=message,
                severity=ValidationSeverity.ERROR,
                code=code,
                suggestion=suggestion,
            )
        )
        self.is_valid = False
    
    def add_warning(
        self,
        field: str,
        message: str,
        code: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Add a validation warning."""
        self.warnings.append(
            ValidationError(
                field=field,
                message=message,
                severity=ValidationSeverity.WARNING,
                code=code,
                suggestion=suggestion,
            )
        )


@dataclass
class PolicyConstraints:
    """Policy validation constraints.
    
    Attributes:
        max_memory_mb: Maximum allowed memory in MB
        max_cpu_cores: Maximum allowed CPU cores
        max_timeout_seconds: Maximum allowed timeout
        allowed_pip_packages: List of allowed pip packages (None = all allowed)
        blocked_pip_packages: List of blocked pip packages
        require_network_policy: Whether network policy is required
        require_readonly_rootfs: Whether read-only rootfs is required
        allowed_ingress_ports: List of allowed ingress ports (None = all allowed)
        blocked_env_vars: List of explicitly blocked environment variable names
    """
    max_memory_mb: Optional[int] = None
    max_cpu_cores: Optional[float] = None
    max_timeout_seconds: Optional[int] = None
    allowed_pip_packages: Optional[list[str]] = None
    blocked_pip_packages: list[str] = field(default_factory=list)
    require_network_policy: bool = False
    require_readonly_rootfs: bool = False
    allowed_ingress_ports: Optional[list[int]] = None
    blocked_env_vars: list[str] = field(default_factory=list)

# Made with Bob