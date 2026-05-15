"""Exceptions for adapter operations."""

from __future__ import annotations


class AdapterError(Exception):
    """Base exception for all adapter errors."""
    pass


class AdapterNotFoundError(AdapterError):
    """Raised when a requested adapter is not registered.
    
    Attributes:
        adapter_type: The type of adapter that was not found (e.g., "container", "storage")
        adapter_name: The name of the adapter that was requested
        available: List of available adapter names for this type
    """
    
    def __init__(
        self,
        message: str,
        adapter_type: str | None = None,
        adapter_name: str | None = None,
        available: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.adapter_type = adapter_type
        self.adapter_name = adapter_name
        self.available = available or []


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid.
    
    Attributes:
        adapter_name: The name of the adapter with invalid configuration
        config_key: The specific configuration key that is invalid
        expected_type: The expected type for the configuration value
    """
    
    def __init__(
        self,
        message: str,
        adapter_name: str | None = None,
        config_key: str | None = None,
        expected_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.adapter_name = adapter_name
        self.config_key = config_key
        self.expected_type = expected_type


class AdapterInitializationError(AdapterError):
    """Raised when adapter initialization fails.
    
    Attributes:
        adapter_name: The name of the adapter that failed to initialize
        reason: The reason for initialization failure
    """
    
    def __init__(
        self,
        message: str,
        adapter_name: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.adapter_name = adapter_name
        self.reason = reason


class AdapterOperationError(AdapterError):
    """Raised when an adapter operation fails.
    
    Attributes:
        adapter_name: The name of the adapter where the operation failed
        operation: The operation that failed (e.g., "provision", "exec", "store")
        details: Additional details about the failure
    """
    
    def __init__(
        self,
        message: str,
        adapter_name: str | None = None,
        operation: str | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.adapter_name = adapter_name
        self.operation = operation
        self.details = details

# Made with Bob
