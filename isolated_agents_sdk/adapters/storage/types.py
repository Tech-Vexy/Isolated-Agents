"""Type definitions for storage adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class StorageLocation:
    """Location of stored artifact.
    
    Attributes:
        session_id: Session identifier
        artifact_name: Name of the artifact
        path: Full path to artifact in storage backend
        url: Optional URL for direct access (e.g., presigned S3 URL)
    """
    session_id: str
    artifact_name: str
    path: str
    url: Optional[str] = None


@dataclass
class ArtifactMetadata:
    """Metadata for a stored artifact.
    
    Attributes:
        session_id: Session identifier
        artifact_name: Name of the artifact
        size_bytes: Size in bytes
        content_type: MIME type (e.g., "text/plain", "application/json")
        created_at: Creation timestamp
        checksum: Optional checksum (e.g., MD5, SHA256)
        tags: Optional key-value tags
    """
    session_id: str
    artifact_name: str
    size_bytes: int
    content_type: str
    created_at: datetime
    checksum: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class StorageStats:
    """Storage usage statistics.
    
    Attributes:
        total_artifacts: Total number of artifacts
        total_size_bytes: Total size in bytes
        sessions: Number of unique sessions
        oldest_artifact: Timestamp of oldest artifact
        newest_artifact: Timestamp of newest artifact
    """
    total_artifacts: int
    total_size_bytes: int
    sessions: int
    oldest_artifact: Optional[datetime] = None
    newest_artifact: Optional[datetime] = None


@dataclass
class StorageConfig:
    """Configuration for storage adapters.
    
    Attributes:
        base_path: Base path for storage (filesystem or bucket name)
        region: Cloud region (for S3, Azure, GCS)
        endpoint_url: Custom endpoint URL (for MinIO, etc.)
        access_key: Access key ID
        secret_key: Secret access key
        encryption: Enable encryption at rest
        compression: Enable compression
        retention_days: Artifact retention period in days (0 = forever)
    """
    base_path: str
    region: Optional[str] = None
    endpoint_url: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    encryption: bool = True
    compression: bool = False
    retention_days: int = 0

# Made with Bob