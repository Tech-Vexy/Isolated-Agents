"""Adapter registry and dependency injection system.

This module provides a centralized registry for managing adapter instances
and implementing dependency injection patterns. It allows:
- Singleton adapter instances shared across the application
- Lazy initialization of adapters
- Automatic dependency resolution
- Thread-safe adapter management
- Easy testing with mock adapters

Example:
    >>> from isolated_agents_sdk.adapters.registry import AdapterRegistry
    >>>
    >>> # Get the global registry
    >>> registry = AdapterRegistry.get_instance()
    >>>
    >>> # Register adapters
    >>> registry.register_container_adapter("podman", PodmanAdapter())
    >>> registry.register_storage_adapter("local", LocalStorageAdapter())
    >>>
    >>> # Get adapters
    >>> container = registry.get_container_adapter()
    >>> storage = registry.get_storage_adapter()
    >>>
    >>> # Use in tests
    >>> registry.register_container_adapter("mock", MockContainerAdapter())
"""

import threading
from typing import Dict, Optional

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.config import AdapterConfig
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.database.base import DatabaseAdapter
from isolated_agents_sdk.adapters.exceptions import (
    AdapterConfigurationError,
    AdapterNotFoundError,
)
from isolated_agents_sdk.adapters.factory import AdapterFactory
from isolated_agents_sdk.adapters.policy.base import PolicyValidator
from isolated_agents_sdk.adapters.storage.base import StorageAdapter


class AdapterRegistry:
    """Centralized registry for managing adapter instances.

    This class implements the Singleton pattern to ensure a single registry
    instance is shared across the application. It provides thread-safe
    adapter management and lazy initialization.

    Attributes:
        _instance: Singleton instance of the registry
        _lock: Thread lock for thread-safe operations
        _container_adapters: Registered container runtime adapters
        _storage_adapters: Registered storage backend adapters
        _audit_adapters: Registered audit logger adapters
        _policy_adapters: Registered policy validator adapters
        _default_container: Name of the default container adapter
        _default_storage: Name of the default storage adapter
        _default_audit: Name of the default audit adapter
        _default_policy: Name of the default policy adapter
    """

    _instance: Optional["AdapterRegistry"] = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        """Initialize the adapter registry.

        Note: Use get_instance() instead of direct instantiation.
        """
        self._container_adapters: dict[str, ContainerRuntimeAdapter] = {}
        self._storage_adapters: dict[str, StorageAdapter] = {}
        self._audit_adapters: dict[str, AuditAdapter] = {}
        self._policy_adapters: dict[str, PolicyValidator] = {}
        self._database_adapters: dict[str, DatabaseAdapter] = {}

        self._default_container: str | None = None
        self._default_storage: str | None = None
        self._default_audit: str | None = None
        self._default_policy: str | None = None
        self._default_database: str | None = None

        self._initialized = False
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "AdapterRegistry":
        """Get the singleton instance of the adapter registry.

        Returns:
            The singleton AdapterRegistry instance

        Example:
            >>> registry = AdapterRegistry.get_instance()
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing).

        Example:
            >>> AdapterRegistry.reset_instance()
            >>> registry = AdapterRegistry.get_instance()  # New instance
        """
        with cls._lock:
            cls._instance = None

    def initialize_from_config(self, config: AdapterConfig) -> None:
        """Initialize adapters from configuration.

        Args:
            config: Adapter configuration

        Example:
            >>> config = AdapterConfig()
            >>> registry.initialize_from_config(config)
        """
        with self._lock:
            if self._initialized:
                return

            # Create and register container adapter
            if config.container_adapter not in self._container_adapters:
                container = AdapterFactory.create_container_adapter(
                    config.container_adapter, **config.container_config
                )
                self.register_container_adapter(config.container_adapter, container)

            if self._default_container is None:
                self._default_container = config.container_adapter

            # Create and register storage adapter
            if config.storage_adapter not in self._storage_adapters:
                storage = AdapterFactory.create_storage_adapter(
                    config.storage_adapter, **config.storage_config
                )
                self.register_storage_adapter(config.storage_adapter, storage)

            if self._default_storage is None:
                self._default_storage = config.storage_adapter

            # Create and register audit adapter
            if config.audit_adapter not in self._audit_adapters:
                audit = AdapterFactory.create_audit_adapter(
                    config.audit_adapter, **config.audit_config
                )
                self.register_audit_adapter(config.audit_adapter, audit)

            if self._default_audit is None:
                self._default_audit = config.audit_adapter

            # Create and register policy adapter
            if config.policy_adapter not in self._policy_adapters:
                policy = AdapterFactory.create_policy_adapter(
                    config.policy_adapter, **config.policy_config
                )
                self.register_policy_adapter(config.policy_adapter, policy)

            if self._default_policy is None:
                self._default_policy = config.policy_adapter

            # Create and register database adapters
            for db_name, db_info in config.database_adapters.items():
                if db_name not in self._database_adapters:
                    db_type = db_info.get("type", "sql")
                    # Remove 'type' from config before passing to factory
                    db_config = {k: v for k, v in db_info.items() if k != "type"}
                    database = AdapterFactory.create_database_adapter(db_type, **db_config)
                    self.register_database_adapter(db_name, database)

            if self._default_database is None:
                self._default_database = config.default_database

            self._initialized = True

    # Container adapter methods

    def register_container_adapter(self, name: str, adapter: ContainerRuntimeAdapter) -> None:
        """Register a container runtime adapter.

        Args:
            name: Name to register the adapter under
            adapter: Container runtime adapter instance

        Example:
            >>> registry.register_container_adapter("podman", PodmanAdapter())
        """
        with self._lock:
            self._container_adapters[name] = adapter
            if self._default_container is None:
                self._default_container = name

    def get_container_adapter(self, name: str | None = None) -> ContainerRuntimeAdapter:
        """Get a container runtime adapter by name.

        Args:
            name: Name of the adapter to get. If None, returns the default adapter.

        Returns:
            Container runtime adapter instance

        Raises:
            AdapterNotFoundError: If the adapter is not found

        Example:
            >>> adapter = registry.get_container_adapter()
            >>> adapter = registry.get_container_adapter("podman")
        """
        if not self._initialized and name is None:
            self.initialize_from_config(AdapterConfig())

        with self._lock:
            if name is None:
                name = self._default_container

            if name is None:
                raise AdapterConfigurationError("No default container adapter configured")

            if name not in self._container_adapters:
                raise AdapterNotFoundError(f"Container adapter not found: {name}")

            return self._container_adapters[name]

    def set_default_container_adapter(self, name: str) -> None:
        """Set the default container adapter.

        Args:
            name: Name of the adapter to set as default

        Raises:
            AdapterNotFoundError: If the adapter is not registered

        Example:
            >>> registry.set_default_container_adapter("podman")
        """
        with self._lock:
            if name not in self._container_adapters:
                raise AdapterNotFoundError(f"Container adapter not found: {name}")
            self._default_container = name

    # Storage adapter methods

    def register_storage_adapter(self, name: str, adapter: StorageAdapter) -> None:
        """Register a storage backend adapter.

        Args:
            name: Name to register the adapter under
            adapter: Storage backend adapter instance

        Example:
            >>> registry.register_storage_adapter("local", LocalStorageAdapter())
        """
        with self._lock:
            self._storage_adapters[name] = adapter
            if self._default_storage is None:
                self._default_storage = name

    def get_storage_adapter(self, name: str | None = None) -> StorageAdapter:
        """Get a storage backend adapter by name.

        Args:
            name: Name of the adapter to get. If None, returns the default adapter.

        Returns:
            Storage backend adapter instance

        Raises:
            AdapterNotFoundError: If the adapter is not found

        Example:
            >>> adapter = registry.get_storage_adapter()
            >>> adapter = registry.get_storage_adapter("local")
        """
        if not self._initialized and name is None:
            self.initialize_from_config(AdapterConfig())

        with self._lock:
            if name is None:
                name = self._default_storage

            if name is None:
                raise AdapterConfigurationError("No default storage adapter configured")

            if name not in self._storage_adapters:
                raise AdapterNotFoundError(f"Storage adapter not found: {name}")

            return self._storage_adapters[name]

    def set_default_storage_adapter(self, name: str) -> None:
        """Set the default storage adapter.

        Args:
            name: Name of the adapter to set as default

        Raises:
            AdapterNotFoundError: If the adapter is not registered

        Example:
            >>> registry.set_default_storage_adapter("local")
        """
        with self._lock:
            if name not in self._storage_adapters:
                raise AdapterNotFoundError(f"Storage adapter not found: {name}")
            self._default_storage = name

    # Audit adapter methods

    def register_audit_adapter(self, name: str, adapter: AuditAdapter) -> None:
        """Register an audit logger adapter.

        Args:
            name: Name to register the adapter under
            adapter: Audit logger adapter instance

        Example:
            >>> registry.register_audit_adapter("file", FileAuditAdapter())
        """
        with self._lock:
            self._audit_adapters[name] = adapter
            if self._default_audit is None:
                self._default_audit = name

    def get_audit_adapter(self, name: str | None = None) -> AuditAdapter:
        """Get an audit logger adapter by name.

        Args:
            name: Name of the adapter to get. If None, returns the default adapter.

        Returns:
            Audit logger adapter instance

        Raises:
            AdapterNotFoundError: If the adapter is not found

        Example:
            >>> adapter = registry.get_audit_adapter()
            >>> adapter = registry.get_audit_adapter("file")
        """
        if not self._initialized and name is None:
            self.initialize_from_config(AdapterConfig())

        with self._lock:
            if name is None:
                name = self._default_audit

            if name is None:
                raise AdapterConfigurationError("No default audit adapter configured")

            if name not in self._audit_adapters:
                raise AdapterNotFoundError(f"Audit adapter not found: {name}")

            return self._audit_adapters[name]

    def set_default_audit_adapter(self, name: str) -> None:
        """Set the default audit adapter.

        Args:
            name: Name of the adapter to set as default

        Raises:
            AdapterNotFoundError: If the adapter is not registered

        Example:
            >>> registry.set_default_audit_adapter("file")
        """
        with self._lock:
            if name not in self._audit_adapters:
                raise AdapterNotFoundError(f"Audit adapter not found: {name}")
            self._default_audit = name

    # Policy adapter methods

    def register_policy_adapter(self, name: str, adapter: PolicyValidator) -> None:
        """Register a policy validator adapter.

        Args:
            name: Name to register the adapter under
            adapter: Policy validator adapter instance

        Example:
            >>> registry.register_policy_adapter("default", DefaultPolicyValidator())
        """
        with self._lock:
            self._policy_adapters[name] = adapter
            if self._default_policy is None:
                self._default_policy = name

    def get_policy_adapter(self, name: str | None = None) -> PolicyValidator:
        """Get a policy validator adapter by name.

        Args:
            name: Name of the adapter to get. If None, returns the default adapter.

        Returns:
            Policy validator adapter instance

        Raises:
            AdapterNotFoundError: If the adapter is not found

        Example:
            >>> adapter = registry.get_policy_adapter()
            >>> adapter = registry.get_policy_adapter("default")
        """
        if not self._initialized and name is None:
            self.initialize_from_config(AdapterConfig())

        with self._lock:
            if name is None:
                name = self._default_policy

            if name is None:
                raise AdapterConfigurationError("No default policy adapter configured")

            if name not in self._policy_adapters:
                raise AdapterNotFoundError(f"Policy adapter not found: {name}")

            return self._policy_adapters[name]

    def set_default_policy_adapter(self, name: str) -> None:
        """Set the default policy adapter.

        Args:
            name: Name of the adapter to set as default

        Raises:
            AdapterNotFoundError: If the adapter is not registered

        Example:
            >>> registry.set_default_policy_adapter("default")
        """
        with self._lock:
            if name not in self._policy_adapters:
                raise AdapterNotFoundError(f"Policy adapter not found: {name}")
            self._default_policy = name

    # Database adapter methods

    def register_database_adapter(self, name: str, adapter: DatabaseAdapter) -> None:
        """Register a database adapter.

        Args:
            name: Name to register the adapter under
            adapter: Database adapter instance
        """
        with self._lock:
            self._database_adapters[name] = adapter
            if self._default_database is None:
                self._default_database = name

    def get_database_adapter(self, name: str | None = None) -> DatabaseAdapter:
        """Get a database adapter by name.

        Args:
            name: Name of the adapter to get. If None, returns the default adapter.

        Returns:
            Database adapter instance

        Raises:
            AdapterNotFoundError: If the adapter is not found
        """
        if not self._initialized and name is None:
            self.initialize_from_config(AdapterConfig())

        with self._lock:
            if name is None:
                name = self._default_database

            if name is None:
                raise AdapterConfigurationError("No default database adapter configured")

            if name not in self._database_adapters:
                raise AdapterNotFoundError(f"Database adapter not found: {name}")

            return self._database_adapters[name]

    def set_default_database_adapter(self, name: str) -> None:
        """Set the default database adapter."""
        with self._lock:
            if name not in self._database_adapters:
                raise AdapterNotFoundError(f"Database adapter not found: {name}")
            self._default_database = name

    # Utility methods

    def list_adapters(self) -> dict[str, list[str]]:
        """List all registered adapters by type.

        Returns:
            Dictionary mapping adapter types to lists of registered adapter names

        Example:
            >>> adapters = registry.list_adapters()
            >>> print(adapters)
            {
                'container': ['podman', 'docker'],
                'storage': ['local', 's3'],
                'audit': ['file', 'database'],
                'policy': ['default', 'opa']
            }
        """
        with self._lock:
            return {
                "container": list(self._container_adapters.keys()),
                "storage": list(self._storage_adapters.keys()),
                "audit": list(self._audit_adapters.keys()),
                "policy": list(self._policy_adapters.keys()),
                "database": list(self._database_adapters.keys()),
            }

    def clear(self) -> None:
        """Clear all registered adapters (useful for testing).

        Example:
            >>> registry.clear()
        """
        with self._lock:
            self._container_adapters.clear()
            self._storage_adapters.clear()
            self._audit_adapters.clear()
            self._policy_adapters.clear()
            self._database_adapters.clear()
            self._default_container = None
            self._default_storage = None
            self._default_audit = None
            self._default_policy = None
            self._default_database = None
            self._initialized = False


# Global registry instance accessor
def get_registry() -> AdapterRegistry:
    """Get the global adapter registry instance.

    Returns:
        The global AdapterRegistry instance

    Example:
        >>> from isolated_agents_sdk.adapters.registry import get_registry
        >>> registry = get_registry()
    """
    return AdapterRegistry.get_instance()


# Made with Bob
