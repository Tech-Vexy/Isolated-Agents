# Integration Tests for Adapter Pattern

This directory contains integration tests for the adapter pattern implementation in the Isolated Agents SDK.

## Overview

These tests verify that:
- Adapters can be switched at runtime
- Different adapter implementations work correctly together
- Data consistency is maintained across adapter switches
- Configuration system works end-to-end
- Registry manages adapters correctly

## Test Structure

```
tests/integration/
├── __init__.py
├── conftest.py                      # Shared fixtures
├── test_adapter_integration.py      # Main integration tests
└── README.md                        # This file
```

## Test Categories

### 1. Registry Integration Tests
- Registry initialization with configuration
- Adapter switching between different instances
- Thread-safe concurrent access
- Adapter registration and retrieval

### 2. Storage Adapter Integration Tests
- Complete storage lifecycle (store, retrieve, list, delete)
- Multiple session isolation
- Adapter switching with data isolation
- Metadata management

### 3. Audit Adapter Integration Tests
- Complete audit lifecycle (log, query, retrieve)
- Event query filtering by session, agent, and type
- Event statistics and analytics

### 4. Policy Adapter Integration Tests
- Policy validation with valid and invalid policies
- Batch policy validation
- Constraint checking

### 5. Configuration Integration Tests
- Configuration from dictionary
- Configuration validation
- Configuration merging with priority

### 6. End-to-End Integration Tests
- Complete workflow with all adapters
- Adapter isolation verification
- Multi-adapter coordination

## Running the Tests

### Run all integration tests:
```bash
pytest tests/integration/ -v
```

### Run specific test class:
```bash
pytest tests/integration/test_adapter_integration.py::TestStorageAdapterIntegration -v
```

### Run specific test:
```bash
pytest tests/integration/test_adapter_integration.py::TestStorageAdapterIntegration::test_storage_lifecycle -v
```

### Run with coverage:
```bash
pytest tests/integration/ --cov=isolated_agents_sdk.adapters --cov-report=html
```

## Test Fixtures

### `temp_dir`
Creates a temporary directory for test data. Automatically cleaned up after each test.

```python
def test_example(temp_dir):
    # temp_dir is a Path object
    file_path = temp_dir / "test.txt"
    file_path.write_text("test")
```

### `reset_registry`
Resets the adapter registry before and after each test to ensure test isolation.

```python
def test_example(reset_registry):
    registry = get_registry()
    # Registry is clean and empty
```

### `sample_session_id`
Provides a consistent session ID for tests.

```python
def test_example(sample_session_id):
    # sample_session_id = "test-session-123"
```

### `sample_agent_id`
Provides a consistent agent ID for tests.

```python
def test_example(sample_agent_id):
    # sample_agent_id = "test-agent-456"
```

## Writing New Tests

### Template for new integration test:

```python
import pytest
from isolated_agents_sdk.adapters import get_registry, AdapterConfig

class TestMyIntegration:
    """Test my integration scenario."""
    
    @pytest.mark.asyncio
    async def test_my_scenario(self, reset_registry, temp_dir):
        """Test description."""
        # Setup
        config = AdapterConfig(
            storage_adapter="local",
            storage_config={"base_path": str(temp_dir)}
        )
        
        registry = get_registry()
        registry.initialize_from_config(config)
        
        # Test
        storage = registry.get_storage_adapter()
        await storage.initialize()
        
        # Assertions
        assert storage is not None
        
        # Cleanup
        await storage.cleanup()
```

## Best Practices

1. **Use fixtures** - Leverage shared fixtures for common setup
2. **Clean up resources** - Always call `cleanup()` on adapters
3. **Test isolation** - Use `reset_registry` to ensure clean state
4. **Async tests** - Mark async tests with `@pytest.mark.asyncio`
5. **Descriptive names** - Use clear, descriptive test names
6. **Test one thing** - Each test should verify one specific behavior
7. **Use temp directories** - Never write to fixed paths

## Common Patterns

### Testing adapter switching:
```python
@pytest.mark.asyncio
async def test_adapter_switching(reset_registry, temp_dir):
    registry = get_registry()
    
    # Register multiple adapters
    adapter1 = LocalStorageAdapter(base_path=str(temp_dir / "storage1"))
    adapter2 = LocalStorageAdapter(base_path=str(temp_dir / "storage2"))
    
    registry.register_storage_adapter("adapter1", adapter1)
    registry.register_storage_adapter("adapter2", adapter2)
    
    # Switch between them
    registry.set_default_storage_adapter("adapter1")
    current = registry.get_storage_adapter()
    assert current is adapter1
    
    registry.set_default_storage_adapter("adapter2")
    current = registry.get_storage_adapter()
    assert current is adapter2
```

### Testing data isolation:
```python
@pytest.mark.asyncio
async def test_data_isolation(reset_registry, temp_dir):
    storage1 = LocalStorageAdapter(base_path=str(temp_dir / "storage1"))
    storage2 = LocalStorageAdapter(base_path=str(temp_dir / "storage2"))
    
    await storage1.initialize()
    await storage2.initialize()
    
    # Store different data in each
    await storage1.store_artifact("session", "file.txt", b"data1")
    await storage2.store_artifact("session", "file.txt", b"data2")
    
    # Verify isolation
    data1 = await storage1.retrieve_artifact("session", "file.txt")
    data2 = await storage2.retrieve_artifact("session", "file.txt")
    
    assert data1 == b"data1"
    assert data2 == b"data2"
    assert data1 != data2
```

### Testing configuration:
```python
@pytest.mark.asyncio
async def test_configuration(reset_registry, temp_dir):
    config = AdapterConfig(
        storage_adapter="local",
        storage_config={"base_path": str(temp_dir)},
        audit_adapter="file",
        audit_config={"log_path": str(temp_dir / "logs")},
    )
    
    registry = get_registry()
    registry.initialize_from_config(config)
    
    # Verify adapters are configured
    storage = registry.get_storage_adapter()
    audit = registry.get_audit_adapter()
    
    assert isinstance(storage, LocalStorageAdapter)
    assert isinstance(audit, FileAuditAdapter)
```

## Troubleshooting

### Tests fail with "Registry already initialized"
- Make sure you're using the `reset_registry` fixture
- Check that previous tests cleaned up properly

### Tests fail with "Directory not found"
- Use the `temp_dir` fixture instead of hardcoded paths
- Ensure directories are created before use

### Tests hang or timeout
- Check for missing `await` keywords
- Verify cleanup is called on all adapters
- Look for infinite loops or blocking operations

### Tests fail intermittently
- Check for race conditions in concurrent tests
- Ensure proper test isolation with fixtures
- Verify cleanup happens in all code paths

## Coverage Goals

- **Line coverage**: > 90%
- **Branch coverage**: > 85%
- **Integration scenarios**: All major workflows covered

## Contributing

When adding new integration tests:
1. Follow the existing test structure
2. Use descriptive test names
3. Add docstrings explaining what is being tested
4. Ensure tests are isolated and repeatable
5. Update this README if adding new test categories