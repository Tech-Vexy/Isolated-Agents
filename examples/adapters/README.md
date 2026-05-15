# Adapter Pattern Examples

This directory contains examples demonstrating how to use the adapter pattern in the Isolated Agents SDK.

## Overview

The adapter pattern allows you to:
- **Swap implementations** without changing your code
- **Configure adapters** through files, environment variables, or code
- **Test easily** by using mock adapters
- **Extend functionality** by creating custom adapters

## Files

### Configuration Files

- **[`config.yaml`](config.yaml)** - YAML configuration example
- **[`config.json`](config.json)** - JSON configuration example

### Examples

- **[`basic_usage.py`](basic_usage.py)** - Comprehensive adapter usage examples

## Quick Start

### 1. Using Configuration Files

```python
from isolated_agents_sdk.adapters import load_config, get_registry

# Load configuration from file
config = load_config(config_file="config.yaml")

# Initialize registry
registry = get_registry()
registry.initialize_from_config(config)

# Get adapters
container = registry.get_container_adapter()
storage = registry.get_storage_adapter()
audit = registry.get_audit_adapter()
policy = registry.get_policy_adapter()
```

### 2. Programmatic Configuration

```python
from isolated_agents_sdk.adapters import AdapterConfig, get_registry

# Create configuration
config = AdapterConfig(
    container_adapter="podman",
    storage_adapter="local",
    storage_config={"base_path": "./storage"},
    audit_adapter="file",
    audit_config={"log_file": "./logs/audit.jsonl"},
    policy_adapter="default",
)

# Initialize registry
registry = get_registry()
registry.initialize_from_config(config)
```

### 3. Environment Variables

```bash
# Set environment variables
export ISOLATED_AGENTS_CONTAINER_ADAPTER=podman
export ISOLATED_AGENTS_STORAGE_ADAPTER=local
export ISOLATED_AGENTS_STORAGE_BASE_PATH=./storage
export ISOLATED_AGENTS_AUDIT_ADAPTER=file
export ISOLATED_AGENTS_POLICY_ADAPTER=default
```

```python
from isolated_agents_sdk.adapters import load_config

# Load from environment
config = load_config(use_env=True)
```

### 4. Factory Pattern

```python
from isolated_agents_sdk.adapters import AdapterFactory

# Create adapters directly
container = AdapterFactory.create_container_adapter("podman")
storage = AdapterFactory.create_storage_adapter("local", base_path="./storage")
audit = AdapterFactory.create_audit_adapter("file", log_file="./logs/audit.jsonl")
policy = AdapterFactory.create_policy_adapter("default")
```

## Adapter Types

### Container Runtime Adapters

Manage container lifecycle and execution:

- **`podman`** - Podman container runtime (default)
- **`docker`** - Docker container runtime (future)

```python
container = AdapterFactory.create_container_adapter("podman")
await container.initialize()

# Create container
handle = await container.create_container(
    image="python:3.11-slim",
    command=["python", "script.py"],
    working_dir="/workspace",
)

# Execute command
result = await container.execute_command(handle, ["ls", "-la"])

# Cleanup
await container.stop_container(handle)
await container.cleanup()
```

### Storage Backend Adapters

Store and retrieve artifacts:

- **`local`** - Local filesystem storage (default)
- **`s3`** - Amazon S3 storage (future)
- **`azure`** - Azure Blob Storage (future)
- **`gcs`** - Google Cloud Storage (future)

```python
storage = AdapterFactory.create_storage_adapter("local", base_path="./storage")
await storage.initialize()

# Store artifact
location = await storage.store_artifact(
    session_id="session-123",
    artifact_name="output.txt",
    data=b"Hello, World!",
    content_type="text/plain",
)

# Retrieve artifact
data = await storage.retrieve_artifact(
    session_id="session-123",
    artifact_name="output.txt",
)

# List artifacts
artifacts = await storage.list_artifacts("session-123")

await storage.cleanup()
```

### Audit Logger Adapters

Log and query audit events:

- **`file`** - File-based JSON logging (default)
- **`database`** - Database logging (future)
- **`cloudwatch`** - AWS CloudWatch logging (future)

```python
from isolated_agents_sdk.adapters.audit.types import EventType, AuditQuery

audit = AdapterFactory.create_audit_adapter("file", log_file="./logs/audit.jsonl")
await audit.initialize()

# Log event
await audit.log_event(
    event_type=EventType.AGENT_STARTED,
    session_id="session-123",
    agent_id="agent-456",
    payload={"message": "Agent started successfully"},
)

# Query events
query = AuditQuery(session_id="session-123")
events = await audit.query_events(query)

await audit.cleanup()
```

### Policy Validator Adapters

Validate policies against constraints:

- **`default`** - Schema-based validation (default)
- **`opa`** - Open Policy Agent validation (future)
- **`custom`** - Custom validation rules (future)

```python
from isolated_agents_sdk.models import Policy

policy_validator = AdapterFactory.create_policy_adapter("default")
await policy_validator.initialize()

# Validate policy
policy = Policy(cpu_cores=2.0, memory_mb=1024)
result = await policy_validator.validate_policy(policy)

if not result.is_valid:
    for error in result.errors:
        print(f"Error in {error.field}: {error.message}")

await policy_validator.cleanup()
```

## Configuration Priority

When using `load_config()`, configuration is loaded in this order (later sources override earlier):

1. **Default configuration** - Built-in defaults
2. **Configuration file** - YAML/JSON file (if specified)
3. **Environment variables** - Environment overrides (if enabled)

```python
# Load with all sources
config = load_config(
    config_file="config.yaml",  # Load from file
    use_env=True,               # Override with environment
)
```

## Testing with Mock Adapters

```python
from isolated_agents_sdk.adapters import get_registry

# Create mock adapter
class MockStorageAdapter:
    async def initialize(self): pass
    async def store_artifact(self, **kwargs): return StorageLocation(path="/mock")
    async def retrieve_artifact(self, **kwargs): return b"mock data"
    async def cleanup(self): pass

# Register mock adapter
registry = get_registry()
registry.register_storage_adapter("mock", MockStorageAdapter())
registry.set_default_storage_adapter("mock")

# Use mock adapter in tests
storage = registry.get_storage_adapter()
```

## Running the Examples

```bash
# Run all examples
python examples/adapters/basic_usage.py

# Or run individual examples by modifying the main() function
```

## Configuration File Format

### YAML Format

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

### JSON Format

```json
{
  "container_adapter": "podman",
  "container_config": {
    "timeout": 300
  },
  "storage_adapter": "local",
  "storage_config": {
    "base_path": "./storage",
    "create_dirs": true
  },
  "audit_adapter": "file",
  "audit_config": {
    "log_file": "./logs/audit.jsonl",
    "create_dirs": true
  },
  "policy_adapter": "default",
  "policy_config": {
    "strict_mode": false,
    "max_cpu_cores": 4.0,
    "max_memory_mb": 4096
  }
}
```

## Best Practices

1. **Use configuration files** for production deployments
2. **Use environment variables** for container/cloud deployments
3. **Use programmatic configuration** for testing and development
4. **Initialize adapters once** at application startup
5. **Use the registry** for dependency injection
6. **Clean up adapters** when shutting down

## Next Steps

- See [`docs/ADAPTER_ARCHITECTURE.md`](../../docs/ADAPTER_ARCHITECTURE.md) for architecture details
- See [`docs/EXTENDING_ADAPTERS.md`](../../docs/EXTENDING_ADAPTERS.md) for creating custom adapters
- See [`docs/MIGRATION_GUIDE.md`](../../docs/MIGRATION_GUIDE.md) for migrating existing code