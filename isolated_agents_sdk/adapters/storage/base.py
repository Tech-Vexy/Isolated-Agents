"""Base interface for storage adapters."""

from __future__ import annotations

from abc import abstractmethod
from typing import Optional

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.storage.types import (
    ArtifactMetadata,
    StorageLocation,
    StorageStats,
)


class StorageAdapter(BaseAdapter):
    """Abstract base class for storage adapters.

    Implementations must provide methods for storing, retrieving, and managing
    artifacts across different storage backends (local filesystem, S3, Azure, GCS).

    Lifecycle:
        1. Initialize adapter
        2. Store/retrieve artifacts
        3. List and manage artifacts
        4. Cleanup adapter

    Example:
        >>> adapter = LocalStorageAdapter(base_path="/tmp/storage")
        >>> await adapter.initialize()
        >>>
        >>> # Store artifact
        >>> location = await adapter.store_artifact(
        ...     session_id="session-123",
        ...     artifact_name="output.txt",
        ...     data=b"Hello, World!",
        ...     content_type="text/plain"
        ... )
        >>>
        >>> # Retrieve artifact
        >>> data = await adapter.retrieve_artifact("session-123", "output.txt")
        >>>
        >>> # List artifacts
        >>> artifacts = await adapter.list_artifacts("session-123")
        >>>
        >>> await adapter.cleanup()
    """

    @abstractmethod
    async def store_artifact(
        self,
        session_id: str,
        artifact_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StorageLocation:
        """Store an artifact.

        Args:
            session_id: Session identifier
            artifact_name: Name of the artifact
            data: Artifact data as bytes
            content_type: MIME type
            metadata: Optional key-value metadata

        Returns:
            StorageLocation with path and optional URL

        Raises:
            AdapterOperationError: If storage operation fails
        """
        pass

    @abstractmethod
    async def retrieve_artifact(
        self,
        session_id: str,
        artifact_name: str,
    ) -> bytes:
        """Retrieve an artifact.

        Args:
            session_id: Session identifier
            artifact_name: Name of the artifact

        Returns:
            Artifact data as bytes

        Raises:
            AdapterOperationError: If artifact not found or retrieval fails
        """
        pass

    @abstractmethod
    async def delete_artifact(
        self,
        session_id: str,
        artifact_name: str,
    ) -> None:
        """Delete an artifact.

        Args:
            session_id: Session identifier
            artifact_name: Name of the artifact

        Raises:
            AdapterOperationError: If deletion fails
        """
        pass

    @abstractmethod
    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactMetadata]:
        """List all artifacts for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of artifact metadata
        """
        pass

    @abstractmethod
    async def get_artifact_metadata(
        self,
        session_id: str,
        artifact_name: str,
    ) -> ArtifactMetadata:
        """Get metadata for an artifact.

        Args:
            session_id: Session identifier
            artifact_name: Name of the artifact

        Returns:
            Artifact metadata

        Raises:
            AdapterOperationError: If artifact not found
        """
        pass

    @abstractmethod
    async def artifact_exists(
        self,
        session_id: str,
        artifact_name: str,
    ) -> bool:
        """Check if an artifact exists.

        Args:
            session_id: Session identifier
            artifact_name: Name of the artifact

        Returns:
            True if artifact exists, False otherwise
        """
        pass

    async def delete_session(
        self,
        session_id: str,
    ) -> None:
        """Delete all artifacts for a session.

        This is an optional method that may be implemented by adapters.

        Args:
            session_id: Session identifier
        """
        artifacts = await self.list_artifacts(session_id)
        for artifact in artifacts:
            await self.delete_artifact(session_id, artifact.artifact_name)

    async def get_storage_stats(self) -> StorageStats:
        """Get storage usage statistics.

        This is an optional method that may be implemented by adapters.

        Returns:
            Storage statistics
        """
        return StorageStats(
            total_artifacts=0,
            total_size_bytes=0,
            sessions=0,
        )

    async def generate_presigned_url(
        self,
        session_id: str,
        artifact_name: str,
        expiration_seconds: int = 3600,
    ) -> str:
        """Generate a presigned URL for direct artifact access.

        This is an optional method that may be implemented by cloud storage adapters.

        Args:
            session_id: Session identifier
            artifact_name: Name of the artifact
            expiration_seconds: URL expiration time in seconds

        Returns:
            Presigned URL

        Raises:
            NotImplementedError: If adapter doesn't support presigned URLs
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support presigned URLs")


# Made with Bob
