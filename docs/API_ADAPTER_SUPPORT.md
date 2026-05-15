# Adapter-Aware Public API

The Isolated Agents SDK now supports adapter configuration through the public API while maintaining 100% backward compatibility. This document describes the new features and how to use them.

## Overview

The SDK provides two new functions for adapter configuration:

1. **`configure_adapters()`** - Configure adapters globally or per-run
2. **`get_adapter_registry()`** - Access the adapter registry for advanced use cases

Additionally, the main entry points (`run_agent()` and `async_run_agent()`) now accept an optional `adapter_config` parameter.

## Backward Compatibility

**All existing code continues to work without any changes.** The adapter system is completely optional:

```python
# This still works exactly as before
result = run_agent(my_agent, "./workspace")
```

If you don't configure adapters, the SDK uses default implementations:
- **Container Runtime**: Podman
- **Storage Backend**: Local filesystem
- **Audit Logger**: File-based logging
- **Policy Validator**: Schema-based validation

## Configuration Methods

### Method 1: Global Configuration

Configure adapters once at application startup:

```python
from isolated_agents_sdk import configure_adapters, run_agent

# Configure once
configure_adapters(config={
    "container": {
        "type": "podman",
        "config": {"base_image": "python:3.11-slim"}
    },
    "storage": {
        "type": "local",
        "config": {"base_path": "/tmp/storage"}
    },
    "audit": {
        "type": "file",
        "config": {"log_path": "./audit.log"}
    },
    "policy": {
        "type": "default"
    }
})

# All subsequent runs use these adapters
result = run_agent(my_agent, "./workspace")
```

### Method 2: Per-Run Configuration

Configure adapters for a specific run only:

```python
from isolated_agents_sdk import run_agent

# This configuration applies only to this run
result = run_agent(
    agent=my_agent,
    working_dir="./workspace",
    adapter_config={
        "container": {"type": "podman"},
        "storage": {"type": "local"}
    }
)
```

### Method 3: Configuration from File

Load configuration from a YAML or JSON file:

```python
from isolated_agents_sdk import configure_adapters, run_agent

# Load from YAML
configure_adapters(config_file="./config.yaml")

# Or load from JSON
configure_adapters(config_file="./config.json")

result = run_agent(my_agent, "./workspace")
```

**Example config.yaml:**

```yaml
container:
  type: podman
  config:
    base_image: python:3.11-slim

storage:
  type: local
  config:
    base_path: /tmp/agent_storage

audit:
  type: file
  config:
    log_path: ./audit.log

policy:
  type: default
```

### Method 4: Configuration from Environment

Load configuration from environment variables (12-factor app pattern):

```python
from isolated_agents_sdk import configure_adapters, run_agent

# Set environment variables:
# ISOLATED_AGENTS_CONTAINER_TYPE=podman
# ISOLATED_AGENTS_STORAGE_TYPE=local
# ISOLATED_AGENTS_AUDIT_TYPE=file
# ISOLATED_AGENTS_POLICY_TYPE=default

configure_adapters(from_env=True)

result = run_agent(my_agent, "./workspace")
```

## API Reference

### `configure_adapters()`

Configure adapters for the SDK.

**Signature:**

```python
def configure_adapters(
    config: Optional[Dict[str, Any]] = None,
    config_file: Optional[str | Path] = None,
    from_env: bool = False,
) -> None
```

**Parameters:**

- `config` (dict, optional): Dictionary with adapter configuration
- `config_file` (str | Path, optional): Path to YAML or JSON configuration file
- `from_env` (bool, optional): Load configuration from environment variables

**Raises:**

- `ImportError`: If adapter support is not available
- `ValueError`: If configuration is invalid

**Example:**

```python
configure_adapters(config={
    "container": {"type": "podman"},
    "storage": {"type": "local"}
})
```

### `get_adapter_registry()`

Get the global adapter registry for advanced use cases.

**Signature:**

```python
def get_adapter_registry() -> Optional[AdapterRegistry]
```

**Returns:**

- `AdapterRegistry` instance or `None` if adapters not available

**Example:**

```python
registry = get_adapter_registry()
if registry:
    container_adapter = registry.get_container_adapter()
    storage_adapter = registry.get_storage_adapter()
```

### `run_agent()` - Updated

The synchronous entry point now accepts an optional `adapter_config` parameter.

**Signature:**

```python
def run_agent(
    agent: Optional[Callable],
    working_dir: str | Path,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str | Path] = None,
    adapter_config: Optional[Dict[str, Any]] = None,
) -> AgentResult
```

**New Parameter:**

- `adapter_config` (dict, optional): Adapter configuration for this specific run

**Example:**

```python
result = run_agent(
    agent=my_agent,
    working_dir="./workspace",
    adapter_config={
        "container": {"type": "podman"},
        "storage": {"type": "local"}
    }
)
```

### `async_run_agent()` - Updated

The async entry point now accepts an optional `adapter_config` parameter.

**Signature:**

```python
async def async_run_agent(
    agent: Optional[Callable],
    working_dir: str | Path,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str | Path] = None,
    adapter_config: Optional[Dict[str, Any]] = None,
) -> AgentResult
```

**New Parameter:**

- `adapter_config` (dict, optional): Adapter configuration for this specific run

**Example:**

```python
result = await async_run_agent(
    agent=my_agent,
    working_dir="./workspace",
    adapter_config={
        "container": {"type": "podman"}
    }
)
```

## Usage Patterns

### Pattern 1: Simple Application (No Adapters)

For simple applications, you don't need to configure adapters at all:

```python
from isolated_agents_sdk import run_agent

def my_agent():
    # Agent code here
    pass

# Just works with defaults
result = run_agent(my_agent, "./workspace")
```

### Pattern 2: Production Application (Global Config)

For production applications, configure adapters once at startup:

```python
from isolated_agents_sdk import configure_adapters, run_agent

# Application startup
def initialize():
    try:
        # Try environment first (12-factor)
        configure_adapters(from_env=True)
    except (ImportError, ValueError):
        try:
            # Fall back to config file
            configure_adapters(config_file="./config.yaml")
        except FileNotFoundError:
            # Use defaults
            pass

# Application code
def process_task(agent, workspace):
    return run_agent(agent, workspace)
```

### Pattern 3: Multi-Tenant Application (Per-Run Config)

For multi-tenant applications, configure adapters per tenant:

```python
from isolated_agents_sdk import run_agent

def process_tenant_task(tenant_id, agent, workspace):
    # Each tenant gets their own configuration
    adapter_config = get_tenant_config(tenant_id)
    
    return run_agent(
        agent=agent,
        working_dir=workspace,
        adapter_config=adapter_config
    )
```

### Pattern 4: Testing (Temporary Config)

For testing, use per-run configuration:

```python
import pytest
from isolated_agents_sdk import run_agent

def test_agent_execution():
    # Test-specific configuration
    result = run_agent(
        agent=test_agent,
        working_dir="./test_workspace",
        adapter_config={
            "storage": {
                "type": "local",
                "config": {"base_path": "/tmp/test_storage"}
            },
            "audit": {
                "type": "file",
                "config": {"log_path": "./test_audit.log"}
            }
        }
    )
    
    assert result.exit_code == 0
```

## Error Handling

### Adapter Support Not Available

If the adapter package is not installed, you'll get an `ImportError`:

```python
from isolated_agents_sdk import configure_adapters, run_agent

try:
    configure_adapters(config={"container": {"type": "podman"}})
except ImportError:
    # Adapter support not available, use defaults
    pass

# This still works with default implementations
result = run_agent(my_agent, "./workspace")
```

### Invalid Configuration

If the configuration is invalid, you'll get a `ValueError`:

```python
from isolated_agents_sdk import configure_adapters

try:
    configure_adapters(config={
        "container": {"type": "invalid_type"}
    })
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

## Advanced Usage

### Accessing Individual Adapters

For advanced use cases, you can access individual adapters:

```python
from isolated_agents_sdk import get_adapter_registry

registry = get_adapter_registry()
if registry:
    # Access adapters directly
    container = registry.get_container_adapter()
    storage = registry.get_storage_adapter()
    audit = registry.get_audit_adapter()
    policy = registry.get_policy_adapter()
    
    # Use adapters for custom operations
    await storage.store_session_data(session_id, data)
```

### Switching Adapters at Runtime

You can switch adapters at runtime by calling `configure_adapters()` again:

```python
from isolated_agents_sdk import configure_adapters, run_agent

# Initial configuration
configure_adapters(config={
    "container": {"type": "podman"}
})

result1 = run_agent(agent1, "./workspace1")

# Switch to different configuration
configure_adapters(config={
    "container": {"type": "docker"}  # If you have a Docker adapter
})

result2 = run_agent(agent2, "./workspace2")
```

### Custom Adapter Registration

You can register custom adapters before configuration:

```python
from isolated_agents_sdk import get_adapter_registry
from isolated_agents_sdk.adapters import AdapterFactory

# Register custom adapter
registry = get_adapter_registry()
if registry:
    AdapterFactory.register_container_adapter(
        "custom",
        MyCustomContainerAdapter
    )
    
    # Now you can use it
    configure_adapters(config={
        "container": {"type": "custom"}
    })
```

## Migration Guide

### From Legacy API to Adapter-Aware API

**Before (still works):**

```python
from isolated_agents_sdk import run_agent

result = run_agent(my_agent, "./workspace")
```

**After (with adapters):**

```python
from isolated_agents_sdk import configure_adapters, run_agent

# Option 1: Global configuration
configure_adapters(config_file="./config.yaml")
result = run_agent(my_agent, "./workspace")

# Option 2: Per-run configuration
result = run_agent(
    my_agent,
    "./workspace",
    adapter_config={"container": {"type": "podman"}}
)
```

### Gradual Migration

You can migrate gradually:

1. **Phase 1**: Keep using the old API (no changes needed)
2. **Phase 2**: Add global adapter configuration at startup
3. **Phase 3**: Migrate to per-run configuration where needed
4. **Phase 4**: Implement custom adapters for specific requirements

## Best Practices

### 1. Configure Once at Startup

For most applications, configure adapters once at startup:

```python
# main.py
from isolated_agents_sdk import configure_adapters

def main():
    # Configure adapters
    configure_adapters(from_env=True)
    
    # Run application
    app.run()
```

### 2. Use Environment Variables in Production

Follow the 12-factor app pattern:

```bash
# .env
ISOLATED_AGENTS_CONTAINER_TYPE=podman
ISOLATED_AGENTS_STORAGE_TYPE=local
ISOLATED_AGENTS_AUDIT_TYPE=file
ISOLATED_AGENTS_POLICY_TYPE=default
```

```python
from isolated_agents_sdk import configure_adapters

configure_adapters(from_env=True)
```

### 3. Use Configuration Files for Development

Use YAML/JSON files for development:

```yaml
# config.dev.yaml
container:
  type: podman
  config:
    base_image: python:3.11-slim

storage:
  type: local
  config:
    base_path: ./dev_storage
```

```python
configure_adapters(config_file="./config.dev.yaml")
```

### 4. Use Per-Run Config for Testing

Use per-run configuration in tests:

```python
def test_agent():
    result = run_agent(
        agent=test_agent,
        working_dir="./test_workspace",
        adapter_config={
            "storage": {"type": "local", "config": {"base_path": "/tmp/test"}}
        }
    )
    assert result.exit_code == 0
```

### 5. Handle Missing Adapter Support Gracefully

Always handle the case where adapter support might not be available:

```python
try:
    configure_adapters(config_file="./config.yaml")
except ImportError:
    # Adapter support not available, use defaults
    logger.warning("Using default adapters")
```

## See Also

- [Adapter Pattern Summary](ADAPTER_PATTERN_SUMMARY.md) - Architecture overview
- [Migration Guide](MIGRATION_GUIDE.md) - Detailed migration instructions
- [Extending Adapters](EXTENDING_ADAPTERS.md) - Creating custom adapters
- [Examples](../examples/adapters/) - Working code examples

## Summary

The adapter-aware public API provides:

- **100% backward compatibility** - existing code works unchanged
- **Flexible configuration** - global, per-run, file, or environment
- **Optional feature** - use adapters only when needed
- **Production-ready** - supports 12-factor app pattern
- **Type-safe** - full type hints and validation
- **Well-documented** - comprehensive examples and guides

Start simple with defaults, then add adapter configuration as your needs grow.