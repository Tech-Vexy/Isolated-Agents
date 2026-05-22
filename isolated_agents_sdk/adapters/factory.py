"""Adapter factory for creating adapter instances."""

from __future__ import annotations

from typing import Optional, Type

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.container.docker import DockerAdapter
from isolated_agents_sdk.adapters.container.kubernetes import KubernetesAdapter
from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
from isolated_agents_sdk.adapters.audit.telemetry import TelemetryAuditAdapter
from isolated_agents_sdk.adapters.audit.composite import CompositeAuditAdapter
from isolated_agents_sdk.adapters.audit.stderr import StderrAuditAdapter
from isolated_agents_sdk.adapters.exceptions import AdapterNotFoundError
from isolated_agents_sdk.adapters.policy.base import PolicyValidator
from isolated_agents_sdk.adapters.policy.default import DefaultPolicyValidator
from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.local import LocalStorageAdapter
from isolated_agents_sdk.adapters.database.base import DatabaseAdapter
from isolated_agents_sdk.adapters.database.sql import SQLDatabaseAdapter
from isolated_agents_sdk.adapters.database.nosql import NoSQLDatabaseAdapter
from isolated_agents_sdk.adapters.database.vector import VectorDatabaseAdapter


class AdapterFactory:
    """Factory for creating adapter instances.
    
    This factory provides centralized adapter creation and registration.
    It supports multiple adapter types (container, storage, audit, policy)
    and allows custom adapter registration.
    
    Example:
        >>> # Create default Podman adapter
        >>> adapter = AdapterFactory.create_container_adapter()
        >>> 
        >>> # Create adapter with custom configuration
        >>> adapter = AdapterFactory.create_container_adapter(
        ...     adapter_type="podman",
        ...     base_image="python:3.11-slim"
        ... )
        >>> 
        >>> # Register custom adapter
        >>> AdapterFactory.register_container_adapter("custom", CustomAdapter)
        >>> adapter = AdapterFactory.create_container_adapter("custom")
    """
    
    _container_adapters: dict[str, Type[ContainerRuntimeAdapter]] = {
        "podman": PodmanAdapter,
        "docker": DockerAdapter,
        "kubernetes": KubernetesAdapter,
    }
    
    _storage_adapters: dict[str, Type[StorageAdapter]] = {
        "local": LocalStorageAdapter,
    }
    
    _audit_adapters: dict[str, Type[AuditAdapter]] = {
        "file": FileAuditAdapter,
        "telemetry": TelemetryAuditAdapter,
        "composite": CompositeAuditAdapter,
        "stderr": StderrAuditAdapter,
    }
    
    _policy_adapters: dict[str, Type[PolicyValidator]] = {
        "default": DefaultPolicyValidator,
    }
    
    _database_adapters: dict[str, Type[DatabaseAdapter]] = {
        "sql": SQLDatabaseAdapter,
        "nosql": NoSQLDatabaseAdapter,
        "vector": VectorDatabaseAdapter,
    }
    
    @classmethod
    def create_container_adapter(
        cls,
        adapter_type: str = "podman",
        **kwargs,
    ) -> ContainerRuntimeAdapter:
        """Create a container runtime adapter.
        
        Args:
            adapter_type: Type of adapter ("podman", "docker", "kubernetes")
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            ContainerRuntimeAdapter instance
        
        Raises:
            AdapterNotFoundError: If adapter type is not registered
        
        Example:
            >>> adapter = AdapterFactory.create_container_adapter("podman")
            >>> await adapter.initialize()
            >>> handle = await adapter.provision_container(...)
        """
        adapter_class = cls._container_adapters.get(adapter_type)
        if adapter_class is None:
            raise AdapterNotFoundError(
                f"Container adapter '{adapter_type}' not found. "
                f"Available adapters: {list(cls._container_adapters.keys())}"
            )
        
        return adapter_class(**kwargs)
    
    @classmethod
    def register_container_adapter(
        cls,
        name: str,
        adapter_class: Type[ContainerRuntimeAdapter],
    ) -> None:
        """Register a custom container adapter.
        
        This allows users to register their own adapter implementations
        that can be created through the factory.
        
        Args:
            name: Adapter name (e.g., "docker", "kubernetes")
            adapter_class: Adapter class that extends ContainerRuntimeAdapter
        
        Example:
            >>> class MyAdapter(ContainerRuntimeAdapter):
            ...     async def provision_container(self, ...): ...
            >>> 
            >>> AdapterFactory.register_container_adapter("my-adapter", MyAdapter)
            >>> adapter = AdapterFactory.create_container_adapter("my-adapter")
        """
        cls._container_adapters[name] = adapter_class
    
    @classmethod
    def list_container_adapters(cls) -> list[str]:
        """List available container adapters.
        
        Returns:
            List of registered adapter names
        
        Example:
            >>> adapters = AdapterFactory.list_container_adapters()
            >>> print(adapters)
            ['podman', 'docker', 'kubernetes']
        """
        return list(cls._container_adapters.keys())
    
    @classmethod
    def get_default_container_adapter(cls) -> str:
        """Get the default container adapter type.
        
        Returns:
            Default adapter type name
        """
        return "podman"
    
    @classmethod
    def create_storage_adapter(
        cls,
        adapter_type: str = "local",
        **kwargs,
    ) -> StorageAdapter:
        """Create a storage adapter.
        
        Args:
            adapter_type: Type of adapter ("local", "s3", "azure", "gcs")
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            StorageAdapter instance
        
        Raises:
            AdapterNotFoundError: If adapter type is not registered
        
        Example:
            >>> adapter = AdapterFactory.create_storage_adapter("local", base_path="/tmp/storage")
            >>> await adapter.initialize()
            >>> location = await adapter.store_artifact(...)
        """
        adapter_class = cls._storage_adapters.get(adapter_type)
        if adapter_class is None:
            raise AdapterNotFoundError(
                f"Storage adapter '{adapter_type}' not found. "
                f"Available adapters: {list(cls._storage_adapters.keys())}"
            )
        
        return adapter_class(**kwargs)
    
    @classmethod
    def register_storage_adapter(
        cls,
        name: str,
        adapter_class: Type[StorageAdapter],
    ) -> None:
        """Register a custom storage adapter.
        
        Args:
            name: Adapter name (e.g., "s3", "azure", "gcs")
            adapter_class: Adapter class that extends StorageAdapter
        
        Example:
            >>> class MyStorageAdapter(StorageAdapter):
            ...     async def store_artifact(self, ...): ...
            >>>
            >>> AdapterFactory.register_storage_adapter("my-storage", MyStorageAdapter)
            >>> adapter = AdapterFactory.create_storage_adapter("my-storage")
        """
        cls._storage_adapters[name] = adapter_class
    
    @classmethod
    def list_storage_adapters(cls) -> list[str]:
        """List available storage adapters.
        
        Returns:
            List of registered adapter names
        
        Example:
            >>> adapters = AdapterFactory.list_storage_adapters()
            >>> print(adapters)
            ['local', 's3', 'azure', 'gcs']
        """
        return list(cls._storage_adapters.keys())
    
    @classmethod
    def get_default_storage_adapter(cls) -> str:
        """Get the default storage adapter type.
        
        Returns:
            Default adapter type name
        """
        return "local"
    
    @classmethod
    def create_audit_adapter(
        cls,
        adapter_type: str = "file",
        **kwargs,
    ) -> AuditAdapter:
        """Create an audit logger adapter.
        
        Args:
            adapter_type: Type of adapter ("file", "telemetry", "composite")
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            AuditAdapter instance
        
        Raises:
            AdapterNotFoundError: If adapter type is not registered
        
        Example:
            >>> adapter = AdapterFactory.create_audit_adapter("file", log_path="/var/log/agents")
            >>> await adapter.initialize()
            >>> await adapter.log_event(...)
        """
        adapter_class = cls._audit_adapters.get(adapter_type)
        if adapter_class is None:
            raise AdapterNotFoundError(
                f"Audit adapter '{adapter_type}' not found. "
                f"Available adapters: {list(cls._audit_adapters.keys())}"
            )
        
        return adapter_class(**kwargs)
    
    @classmethod
    def register_audit_adapter(
        cls,
        name: str,
        adapter_class: Type[AuditAdapter],
    ) -> None:
        """Register a custom audit adapter.
        
        Args:
            name: Adapter name (e.g., "database", "cloudwatch")
            adapter_class: Adapter class that extends AuditAdapter
        
        Example:
            >>> class MyAuditAdapter(AuditAdapter):
            ...     async def log_event(self, ...): ...
            >>>
            >>> AdapterFactory.register_audit_adapter("my-audit", MyAuditAdapter)
            >>> adapter = AdapterFactory.create_audit_adapter("my-audit")
        """
        cls._audit_adapters[name] = adapter_class
    
    @classmethod
    def list_audit_adapters(cls) -> list[str]:
        """List available audit adapters.
        
        Returns:
            List of registered adapter names
        
        Example:
            >>> adapters = AdapterFactory.list_audit_adapters()
            >>> print(adapters)
            ['file', 'database', 'cloudwatch']
        """
        return list(cls._audit_adapters.keys())
    
    @classmethod
    def get_default_audit_adapter(cls) -> str:
        """Get the default audit adapter type.
        
        Returns:
            Default adapter type name
        """
        return "file"
    
    @classmethod
    def create_policy_adapter(
        cls,
        adapter_type: str = "default",
        **kwargs,
    ) -> PolicyValidator:
        """Create a policy validator adapter.
        
        Args:
            adapter_type: Type of adapter ("default", "opa", "custom")
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            PolicyValidator instance
        
        Raises:
            AdapterNotFoundError: If adapter type is not registered
        
        Example:
            >>> adapter = AdapterFactory.create_policy_adapter("default")
            >>> await adapter.initialize()
            >>> result = await adapter.validate_policy(policy)
        """
        adapter_class = cls._policy_adapters.get(adapter_type)
        if adapter_class is None:
            raise AdapterNotFoundError(
                f"Policy adapter '{adapter_type}' not found. "
                f"Available adapters: {list(cls._policy_adapters.keys())}"
            )
        
        return adapter_class(**kwargs)
    
    @classmethod
    def register_policy_adapter(
        cls,
        name: str,
        adapter_class: Type[PolicyValidator],
    ) -> None:
        """Register a custom policy adapter.
        
        Args:
            name: Adapter name (e.g., "opa", "custom")
            adapter_class: Adapter class that extends PolicyValidator
        
        Example:
            >>> class MyPolicyValidator(PolicyValidator):
            ...     async def validate_policy(self, ...): ...
            >>>
            >>> AdapterFactory.register_policy_adapter("my-policy", MyPolicyValidator)
            >>> adapter = AdapterFactory.create_policy_adapter("my-policy")
        """
        cls._policy_adapters[name] = adapter_class
    
    @classmethod
    def list_policy_adapters(cls) -> list[str]:
        """List available policy adapters.
        
        Returns:
            List of registered adapter names
        
        Example:
            >>> adapters = AdapterFactory.list_policy_adapters()
            >>> print(adapters)
            ['default', 'opa', 'custom']
        """
        return list(cls._policy_adapters.keys())
    
    @classmethod
    def get_default_policy_adapter(cls) -> str:
        """Get the default policy adapter type.
        
        Returns:
            Default adapter type name
        """
        return "default"

    @classmethod
    def create_database_adapter(
        cls,
        adapter_type: str = "sql",
        **kwargs,
    ) -> DatabaseAdapter:
        """Create a database adapter.
        
        Args:
            adapter_type: Type of adapter ("sql", "nosql", "vector")
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            DatabaseAdapter instance
        
        Raises:
            AdapterNotFoundError: If adapter type is not registered
        """
        adapter_class = cls._database_adapters.get(adapter_type)
        if adapter_class is None:
            raise AdapterNotFoundError(
                f"Database adapter '{adapter_type}' not found. "
                f"Available adapters: {list(cls._database_adapters.keys())}"
            )
        
        return adapter_class(**kwargs)

    @classmethod
    def register_database_adapter(
        cls,
        name: str,
        adapter_class: Type[DatabaseAdapter],
    ) -> None:
        """Register a custom database adapter."""
        cls._database_adapters[name] = adapter_class

    @classmethod
    def list_database_adapters(cls) -> list[str]:
        """List available database adapters."""
        return list(cls._database_adapters.keys())

    @classmethod
    def get_default_database_adapter(cls) -> str:
        """Get the default database adapter type."""
        return "sql"

# Made with Bob
