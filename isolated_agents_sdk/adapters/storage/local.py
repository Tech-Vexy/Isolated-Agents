"""Local filesystem storage adapter."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.exceptions import (
    AdapterInitializationError,
    AdapterOperationError,
)
from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.types import (
    ArtifactMetadata,
    StorageLocation,
    StorageStats,
)


class LocalStorageAdapter(StorageAdapter):
    """Local filesystem storage adapter.
    
    Stores artifacts in a local directory structure organized by session ID.
    
    Directory structure:
        base_path/
            session-123/
                output.txt
                data.json
                .metadata/
                    output.txt.meta
                    data.json.meta
            session-456/
                ...
    
    Example:
        >>> adapter = LocalStorageAdapter(base_path="/tmp/storage")
        >>> await adapter.initialize()
        >>> 
        >>> location = await adapter.store_artifact(
        ...     session_id="session-123",
        ...     artifact_name="output.txt",
        ...     data=b"Hello, World!",
        ...     content_type="text/plain"
        ... )
        >>> print(location.path)
        /tmp/storage/session-123/output.txt
    """
    
    def __init__(self, base_path: str | Path):
        """Initialize local storage adapter.
        
        Args:
            base_path: Base directory for storage
        """
        super().__init__()
        self._base_path = Path(base_path)
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the adapter and create base directory."""
        if self._initialized:
            return
        
        try:
            self._base_path.mkdir(parents=True, exist_ok=True)
            self._initialized = True
        except Exception as e:
            raise AdapterInitializationError(
                f"Failed to create storage directory {self._base_path}: {e}"
            )
    
    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if storage is accessible."""
        try:
            return self._base_path.exists() and self._base_path.is_dir()
        except Exception:
            return False
    
    async def store_artifact(
        self,
        session_id: str,
        artifact_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict[str, str]] = None,
    ) -> StorageLocation:
        """Store an artifact in local filesystem."""
        if not self._initialized:
            await self.initialize()
        
        # Create session directory
        session_dir = self._base_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Create metadata directory
        metadata_dir = session_dir / ".metadata"
        metadata_dir.mkdir(exist_ok=True)
        
        # Write artifact
        artifact_path = session_dir / artifact_name
        try:
            artifact_path.write_bytes(data)
        except Exception as e:
            raise AdapterOperationError(
                f"Failed to write artifact {artifact_name}: {e}"
            )
        
        # Calculate checksum
        checksum = hashlib.sha256(data).hexdigest()
        
        # Write metadata
        meta = ArtifactMetadata(
            session_id=session_id,
            artifact_name=artifact_name,
            size_bytes=len(data),
            content_type=content_type,
            created_at=datetime.now(),
            checksum=checksum,
            tags=metadata or {},
        )
        
        meta_path = metadata_dir / f"{artifact_name}.meta"
        try:
            meta_path.write_text(self._serialize_metadata(meta))
        except Exception as e:
            # Non-fatal - artifact is stored even if metadata fails
            pass
        
        return StorageLocation(
            session_id=session_id,
            artifact_name=artifact_name,
            path=str(artifact_path),
        )
    
    async def retrieve_artifact(
        self,
        session_id: str,
        artifact_name: str,
    ) -> bytes:
        """Retrieve an artifact from local filesystem."""
        artifact_path = self._base_path / session_id / artifact_name
        
        if not artifact_path.exists():
            raise AdapterOperationError(
                f"Artifact {artifact_name} not found in session {session_id}"
            )
        
        try:
            return artifact_path.read_bytes()
        except Exception as e:
            raise AdapterOperationError(
                f"Failed to read artifact {artifact_name}: {e}"
            )
    
    async def delete_artifact(
        self,
        session_id: str,
        artifact_name: str,
    ) -> None:
        """Delete an artifact from local filesystem."""
        artifact_path = self._base_path / session_id / artifact_name
        meta_path = self._base_path / session_id / ".metadata" / f"{artifact_name}.meta"
        
        try:
            if artifact_path.exists():
                artifact_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
        except Exception as e:
            raise AdapterOperationError(
                f"Failed to delete artifact {artifact_name}: {e}"
            )
    
    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactMetadata]:
        """List all artifacts for a session."""
        session_dir = self._base_path / session_id
        
        if not session_dir.exists():
            return []
        
        artifacts = []
        for artifact_path in session_dir.iterdir():
            if artifact_path.is_file() and artifact_path.name != ".metadata":
                try:
                    meta = await self.get_artifact_metadata(session_id, artifact_path.name)
                    artifacts.append(meta)
                except Exception:
                    # If metadata fails, create basic metadata
                    stat = artifact_path.stat()
                    artifacts.append(
                        ArtifactMetadata(
                            session_id=session_id,
                            artifact_name=artifact_path.name,
                            size_bytes=stat.st_size,
                            content_type="application/octet-stream",
                            created_at=datetime.fromtimestamp(stat.st_ctime),
                        )
                    )
        
        return artifacts
    
    async def get_artifact_metadata(
        self,
        session_id: str,
        artifact_name: str,
    ) -> ArtifactMetadata:
        """Get metadata for an artifact."""
        artifact_path = self._base_path / session_id / artifact_name
        meta_path = self._base_path / session_id / ".metadata" / f"{artifact_name}.meta"
        
        if not artifact_path.exists():
            raise AdapterOperationError(
                f"Artifact {artifact_name} not found in session {session_id}"
            )
        
        # Try to load metadata file
        if meta_path.exists():
            try:
                return self._deserialize_metadata(meta_path.read_text())
            except Exception:
                pass
        
        # Fallback to basic metadata from file stats
        stat = artifact_path.stat()
        return ArtifactMetadata(
            session_id=session_id,
            artifact_name=artifact_name,
            size_bytes=stat.st_size,
            content_type="application/octet-stream",
            created_at=datetime.fromtimestamp(stat.st_ctime),
        )
    
    async def artifact_exists(
        self,
        session_id: str,
        artifact_name: str,
    ) -> bool:
        """Check if an artifact exists."""
        artifact_path = self._base_path / session_id / artifact_name
        return artifact_path.exists()
    
    async def delete_session(
        self,
        session_id: str,
    ) -> None:
        """Delete all artifacts for a session."""
        session_dir = self._base_path / session_id
        
        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
            except Exception as e:
                raise AdapterOperationError(
                    f"Failed to delete session {session_id}: {e}"
                )
    
    async def get_storage_stats(self) -> StorageStats:
        """Get storage usage statistics."""
        total_artifacts = 0
        total_size = 0
        sessions = set()
        oldest = None
        newest = None
        
        for session_dir in self._base_path.iterdir():
            if session_dir.is_dir():
                sessions.add(session_dir.name)
                
                for artifact_path in session_dir.iterdir():
                    if artifact_path.is_file() and artifact_path.name != ".metadata":
                        total_artifacts += 1
                        stat = artifact_path.stat()
                        total_size += stat.st_size
                        
                        created = datetime.fromtimestamp(stat.st_ctime)
                        if oldest is None or created < oldest:
                            oldest = created
                        if newest is None or created > newest:
                            newest = created
        
        return StorageStats(
            total_artifacts=total_artifacts,
            total_size_bytes=total_size,
            sessions=len(sessions),
            oldest_artifact=oldest,
            newest_artifact=newest,
        )
    
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    
    def _serialize_metadata(self, meta: ArtifactMetadata) -> str:
        """Serialize metadata to string."""
        import json
        return json.dumps({
            "session_id": meta.session_id,
            "artifact_name": meta.artifact_name,
            "size_bytes": meta.size_bytes,
            "content_type": meta.content_type,
            "created_at": meta.created_at.isoformat(),
            "checksum": meta.checksum,
            "tags": meta.tags,
        })
    
    def _deserialize_metadata(self, data: str) -> ArtifactMetadata:
        """Deserialize metadata from string."""
        import json
        obj = json.loads(data)
        return ArtifactMetadata(
            session_id=obj["session_id"],
            artifact_name=obj["artifact_name"],
            size_bytes=obj["size_bytes"],
            content_type=obj["content_type"],
            created_at=datetime.fromisoformat(obj["created_at"]),
            checksum=obj.get("checksum"),
            tags=obj.get("tags", {}),
        )

# Made with Bob