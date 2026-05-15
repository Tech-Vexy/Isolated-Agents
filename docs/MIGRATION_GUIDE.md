# Migration Guide: Adapter Pattern

This guide helps you migrate from the current direct implementation to the new adapter-based architecture.

## Overview

The adapter pattern provides:
- **Flexibility**: Swap implementations without code changes
- **Testability**: Easy mocking and testing
- **Extensibility**: Add new backends without modifying core code
- **Configuration**: Centralized adapter management

## Migration Strategy

### Phase 1: Backward Compatible (Current)

The SDK maintains 100% backward compatibility. Existing code continues to work without changes.

```python
# Existing code - still works!
from isolated_agents_sdk import SessionManager

session = SessionManager()
result = await session.run_agent(agent_fn, policy=policy)
```

### Phase 2: Gradual Adoption (Recommended)

Gradually adopt adapters for new features while maintaining existing code.

```python
# New code using adapters
from isolated_agents_sdk.adapters import load_config, get_registry

# Initialize adapters once at startup
config = load_config(config_file="config.yaml")
registry = get_registry()
registry.initialize_from_config(config)

# Use existing SessionManager with adapter-aware components
session = SessionManager()
result = await session.run_agent(agent_fn, policy=policy)
```

### Phase 3: Full Adoption (Future)

Fully leverage adapters for maximum flexibility.

```python
# Future: Direct adapter usage
from isolated_agents_sdk.adapters import get_registry

registry = get_registry()
container = registry.get_container_adapter()
storage = registry.get_storage_adapter()
audit = registry.get_audit_adapter()
policy = registry.get_policy_adapter()

# Use adapters directly for custom workflows
```

## Component-by-Component Migration

### 1. Container Provisioner

#### Before (Current Implementation)

```python
from isolated_agents_sdk.container_provisioner import ContainerProvisioner

provisioner = ContainerProvisioner(
    audit_logger=audit_logger,
    base_image="python:3.11-slim"
)

handle = await provisioner.provision(
    working_dir="/workspace",
    policy=policy,
    session_id="session-123",
    agent_id="agent-456"
)
```

#### After (With Adapters)

```python
from isolated_agents_sdk.adapters import get_registry

# Get container adapter from registry
registry = get_registry()
container = registry.get_container_adapter()

# Initialize adapter
await container.initialize()

# Create container with adapter
handle = await container.create_container(
    image="python:3.11-slim",
    command=["python", "script.py"],
    working_dir="/workspace",
    mounts=[Mount(source="/host/path", target="/container/path")],
    resource_limits=ResourceLimits(cpu_cores=2.0, memory_mb=1024),
)

# Cleanup
await container.cleanup()
```

#### Migration Steps

1. **Keep existing code** - No immediate changes required
2. **Add adapter initialization** at application startup
3. **Gradually replace** direct ContainerProvisioner usage with adapter calls
4. **Test thoroughly** before removing old code

### 2. Storage/Output Collector

#### Before (Current Implementation)

```python
from isolated_agents_sdk.output_collector import OutputCollector

collector = OutputCollector(audit_logger=audit_logger)

result = await collector.collect(
    container_id=container_id,
    output_path_in_container="/output",
    host_output_path="./output",
    max_output_bytes=10_000_000,
    exit_code=0,
    session_id="session-123",
    agent_id="agent-456"
)
```

#### After (With Adapters)

```python
from isolated_agents_sdk.adapters import get_registry

# Get storage adapter from registry
registry = get_registry()
storage = registry.get_storage_adapter()

# Initialize adapter
await storage.initialize()

# Store artifacts
location = await storage.store_artifact(
    session_id="session-123",
    artifact_name="output.txt",
    data=output_data,
    content_type="text/plain",
    metadata={"agent_id": "agent-456"}
)

# Retrieve artifacts
data = await storage.retrieve_artifact(
    session_id="session-123",
    artifact_name="output.txt"
)

# List artifacts
artifacts = await storage.list_artifacts("session-123")

# Cleanup
await storage.cleanup()
```

#### Migration Steps

1. **Identify output collection points** in your code
2. **Add storage adapter** initialization
3. **Replace collector.collect()** with storage.store_artifact()
4. **Update retrieval logic** to use storage.retrieve_artifact()
5. **Test artifact storage** and retrieval

### 3. Audit Logger

#### Before (Current Implementation)

```python
from isolated_agents_sdk.audit_logger import AuditLogger

audit = AuditLogger(log_output_path="./logs/audit.log")

audit.log_event(
    event_type="agent_started",
    session_id="session-123",
    agent_id="agent-456",
    payload={"message": "Agent started"}
)
```

#### After (With Adapters)

```python
from isolated_agents_sdk.adapters import get_registry
from isolated_agents_sdk.adapters.audit.types import EventType

# Get audit adapter from registry
registry = get_registry()
audit = registry.get_audit_adapter()

# Initialize adapter
await audit.initialize()

# Log events
await audit.log_event(
    event_type=EventType.AGENT_STARTED,
    session_id="session-123",
    agent_id="agent-456",
    payload={"message": "Agent started"}
)

# Query events
from isolated_agents_sdk.adapters.audit.types import AuditQuery

query = AuditQuery(
    session_id="session-123",
    event_types=[EventType.AGENT_STARTED, EventType.AGENT_COMPLETED]
)
events = await audit.query_events(query)

# Get statistics
stats = await audit.get_statistics()

# Cleanup
await audit.cleanup()
```

#### Migration Steps

1. **Replace AuditLogger** with audit adapter
2. **Update event types** to use EventType enum
3. **Add async/await** to log_event calls
4. **Leverage query capabilities** for event analysis
5. **Use statistics** for monitoring

### 4. Policy Validator

#### Before (Current Implementation)

```python
from isolated_agents_sdk.policy_validator import PolicyValidator

validator = PolicyValidator()
validated_policy = validator.validate(policy)
```

#### After (With Adapters)

```python
from isolated_agents_sdk.adapters import get_registry

# Get policy adapter from registry
registry = get_registry()
policy_validator = registry.get_policy_adapter()

# Initialize adapter
await policy_validator.initialize()

# Validate policy
result = await policy_validator.validate_policy(policy)

if not result.is_valid:
    for error in result.errors:
        print(f"Error in {error.field}: {error.message}")
    for warning in result.warnings:
        print(f"Warning in {warning.field}: {warning.message}")

# Batch validation
results = await policy_validator.validate_batch([policy1, policy2, policy3])

# Cleanup
await policy_validator.cleanup()
```

#### Migration Steps

1. **Replace PolicyValidator** with policy adapter
2. **Add async/await** to validate calls
3. **Handle validation results** with errors and warnings
4. **Use batch validation** for multiple policies
5. **Leverage suggestions** for policy improvements

## Configuration Migration

### Step 1: Create Configuration File

Create `config.yaml`:

```yaml
container_adapter: podman
container_config:
  timeout: 300

storage_adapter: local
storage_config:
  base_path: ./storage
  create_dirs: true

audit_adapter: file
audit_config:
  log_file: ./logs/audit.jsonl
  create_dirs: true

policy_adapter: default
policy_config:
  strict_mode: false
  max_cpu_cores: 4.0
  max_memory_mb: 4096
```

### Step 2: Initialize at Startup

```python
from isolated_agents_sdk.adapters import load_config, get_registry

def initialize_adapters():
    """Initialize adapters at application startup."""
    # Load configuration
    config = load_config(
        config_file="config.yaml",
        use_env=True  # Allow environment overrides
    )
    
    # Initialize registry
    registry = get_registry()
    registry.initialize_from_config(config)
    
    return registry

# Call once at startup
registry = initialize_adapters()
```

### Step 3: Use Throughout Application

```python
from isolated_agents_sdk.adapters import get_registry

def my_function():
    """Use adapters in your functions."""
    registry = get_registry()
    
    # Get adapters as needed
    container = registry.get_container_adapter()
    storage = registry.get_storage_adapter()
    audit = registry.get_audit_adapter()
    policy = registry.get_policy_adapter()
    
    # Use adapters...
```

## Testing Migration

### Before (Current Testing)

```python
def test_agent_execution():
    """Test with real components."""
    provisioner = ContainerProvisioner()
    # Test with real Podman...
```

### After (With Mock Adapters)

```python
from isolated_agents_sdk.adapters import get_registry

class MockContainerAdapter:
    """Mock container adapter for testing."""
    async def initialize(self): pass
    async def create_container(self, **kwargs):
        return ContainerHandle(container_id="mock-123")
    async def cleanup(self): pass

def test_agent_execution():
    """Test with mock adapters."""
    # Reset registry for test
    from isolated_agents_sdk.adapters import AdapterRegistry
    AdapterRegistry.reset_instance()
    
    # Register mock adapter
    registry = get_registry()
    registry.register_container_adapter("mock", MockContainerAdapter())
    registry.set_default_container_adapter("mock")
    
    # Test with mock adapter
    container = registry.get_container_adapter()
    # Test logic...
```

## Common Migration Patterns

### Pattern 1: Dependency Injection

```python
# Before
class MyService:
    def __init__(self):
        self.provisioner = ContainerProvisioner()
        self.collector = OutputCollector()

# After
class MyService:
    def __init__(self, registry=None):
        self.registry = registry or get_registry()
    
    async def do_work(self):
        container = self.registry.get_container_adapter()
        storage = self.registry.get_storage_adapter()
        # Use adapters...
```

### Pattern 2: Configuration-Driven

```python
# Before
provisioner = ContainerProvisioner(base_image="python:3.11-slim")

# After
config = load_config(config_file="config.yaml")
registry = get_registry()
registry.initialize_from_config(config)
container = registry.get_container_adapter()
```

### Pattern 3: Environment-Specific

```python
# Development
config = load_config(config_file="config.dev.yaml")

# Production
config = load_config(config_file="config.prod.yaml", use_env=True)

# Testing
config = AdapterConfig(
    container_adapter="mock",
    storage_adapter="mock",
    audit_adapter="mock",
    policy_adapter="mock"
)
```

## Rollback Strategy

If you need to rollback:

1. **Remove adapter initialization** code
2. **Revert to direct imports** of ContainerProvisioner, OutputCollector, etc.
3. **Remove configuration files**
4. **Update tests** to use real components

The SDK maintains backward compatibility, so rollback is straightforward.

## Best Practices

### 1. Initialize Once

```python
# Good: Initialize at startup
registry = initialize_adapters()

# Bad: Initialize in every function
def my_function():
    registry = get_registry()
    registry.initialize_from_config(config)  # Don't do this!
```

### 2. Use Registry Pattern

```python
# Good: Get from registry
registry = get_registry()
container = registry.get_container_adapter()

# Bad: Create directly
container = PodmanAdapter()  # Don't do this!
```

### 3. Clean Up Resources

```python
# Good: Clean up adapters
async def shutdown():
    registry = get_registry()
    container = registry.get_container_adapter()
    await container.cleanup()

# Bad: Leave resources hanging
# (no cleanup)
```

### 4. Handle Errors

```python
# Good: Handle adapter errors
try:
    result = await container.create_container(...)
except AdapterOperationError as e:
    logger.error(f"Container creation failed: {e}")
    # Handle error...

# Bad: Ignore errors
result = await container.create_container(...)  # May fail silently
```

## Timeline Recommendation

### Week 1-2: Preparation
- Review this guide
- Create configuration files
- Set up adapter initialization
- Test in development environment

### Week 3-4: Gradual Migration
- Migrate one component at a time
- Start with audit logging (lowest risk)
- Then storage, policy, container
- Test thoroughly after each migration

### Week 5-6: Testing & Validation
- Run full test suite
- Performance testing
- Load testing
- Security review

### Week 7-8: Production Rollout
- Deploy to staging
- Monitor for issues
- Gradual production rollout
- Keep rollback plan ready

## Support

For questions or issues during migration:
- Check [`examples/adapters/`](../examples/adapters/) for working examples
- Review [`docs/ADAPTER_ARCHITECTURE.md`](ADAPTER_ARCHITECTURE.md) for architecture details
- See [`docs/EXTENDING_ADAPTERS.md`](EXTENDING_ADAPTERS.md) for custom adapters
- Open an issue on GitHub for help

## Summary

The adapter pattern migration is:
- **Backward compatible** - existing code works unchanged
- **Gradual** - migrate at your own pace
- **Flexible** - choose which components to migrate
- **Reversible** - easy to rollback if needed

Start with configuration and registry setup, then gradually migrate components as needed.