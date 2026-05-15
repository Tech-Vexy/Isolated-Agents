"""Adapter interfaces and implementations for the Isolated Agents SDK.

This package provides pluggable adapters for:
- Container runtimes (Podman, Docker, Kubernetes)
- Storage backends (Local, S3, Azure, GCS)
- Audit loggers (File, Database, CloudWatch, Datadog)
- Policy validators (Default, OPA, Custom)

Example usage:
    from isolated_agents_sdk.adapters.container import PodmanAdapter
    from isolated_agents_sdk.factory import AdapterFactory
    
    # Register and create adapter
    adapter = await AdapterFactory.create_container_adapter("podman")
"""

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    EventType,
)
from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.config import AdapterConfig, load_config
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.container.types import (
    ContainerHandle,
    ContainerStats,
    ExecResult,
    Mount,
    NetworkConfig,
    ResourceLimits,
    SecurityConfig,
)
from isolated_agents_sdk.adapters.exceptions import (
    AdapterConfigurationError,
    AdapterError,
    AdapterInitializationError,
    AdapterNotFoundError,
    AdapterOperationError,
)
from isolated_agents_sdk.adapters.factory import AdapterFactory
from isolated_agents_sdk.adapters.policy.base import PolicyValidator
from isolated_agents_sdk.adapters.policy.default import DefaultPolicyValidator
from isolated_agents_sdk.adapters.policy.types import (
    PolicyConstraints,
    PolicyValidationResult,
    ValidationError,
)
from isolated_agents_sdk.adapters.registry import AdapterRegistry, get_registry
from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.local import LocalStorageAdapter
from isolated_agents_sdk.adapters.storage.types import (
    ArtifactMetadata,
    StorageLocation,
    StorageStats,
)

__all__ = [
    # Base classes
    "BaseAdapter",
    "ContainerRuntimeAdapter",
    "StorageAdapter",
    "AuditAdapter",
    "PolicyValidator",
    # Container adapters
    "PodmanAdapter",
    # Storage adapters
    "LocalStorageAdapter",
    # Audit adapters
    "FileAuditAdapter",
    # Policy adapters
    "DefaultPolicyValidator",
    # Factory
    "AdapterFactory",
    # Configuration
    "AdapterConfig",
    "load_config",
    # Registry
    "AdapterRegistry",
    "get_registry",
    # Container types
    "ContainerHandle",
    "ContainerStats",
    "ExecResult",
    "Mount",
    "NetworkConfig",
    "ResourceLimits",
    "SecurityConfig",
    # Storage types
    "ArtifactMetadata",
    "StorageLocation",
    "StorageStats",
    # Audit types
    "AuditEvent",
    "AuditQuery",
    "EventType",
    # Policy types
    "PolicyConstraints",
    "PolicyValidationResult",
    "ValidationError",
    # Exceptions
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterConfigurationError",
    "AdapterInitializationError",
    "AdapterOperationError",
]

# Made with Bob
