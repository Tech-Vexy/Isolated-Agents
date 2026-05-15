# Extending Adapters Guide

This guide shows you how to create custom adapter implementations for the Isolated Agents SDK.

## Overview

The adapter pattern allows you to:
- **Create custom implementations** for different backends
- **Extend existing adapters** with additional functionality
- **Integrate third-party services** seamlessly
- **Test with mock adapters** easily

## Adapter Types

The SDK provides four adapter types:

1. **Container Runtime Adapters** - Manage container lifecycle
2. **Storage Backend Adapters** - Store and retrieve artifacts
3. **Audit Logger Adapters** - Log and query audit events
4. **Policy Validator Adapters** - Validate policies

## Creating a Custom Container Adapter

### Step 1: Implement the Interface

```python
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import (
    ContainerHandle,
    ExecResult,
    ContainerStats,
    Mount,
    ResourceLimits,
    NetworkConfig,
    SecurityConfig,
)
from isolated_agents_sdk.adapters.exceptions import AdapterOperationError

class DockerAdapter(ContainerRuntimeAdapter):
    """Docker container runtime adapter.
    
    This adapter uses Docker instead of Podman for container management.
    """
    
    def __init__(self, socket_path: str = "/var/run/docker.sock", **kwargs):
        """Initialize Docker adapter.
        
        Args:
            socket_path: Path to Docker socket
            **kwargs: Additional configuration
        """
        super().__init__()
        self._socket_path = socket_path
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize Docker client."""
        try:
            import docker
            self._client = docker.DockerClient(base_url=f"unix://{self._socket_path}")
            await super().initialize()
        except ImportError:
            raise AdapterOperationError(
                "Docker Python SDK not installed. Install with: pip install docker"
            )
        except Exception as e:
            raise AdapterOperationError(f"Failed to initialize Docker client: {e}")
    
    async def create_container(
        self,
        image: str,
        command: list[str],
        working_dir: str,
        mounts: list[Mount] | None = None,
        resource_limits: ResourceLimits | None = None,
        network_config: NetworkConfig | None = None,
        security_config: SecurityConfig | None = None,
        environment: dict[str, str] | None = None,
    ) -> ContainerHandle:
        """Create a Docker container."""
        try:
            # Build Docker configuration
            volumes = {}
            if mounts:
                for mount in mounts:
                    volumes[mount.source] = {
                        "bind": mount.target,
                        "mode": "ro" if mount.readonly else "rw"
                    }
            
            # Resource limits
            mem_limit = None
            cpu_quota = None
            if resource_limits:
                mem_limit = f"{resource_limits.memory_mb}m"
                cpu_quota = int(resource_limits.cpu_cores * 100000)
            
            # Create container
            container = self._client.containers.create(
                image=image,
                command=command,
                working_dir=working_dir,
                volumes=volumes,
                mem_limit=mem_limit,
                cpu_quota=cpu_quota,
                environment=environment or {},
                detach=True,
                network_disabled=network_config.disabled if network_config else True,
            )
            
            # Start container
            container.start()
            
            return ContainerHandle(container_id=container.id)
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to create Docker container: {e}")
    
    async def execute_command(
        self,
        handle: ContainerHandle,
        command: list[str],
        timeout: int | None = None,
    ) -> ExecResult:
        """Execute command in Docker container."""
        try:
            container = self._client.containers.get(handle.container_id)
            
            exec_result = container.exec_run(
                command,
                stdout=True,
                stderr=True,
            )
            
            return ExecResult(
                exit_code=exec_result.exit_code,
                stdout=exec_result.output.decode("utf-8", errors="replace"),
                stderr="",  # Docker combines stdout/stderr
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to execute command: {e}")
    
    async def stop_container(self, handle: ContainerHandle, timeout: int = 10) -> None:
        """Stop Docker container."""
        try:
            container = self._client.containers.get(handle.container_id)
            container.stop(timeout=timeout)
        except Exception as e:
            raise AdapterOperationError(f"Failed to stop container: {e}")
    
    async def remove_container(self, handle: ContainerHandle, force: bool = False) -> None:
        """Remove Docker container."""
        try:
            container = self._client.containers.get(handle.container_id)
            container.remove(force=force)
        except Exception as e:
            raise AdapterOperationError(f"Failed to remove container: {e}")
    
    async def get_container_stats(self, handle: ContainerHandle) -> ContainerStats:
        """Get Docker container statistics."""
        try:
            container = self._client.containers.get(handle.container_id)
            stats = container.stats(stream=False)
            
            # Parse Docker stats
            cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
            memory_usage = stats["memory_stats"]["usage"]
            
            return ContainerStats(
                cpu_usage_percent=0.0,  # Calculate from stats
                memory_usage_bytes=memory_usage,
                network_rx_bytes=0,
                network_tx_bytes=0,
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to get container stats: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup Docker client."""
        if self._client:
            self._client.close()
        await super().cleanup()
```

### Step 2: Register the Adapter

```python
from isolated_agents_sdk.adapters import AdapterFactory

# Register with factory
AdapterFactory.register_container_adapter("docker", DockerAdapter)

# Now you can create it
docker = AdapterFactory.create_container_adapter("docker")
```

### Step 3: Use in Configuration

```yaml
# config.yaml
container_adapter: docker
container_config:
  socket_path: /var/run/docker.sock
```

## Creating a Custom Storage Adapter

### Example: S3 Storage Adapter

```python
from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.types import (
    StorageLocation,
    ArtifactMetadata,
    StorageStats,
)
from isolated_agents_sdk.adapters.exceptions import AdapterOperationError

class S3StorageAdapter(StorageAdapter):
    """Amazon S3 storage adapter."""
    
    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        prefix: str = "",
        **kwargs
    ):
        """Initialize S3 adapter.
        
        Args:
            bucket_name: S3 bucket name
            region: AWS region
            prefix: Key prefix for all objects
            **kwargs: Additional configuration
        """
        super().__init__()
        self._bucket_name = bucket_name
        self._region = region
        self._prefix = prefix
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize S3 client."""
        try:
            import boto3
            self._client = boto3.client("s3", region_name=self._region)
            await super().initialize()
        except ImportError:
            raise AdapterOperationError(
                "boto3 not installed. Install with: pip install boto3"
            )
        except Exception as e:
            raise AdapterOperationError(f"Failed to initialize S3 client: {e}")
    
    async def store_artifact(
        self,
        session_id: str,
        artifact_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StorageLocation:
        """Store artifact in S3."""
        try:
            # Build S3 key
            key = f"{self._prefix}{session_id}/{artifact_name}"
            
            # Upload to S3
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=metadata or {},
            )
            
            # Generate URL
            url = f"s3://{self._bucket_name}/{key}"
            
            return StorageLocation(path=key, url=url)
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to store artifact in S3: {e}")
    
    async def retrieve_artifact(
        self,
        session_id: str,
        artifact_name: str,
    ) -> bytes:
        """Retrieve artifact from S3."""
        try:
            key = f"{self._prefix}{session_id}/{artifact_name}"
            
            response = self._client.get_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            
            return response["Body"].read()
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to retrieve artifact from S3: {e}")
    
    async def delete_artifact(
        self,
        session_id: str,
        artifact_name: str,
    ) -> None:
        """Delete artifact from S3."""
        try:
            key = f"{self._prefix}{session_id}/{artifact_name}"
            
            self._client.delete_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to delete artifact from S3: {e}")
    
    async def list_artifacts(
        self,
        session_id: str,
        prefix: str | None = None,
    ) -> list[ArtifactMetadata]:
        """List artifacts in S3."""
        try:
            list_prefix = f"{self._prefix}{session_id}/"
            if prefix:
                list_prefix += prefix
            
            response = self._client.list_objects_v2(
                Bucket=self._bucket_name,
                Prefix=list_prefix,
            )
            
            artifacts = []
            for obj in response.get("Contents", []):
                # Extract artifact name from key
                artifact_name = obj["Key"][len(list_prefix):]
                
                artifacts.append(ArtifactMetadata(
                    session_id=session_id,
                    artifact_name=artifact_name,
                    size_bytes=obj["Size"],
                    content_type="application/octet-stream",
                    created_at=obj["LastModified"].isoformat(),
                    checksum=obj.get("ETag", "").strip('"'),
                ))
            
            return artifacts
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to list artifacts in S3: {e}")
    
    async def get_artifact_metadata(
        self,
        session_id: str,
        artifact_name: str,
    ) -> ArtifactMetadata:
        """Get artifact metadata from S3."""
        try:
            key = f"{self._prefix}{session_id}/{artifact_name}"
            
            response = self._client.head_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            
            return ArtifactMetadata(
                session_id=session_id,
                artifact_name=artifact_name,
                size_bytes=response["ContentLength"],
                content_type=response.get("ContentType", "application/octet-stream"),
                created_at=response["LastModified"].isoformat(),
                checksum=response.get("ETag", "").strip('"'),
                metadata=response.get("Metadata", {}),
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to get artifact metadata: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup S3 client."""
        self._client = None
        await super().cleanup()
```

## Creating a Custom Audit Adapter

### Example: Database Audit Adapter

```python
from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    AuditStats,
    EventType,
)
from isolated_agents_sdk.adapters.exceptions import AdapterOperationError
from datetime import datetime, timezone
import uuid

class DatabaseAuditAdapter(AuditAdapter):
    """Database audit logger adapter using PostgreSQL."""
    
    def __init__(
        self,
        connection_string: str,
        table_name: str = "audit_events",
        **kwargs
    ):
        """Initialize database adapter.
        
        Args:
            connection_string: PostgreSQL connection string
            table_name: Name of the audit events table
            **kwargs: Additional configuration
        """
        super().__init__()
        self._connection_string = connection_string
        self._table_name = table_name
        self._pool = None
    
    async def initialize(self) -> None:
        """Initialize database connection pool."""
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._connection_string)
            
            # Create table if it doesn't exist
            async with self._pool.acquire() as conn:
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        session_id TEXT NOT NULL,
                        agent_id TEXT NOT NULL,
                        user_id TEXT,
                        severity TEXT NOT NULL,
                        payload JSONB,
                        tags JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                
                # Create indexes
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_session_id 
                    ON {self._table_name}(session_id)
                """)
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON {self._table_name}(timestamp)
                """)
            
            await super().initialize()
            
        except ImportError:
            raise AdapterOperationError(
                "asyncpg not installed. Install with: pip install asyncpg"
            )
        except Exception as e:
            raise AdapterOperationError(f"Failed to initialize database: {e}")
    
    async def log_event(
        self,
        event_type: EventType,
        session_id: str,
        agent_id: str,
        payload: dict | None = None,
        user_id: str | None = None,
        severity: str = "info",
        tags: dict[str, str] | None = None,
    ) -> str:
        """Log event to database."""
        try:
            event_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc)
            
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name}
                    (event_id, event_type, timestamp, session_id, agent_id, 
                     user_id, severity, payload, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    event_id,
                    event_type.value,
                    timestamp,
                    session_id,
                    agent_id,
                    user_id,
                    severity,
                    payload,
                    tags,
                )
            
            return event_id
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to log event: {e}")
    
    async def query_events(self, query: AuditQuery) -> list[AuditEvent]:
        """Query events from database."""
        try:
            # Build SQL query
            conditions = []
            params = []
            param_count = 1
            
            if query.session_id:
                conditions.append(f"session_id = ${param_count}")
                params.append(query.session_id)
                param_count += 1
            
            if query.agent_id:
                conditions.append(f"agent_id = ${param_count}")
                params.append(query.agent_id)
                param_count += 1
            
            if query.event_types:
                placeholders = ",".join([f"${i}" for i in range(param_count, param_count + len(query.event_types))])
                conditions.append(f"event_type IN ({placeholders})")
                params.extend([et.value for et in query.event_types])
                param_count += len(query.event_types)
            
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            sql = f"""
                SELECT event_id, event_type, timestamp, session_id, agent_id,
                       user_id, severity, payload, tags
                FROM {self._table_name}
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_count}
            """
            params.append(query.limit)
            
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            
            events = []
            for row in rows:
                events.append(AuditEvent(
                    event_id=row["event_id"],
                    event_type=EventType(row["event_type"]),
                    timestamp=row["timestamp"].isoformat(),
                    session_id=row["session_id"],
                    agent_id=row["agent_id"],
                    user_id=row["user_id"],
                    severity=row["severity"],
                    payload=row["payload"],
                    tags=row["tags"],
                ))
            
            return events
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to query events: {e}")
    
    async def get_event(self, event_id: str) -> AuditEvent:
        """Get specific event from database."""
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT event_id, event_type, timestamp, session_id, agent_id,
                           user_id, severity, payload, tags
                    FROM {self._table_name}
                    WHERE event_id = $1
                    """,
                    event_id,
                )
            
            if not row:
                raise AdapterOperationError(f"Event not found: {event_id}")
            
            return AuditEvent(
                event_id=row["event_id"],
                event_type=EventType(row["event_type"]),
                timestamp=row["timestamp"].isoformat(),
                session_id=row["session_id"],
                agent_id=row["agent_id"],
                user_id=row["user_id"],
                severity=row["severity"],
                payload=row["payload"],
                tags=row["tags"],
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to get event: {e}")
    
    async def get_statistics(
        self,
        session_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> AuditStats:
        """Get audit statistics from database."""
        try:
            conditions = []
            params = []
            
            if session_id:
                conditions.append("session_id = $1")
                params.append(session_id)
            
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT 
                        COUNT(*) as total_events,
                        COUNT(DISTINCT session_id) as total_sessions,
                        COUNT(DISTINCT agent_id) as total_agents
                    FROM {self._table_name}
                    WHERE {where_clause}
                    """,
                    *params,
                )
            
            return AuditStats(
                total_events=row["total_events"],
                total_sessions=row["total_sessions"],
                total_agents=row["total_agents"],
                events_by_type={},
                events_by_severity={},
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to get statistics: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup database connection pool."""
        if self._pool:
            await self._pool.close()
        await super().cleanup()
```

## Creating a Custom Policy Validator

### Example: OPA Policy Validator

```python
from isolated_agents_sdk.adapters.policy.base import PolicyValidator
from isolated_agents_sdk.adapters.policy.types import (
    PolicyValidationResult,
    ValidationError,
    PolicyConstraints,
)
from isolated_agents_sdk.adapters.exceptions import AdapterOperationError

class OPAPolicyValidator(PolicyValidator):
    """Open Policy Agent (OPA) policy validator."""
    
    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "isolated_agents/policy",
        **kwargs
    ):
        """Initialize OPA validator.
        
        Args:
            opa_url: OPA server URL
            policy_path: Policy path in OPA
            **kwargs: Additional configuration
        """
        super().__init__()
        self._opa_url = opa_url
        self._policy_path = policy_path
    
    async def initialize(self) -> None:
        """Initialize OPA client."""
        try:
            import aiohttp
            self._session = aiohttp.ClientSession()
            await super().initialize()
        except ImportError:
            raise AdapterOperationError(
                "aiohttp not installed. Install with: pip install aiohttp"
            )
    
    async def validate_policy(
        self,
        policy: any,
        constraints: PolicyConstraints | None = None,
    ) -> PolicyValidationResult:
        """Validate policy using OPA."""
        try:
            # Convert policy to dict
            policy_dict = policy.to_dict() if hasattr(policy, "to_dict") else vars(policy)
            
            # Send to OPA
            url = f"{self._opa_url}/v1/data/{self._policy_path}"
            async with self._session.post(url, json={"input": policy_dict}) as response:
                result = await response.json()
            
            # Parse OPA response
            opa_result = result.get("result", {})
            is_valid = opa_result.get("allow", False)
            violations = opa_result.get("violations", [])
            
            # Convert to validation errors
            errors = []
            for violation in violations:
                errors.append(ValidationError(
                    field=violation.get("field", "unknown"),
                    message=violation.get("message", "Validation failed"),
                    severity="error",
                ))
            
            return PolicyValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=[],
                suggestions=[],
            )
            
        except Exception as e:
            raise AdapterOperationError(f"Failed to validate policy with OPA: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup OPA client."""
        if hasattr(self, "_session"):
            await self._session.close()
        await super().cleanup()
```

## Testing Custom Adapters

```python
import pytest
from isolated_agents_sdk.adapters import AdapterFactory, get_registry

@pytest.mark.asyncio
async def test_custom_storage_adapter():
    """Test custom S3 storage adapter."""
    # Create adapter
    adapter = S3StorageAdapter(
        bucket_name="test-bucket",
        region="us-east-1",
    )
    
    # Initialize
    await adapter.initialize()
    
    # Test store
    location = await adapter.store_artifact(
        session_id="test-session",
        artifact_name="test.txt",
        data=b"test data",
    )
    
    assert location.path == "test-session/test.txt"
    
    # Test retrieve
    data = await adapter.retrieve_artifact(
        session_id="test-session",
        artifact_name="test.txt",
    )
    
    assert data == b"test data"
    
    # Cleanup
    await adapter.cleanup()

@pytest.mark.asyncio
async def test_adapter_registration():
    """Test registering custom adapter."""
    # Register adapter
    AdapterFactory.register_storage_adapter("s3", S3StorageAdapter)
    
    # Create from factory
    adapter = AdapterFactory.create_storage_adapter(
        "s3",
        bucket_name="test-bucket",
    )
    
    assert isinstance(adapter, S3StorageAdapter)
```

## Best Practices

### 1. Error Handling

Always wrap operations in try-except and raise `AdapterOperationError`:

```python
try:
    result = await self._client.operation()
except Exception as e:
    raise AdapterOperationError(f"Operation failed: {e}")
```

### 2. Resource Cleanup

Implement proper cleanup in the `cleanup()` method:

```python
async def cleanup(self) -> None:
    """Cleanup resources."""
    if self._client:
        await self._client.close()
    await super().cleanup()
```

### 3. Type Hints

Use proper type hints for all methods:

```python
async def store_artifact(
    self,
    session_id: str,
    artifact_name: str,
    data: bytes,
) -> StorageLocation:
    """Store artifact with proper types."""
    pass
```

### 4. Documentation

Document all public methods with docstrings:

```python
async def my_method(self, param: str) -> str:
    """Brief description.
    
    Args:
        param: Parameter description
    
    Returns:
        Return value description
    
    Raises:
        AdapterOperationError: When operation fails
    """
    pass
```

### 5. Configuration

Accept configuration in `__init__`:

```python
def __init__(self, config_param: str, **kwargs):
    """Initialize adapter.
    
    Args:
        config_param: Configuration parameter
        **kwargs: Additional configuration
    """
    super().__init__()
    self._config_param = config_param
```

## Summary

Creating custom adapters involves:
1. **Implement the interface** - Inherit from base adapter class
2. **Add initialization** - Set up clients and resources
3. **Implement methods** - Provide functionality for each method
4. **Handle errors** - Wrap operations and raise appropriate errors
5. **Cleanup resources** - Implement proper cleanup
6. **Register adapter** - Register with factory for easy creation
7. **Test thoroughly** - Write comprehensive tests

For more examples, see:
- [`isolated_agents_sdk/adapters/container/podman.py`](../isolated_agents_sdk/adapters/container/podman.py)
- [`isolated_agents_sdk/adapters/storage/local.py`](../isolated_agents_sdk/adapters/storage/local.py)
- [`isolated_agents_sdk/adapters/audit/file.py`](../isolated_agents_sdk/adapters/audit/file.py)
- [`isolated_agents_sdk/adapters/policy/default.py`](../isolated_agents_sdk/adapters/policy/default.py)