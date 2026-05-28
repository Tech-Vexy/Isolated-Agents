"""Base adapter interface for all SDK adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAdapter(ABC):
    """Base class for all adapters in the SDK.

    Provides common lifecycle methods and configuration management that all
    adapters must implement. Adapters are responsible for abstracting external
    dependencies (container runtimes, storage backends, logging systems, etc.)
    to enable flexible, testable, and production-ready deployments.

    Lifecycle:
        1. Instantiate with configuration
        2. Call initialize() to set up resources
        3. Use adapter methods
        4. Call cleanup() to release resources

    Example:
        >>> adapter = MyAdapter(config={"timeout": 30})
        >>> await adapter.initialize()
        >>> # Use adapter...
        >>> await adapter.cleanup()

    Args:
        config: Adapter-specific configuration dictionary. Keys and values
            depend on the specific adapter implementation.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the adapter with optional configuration.

        Args:
            config: Adapter-specific configuration dictionary
        """
        self._config = config or {}
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter.

        This method is called once after instantiation to set up any required
        resources (connections, clients, file handles, etc.). Implementations
        should:
        - Validate configuration
        - Establish connections to external services
        - Perform health checks
        - Set self._initialized = True on success

        Raises:
            AdapterInitializationError: If initialization fails
            AdapterConfigurationError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up adapter resources.

        This method is called when the adapter is no longer needed. Implementations
        should:
        - Close connections
        - Flush buffers
        - Release file handles
        - Set self._initialized = False

        This method should not raise exceptions - errors should be logged but
        not propagated to allow graceful shutdown.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the adapter is healthy and ready to use.

        This method performs a lightweight check to verify the adapter can
        communicate with its backing service. It should:
        - Return quickly (< 1 second)
        - Not modify state
        - Be safe to call repeatedly

        Returns:
            True if the adapter is healthy and operational, False otherwise
        """
        pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key to retrieve
            default: Default value if key is not found

        Returns:
            Configuration value or default if key not found
        """
        return self._config.get(key, default)

    def is_initialized(self) -> bool:
        """Check if the adapter has been initialized.

        Returns:
            True if initialize() has been called successfully
        """
        return self._initialized

    def get_adapter_name(self) -> str:
        """Get the name of this adapter.

        Returns:
            The adapter class name (e.g., "PodmanAdapter", "S3StorageAdapter")
        """
        return self.__class__.__name__

    def __repr__(self) -> str:
        """Return a string representation of the adapter."""
        status = "initialized" if self._initialized else "not initialized"
        return f"{self.get_adapter_name()}({status})"


# Made with Bob
