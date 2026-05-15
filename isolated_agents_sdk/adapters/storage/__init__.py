"""Storage backend adapters for the Isolated Agents SDK.

This package provides pluggable storage adapters for:
- Local filesystem storage
- AWS S3
- Azure Blob Storage
- Google Cloud Storage
- MinIO and S3-compatible services

Example usage:
    from isolated_agents_sdk.adapters.storage import LocalStorageAdapter
    from isolated_agents_sdk.adapters.factory import AdapterFactory
    
    # Create local storage adapter
    adapter = AdapterFactory.create_storage_adapter("local", base_path="/tmp/storage")
    await adapter.initialize()
    
    # Store artifact
    await adapter.store_artifact("session-123", "output.txt", b"Hello, World!")
    
    # Retrieve artifact
    data = await adapter.retrieve_artifact("session-123", "output.txt")
"""

from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.local import LocalStorageAdapter
from isolated_agents_sdk.adapters.storage.types import (
    ArtifactMetadata,
    StorageLocation,
    StorageStats,
)

__all__ = [
    "StorageAdapter",
    "LocalStorageAdapter",
    "ArtifactMetadata",
    "StorageLocation",
    "StorageStats",
]

# Made with Bob