# Adapter Pattern Architecture for Production-Ready SDK

## Executive Summary

This document outlines the comprehensive adapter pattern architecture to make the Isolated Agents SDK production-ready. The design introduces abstraction layers for container runtimes, storage backends, audit logging, and policy validation, enabling flexibility, testability, and cloud-native deployments.

## Current Architecture Analysis

### Identified Tight Coupling Points

1. **Container Runtime**: Hard-coded Podman CLI calls throughout `ContainerProvisioner`, `AgentRunner`, `SessionManager`, and `OutputCollector`
2. **Storage Backend**: Direct filesystem operations for artifact collection
3. **Audit Logging**: Fixed file/stderr output with no pluggable backends
4. **Policy Validation**: Monolithic validation logic without extensibility

### Impact on Production Readiness

- **Vendor Lock-in**: Cannot switch to Docker, containerd, or cloud container services
- **Scalability**: No support for distributed storage (S3, Azure Blob, GCS)
- **Observability**: Limited integration with enterprise logging systems
- **Compliance**: Difficult to add custom policy enforcement rules

## Proposed Adapter Architecture

### Design Principles

1. **Interface Segregation**: Small, focused interfaces for each adapter type
2. **Dependency Inversion**: Core logic depends on abstractions, not implementations
3. **Open/Closed**: Open for extension via new adapters, closed for modification
4. **Factory Pattern**: Centralized adapter instantiation with configuration
5. **Fail-Fast**: Clear error messages when adapters are misconfigured

### Core Adapter Interfaces

```
isolated_agents_sdk/
├── adapters/
│   ├── __init__.py
│   ├── base.py                    # Base adapter interfaces
│   ├── container/
│   │   ├── __init__.py
│   │   ├── base.py                # ContainerRuntimeAdapter interface
│   │   ├── podman.py              # PodmanAdapter (default)
│   │   ├── docker.py              # DockerAdapter
│   │   └── kubernetes.py          # KubernetesAdapter (future)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── base.py                # StorageBackendAdapter interface
│   │   ├── local.py               # LocalFilesystemAdapter (default)
│   │   ├── s3.py                  # S3StorageAdapter
│   │   ├── azure.py               # AzureBlobAdapter
│   │   └── gcs.py                 # GCSStorageAdapter
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── base.py                # AuditLoggerAdapter interface
│   │   ├── file.py                # FileAuditAdapter (default)
│   │   ├── database.py            # DatabaseAuditAdapter
│   │   ├── cloudwatch.py          # CloudWatchAdapter
│   │   └── datadog.py             # DatadogAdapter
│   └── policy/
│       ├── __init__.py
│       ├── base.py                # PolicyValidatorAdapter interface
│       ├── default.py             # DefaultPolicyValidator
│       ├── opa.py                 # OpenPolicyAgentValidator
│       └── custom.py              # CustomPolicyValidator
├── config.py                      # Configuration management
└── factory.py                     # Adapter factory
```

## Adapter Interface Specifications

### 1. Container Runtime Adapter

**Purpose**: Abstract container lifecycle operations (create, exec, copy, destroy)

**Interface**:
```python
class ContainerRuntimeAdapter(ABC):
    @abstractmethod
    async def check_availability(self) -> bool:
        """Verify runtime is installed and accessible"""
        
    @abstractmethod
    async def provision_container(
        self,
        image: str,
        command: list[str],
        mounts: list[Mount],
        resources: ResourceLimits,
        network: NetworkConfig,
        security: SecurityConfig,
    ) -> ContainerHandle:
        """Create and start a container"""
        
    @abstractmethod
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: dict[str, str] | None = None,
    ) -> ExecResult:
        """Execute command inside container"""
        
    @abstractmethod
    async def copy_from_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy file/directory from container to host"""
        
    @abstractmethod
    async def copy_to_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy file/directory from host to container"""
        
    @abstractmethod
    async def get_container_stats(
        self,
        container_id: str,
    ) -> ContainerStats:
        """Get CPU/memory usage metrics"""
        
    @abstractmethod
    async def destroy_container(
        self,
        container_id: str,
        force: bool = True,
    ) -> None:
        """Stop and remove container"""
```

**Implementations**:
- `PodmanAdapter`: Current implementation (default)
- `DockerAdapter`: Docker CLI/API support
- `KubernetesAdapter`: K8s Job/Pod support (future)

### 2. Storage Backend Adapter

**Purpose**: Abstract artifact storage and retrieval

**Interface**:
```python
class StorageBackendAdapter(ABC):
    @abstractmethod
    async def store_artifact(
        self,
        session_id: str,
        artifact_name: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Store artifact and return URI"""
        
    @abstractmethod
    async def retrieve_artifact(
        self,
        uri: str,
    ) -> bytes:
        """Retrieve artifact by URI"""
        
    @abstractmethod
    async def list_artifacts(
        self,
        session_id: str,
    ) -> list[ArtifactInfo]:
        """List all artifacts for a session"""
        
    @abstractmethod
    async def delete_artifacts(
        self,
        session_id: str,
    ) -> None:
        """Delete all artifacts for a session"""
        
    @abstractmethod
    async def get_artifact_url(
        self,
        uri: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """Generate signed URL for artifact access"""
```

**Implementations**:
- `LocalFilesystemAdapter`: Current implementation (default)
- `S3StorageAdapter`: AWS S3 support
- `AzureBlobAdapter`: Azure Blob Storage support
- `GCSStorageAdapter`: Google Cloud Storage support

### 3. Audit Logger Adapter

**Purpose**: Abstract audit event emission to various backends

**Interface**:
```python
class AuditLoggerAdapter(ABC):
    @abstractmethod
    async def emit_event(
        self,
        event: AuditEvent,
    ) -> None:
        """Emit a single audit event"""
        
    @abstractmethod
    async def emit_batch(
        self,
        events: list[AuditEvent],
    ) -> None:
        """Emit multiple events efficiently"""
        
    @abstractmethod
    async def query_events(
        self,
        session_id: str | None = None,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Query historical audit events"""
        
    @abstractmethod
    async def flush(self) -> None:
        """Ensure all buffered events are written"""
```

**Implementations**:
- `FileAuditAdapter`: Current file/stderr implementation (default)
- `DatabaseAuditAdapter`: PostgreSQL/MySQL support
- `CloudWatchAdapter`: AWS CloudWatch Logs
- `DatadogAdapter`: Datadog logging
- `ElasticsearchAdapter`: Elasticsearch/OpenSearch

### 4. Policy Validator Adapter

**Purpose**: Pluggable policy validation and enforcement

**Interface**:
```python
class PolicyValidatorAdapter(ABC):
    @abstractmethod
    async def validate_policy(
        self,
        policy: Policy,
    ) -> ValidationResult:
        """Validate policy and return errors/warnings"""
        
    @abstractmethod
    async def enforce_constraints(
        self,
        policy: Policy,
        context: EnforcementContext,
    ) -> Policy:
        """Apply organizational constraints and return modified policy"""
        
    @abstractmethod
    async def check_compliance(
        self,
        policy: Policy,
        compliance_rules: list[str],
    ) -> ComplianceReport:
        """Check policy against compliance requirements"""
```

**Implementations**:
- `DefaultPolicyValidator`: Current implementation
- `OpenPolicyAgentValidator`: OPA integration
- `CustomPolicyValidator`: User-defined validation logic

## Configuration System

### Configuration File Format (YAML)

```yaml
# isolated_agents_config.yaml
adapters:
  container_runtime:
    type: podman  # podman | docker | kubernetes
    config:
      timeout_seconds: 300
      
  storage_backend:
    type: s3  # local | s3 | azure | gcs
    config:
      bucket: my-agent-artifacts
      region: us-east-1
      prefix: agents/
      
  audit_logger:
    type: cloudwatch  # file | database | cloudwatch | datadog
    config:
      log_group: /isolated-agents/audit
      stream_prefix: session-
      
  policy_validator:
    type: default  # default | opa | custom
    config:
      strict_mode: true
```

### Environment Variable Override

```bash
ISOLATED_AGENTS_CONTAINER_RUNTIME=docker
ISOLATED_AGENTS_STORAGE_BACKEND=s3
ISOLATED_AGENTS_STORAGE_S3_BUCKET=my-bucket
ISOLATED_AGENTS_AUDIT_LOGGER=cloudwatch
```

### Programmatic Configuration

```python
from isolated_agents_sdk import configure_adapters
from isolated_agents_sdk.adapters.storage import S3StorageAdapter

configure_adapters(
    container_runtime="docker",
    storage_backend=S3StorageAdapter(
        bucket="my-bucket",
        region="us-east-1",
    ),
    audit_logger="cloudwatch",
)
```

## Factory Pattern Implementation

### Adapter Factory

```python
class AdapterFactory:
    """Central factory for creating adapter instances"""
    
    _container_adapters: dict[str, type[ContainerRuntimeAdapter]] = {}
    _storage_adapters: dict[str, type[StorageBackendAdapter]] = {}
    _audit_adapters: dict[str, type[AuditLoggerAdapter]] = {}
    _policy_adapters: dict[str, type[PolicyValidatorAdapter]] = {}
    
    @classmethod
    def register_container_adapter(
        cls,
        name: str,
        adapter_class: type[ContainerRuntimeAdapter],
    ) -> None:
        """Register a container runtime adapter"""
        
    @classmethod
    def create_container_adapter(
        cls,
        name: str,
        config: dict[str, Any] | None = None,
    ) -> ContainerRuntimeAdapter:
        """Create container runtime adapter instance"""
        
    # Similar methods for other adapter types...
```

## Migration Strategy

### Phase 1: Interface Definition (Week 1)
- Define all adapter interfaces
- Create base classes and type definitions
- Set up adapter registry and factory

### Phase 2: Default Adapters (Week 2)
- Refactor existing code into default adapters
- Maintain backward compatibility
- Add comprehensive tests

### Phase 3: Core Integration (Week 3)
- Update `ContainerProvisioner` to use `ContainerRuntimeAdapter`
- Update `OutputCollector` to use `StorageBackendAdapter`
- Update `AuditLogger` to use `AuditLoggerAdapter`
- Update `PolicyValidator` to use `PolicyValidatorAdapter`

### Phase 4: Additional Implementations (Week 4-5)
- Implement Docker adapter
- Implement S3 storage adapter
- Implement CloudWatch audit adapter
- Add configuration system

### Phase 5: Testing & Documentation (Week 6)
- Integration tests for adapter switching
- Performance benchmarks
- Migration guide
- API documentation updates

## Backward Compatibility

### Deprecation Strategy

1. **Current API remains default**: No breaking changes for existing users
2. **Gradual migration**: New adapter-based API available alongside old API
3. **Deprecation warnings**: Clear messages when using legacy patterns
4. **Migration tools**: Scripts to help users transition

### Example Migration

**Before (current)**:
```python
from isolated_agents_sdk import run_agent, Policy

result = run_agent(
    agent=my_agent,
    working_dir="./workspace",
    policy=Policy(memory_mb=1024),
)
```

**After (with adapters)**:
```python
from isolated_agents_sdk import run_agent, Policy, configure_adapters

# Optional: Configure adapters (uses defaults if not called)
configure_adapters(
    container_runtime="docker",
    storage_backend="s3",
)

result = run_agent(
    agent=my_agent,
    working_dir="./workspace",
    policy=Policy(memory_mb=1024),
)
```

## Testing Strategy

### Unit Tests
- Mock adapters for testing core logic
- Adapter interface compliance tests
- Factory registration tests

### Integration Tests
- Real adapter implementations
- Cross-adapter compatibility
- Failure scenario handling

### Performance Tests
- Adapter overhead measurement
- Storage backend benchmarks
- Audit logging throughput

## Security Considerations

### Adapter Isolation
- Adapters run with minimal privileges
- Credential management per adapter
- Audit all adapter operations

### Configuration Security
- Encrypted configuration files
- Secret management integration
- Least-privilege access

## Benefits Summary

### For Users
- **Flexibility**: Choose container runtime based on infrastructure
- **Scalability**: Use cloud storage for distributed deployments
- **Observability**: Integrate with existing logging infrastructure
- **Compliance**: Custom policy validation for regulatory requirements

### For Developers
- **Testability**: Mock adapters for unit testing
- **Extensibility**: Add new adapters without modifying core
- **Maintainability**: Clear separation of concerns
- **Documentation**: Well-defined interfaces

### For Operations
- **Deployment**: Support multiple environments (local, cloud, hybrid)
- **Monitoring**: Centralized audit logging
- **Cost Optimization**: Choose appropriate storage tiers
- **Disaster Recovery**: Backup/restore via storage adapters

## Next Steps

1. Review and approve this architecture
2. Create detailed implementation tickets
3. Set up development branches
4. Begin Phase 1 implementation
5. Establish testing infrastructure

## Appendix: Example Adapter Implementations

### Example: Docker Adapter

```python
class DockerAdapter(ContainerRuntimeAdapter):
    async def provision_container(self, ...):
        # Use Docker SDK instead of Podman CLI
        import docker
        client = docker.from_env()
        container = client.containers.run(
            image=image,
            command=command,
            detach=True,
            # Map parameters to Docker API...
        )
        return ContainerHandle(container_id=container.id)
```

### Example: S3 Storage Adapter

```python
class S3StorageAdapter(StorageBackendAdapter):
    async def store_artifact(self, session_id, artifact_name, content, metadata):
        import boto3
        s3 = boto3.client('s3')
        key = f"{self.prefix}{session_id}/{artifact_name}"
        s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            Metadata=metadata or {},
        )
        return f"s3://{self.bucket}/{key}"
```

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-15  
**Status**: Proposed  
**Reviewers**: [To be assigned]