"""Basic adapter usage example.

This example demonstrates how to use the adapter system with the Isolated Agents SDK.
It shows:
1. Loading configuration from files
2. Using the adapter registry
3. Creating adapters with the factory
4. Switching between different adapter implementations
"""

import asyncio
from pathlib import Path

from isolated_agents_sdk.adapters import (
    AdapterConfig,
    AdapterFactory,
    AdapterRegistry,
    get_registry,
    load_config,
)


async def example_1_load_from_config_file():
    """Example 1: Load adapters from a configuration file."""
    print("=" * 70)
    print("Example 1: Loading adapters from configuration file")
    print("=" * 70)

    # Load configuration from YAML file
    config = load_config(config_file="examples/adapters/config.yaml")

    print(f"Container adapter: {config.container_adapter}")
    print(f"Storage adapter: {config.storage_adapter}")
    print(f"Audit adapter: {config.audit_adapter}")
    print(f"Policy adapter: {config.policy_adapter}")

    # Initialize the registry with the configuration
    registry = get_registry()
    registry.initialize_from_config(config)

    # Get adapters from the registry
    container = registry.get_container_adapter()
    storage = registry.get_storage_adapter()
    audit = registry.get_audit_adapter()
    policy = registry.get_policy_adapter()

    print(f"\nContainer adapter type: {type(container).__name__}")
    print(f"Storage adapter type: {type(storage).__name__}")
    print(f"Audit adapter type: {type(audit).__name__}")
    print(f"Policy adapter type: {type(policy).__name__}")
    print()


async def example_2_programmatic_configuration():
    """Example 2: Configure adapters programmatically."""
    print("=" * 70)
    print("Example 2: Programmatic adapter configuration")
    print("=" * 70)

    # Create configuration programmatically
    config = AdapterConfig(
        container_adapter="podman",
        container_config={"timeout": 300},
        storage_adapter="local",
        storage_config={"base_path": "./my_storage"},
        audit_adapter="file",
        audit_config={"log_file": "./my_logs/audit.jsonl"},
        policy_adapter="default",
        policy_config={"strict_mode": False},
    )

    # Reset registry for this example
    AdapterRegistry.reset_instance()
    registry = get_registry()
    registry.initialize_from_config(config)

    print("Adapters configured programmatically:")
    adapters = registry.list_adapters()
    for adapter_type, names in adapters.items():
        print(f"  {adapter_type}: {names}")
    print()


async def example_3_factory_pattern():
    """Example 3: Create adapters using the factory pattern."""
    print("=" * 70)
    print("Example 3: Using the adapter factory")
    print("=" * 70)

    # Create adapters directly using the factory
    container = AdapterFactory.create_container_adapter("podman")
    storage = AdapterFactory.create_storage_adapter("local", base_path="./storage")
    audit = AdapterFactory.create_audit_adapter("file", log_file="./logs/audit.jsonl")
    policy = AdapterFactory.create_policy_adapter("default")

    print(f"Created container adapter: {type(container).__name__}")
    print(f"Created storage adapter: {type(storage).__name__}")
    print(f"Created audit adapter: {type(audit).__name__}")
    print(f"Created policy adapter: {type(policy).__name__}")
    print()


async def example_4_environment_variables():
    """Example 4: Load configuration from environment variables."""
    print("=" * 70)
    print("Example 4: Loading from environment variables")
    print("=" * 70)

    import os

    # Set environment variables
    os.environ["ISOLATED_AGENTS_CONTAINER_ADAPTER"] = "podman"
    os.environ["ISOLATED_AGENTS_STORAGE_ADAPTER"] = "local"
    os.environ["ISOLATED_AGENTS_STORAGE_BASE_PATH"] = "./env_storage"
    os.environ["ISOLATED_AGENTS_AUDIT_ADAPTER"] = "file"
    os.environ["ISOLATED_AGENTS_POLICY_ADAPTER"] = "default"

    # Load configuration from environment
    config = AdapterConfig.from_env()

    print(f"Container adapter: {config.container_adapter}")
    print(f"Storage adapter: {config.storage_adapter}")
    print(f"Storage base path: {config.storage_config.get('base_path')}")
    print(f"Audit adapter: {config.audit_adapter}")
    print(f"Policy adapter: {config.policy_adapter}")
    print()


async def example_5_adapter_operations():
    """Example 5: Perform operations with adapters."""
    print("=" * 70)
    print("Example 5: Adapter operations")
    print("=" * 70)

    # Reset and initialize registry
    AdapterRegistry.reset_instance()
    config = AdapterConfig(
        storage_adapter="local",
        storage_config={"base_path": "./demo_storage"},
        audit_adapter="file",
        audit_config={"log_file": "./demo_logs/audit.jsonl"},
        policy_adapter="default",
    )

    registry = get_registry()
    registry.initialize_from_config(config)

    # Get adapters
    storage = registry.get_storage_adapter()
    audit = registry.get_audit_adapter()
    policy = registry.get_policy_adapter()

    # Storage operations
    print("Storage adapter operations:")

    # Create a test artifact
    test_data = b"Hello, Isolated Agents!"

    # Store artifact
    location = await storage.store_artifact(
        session_id="demo-session",
        artifact_name="test_artifact.txt",
        data=test_data,
        content_type="text/plain",
    )
    print(f"  Stored artifact: {location.path}")

    # Retrieve artifact
    retrieved = await storage.retrieve_artifact(
        session_id="demo-session",
        artifact_name="test_artifact.txt",
    )
    print(f"  Retrieved {len(retrieved)} bytes")

    # List artifacts
    artifacts = await storage.list_artifacts("demo-session")
    print(f"  Total artifacts: {len(artifacts)}")

    # Audit operations
    print("\nAudit adapter operations:")
    from isolated_agents_sdk.adapters.audit.types import EventType

    await audit.log_event(
        event_type=EventType.AGENT_STARTED,
        session_id="demo-session",
        agent_id="demo-agent",
        payload={"message": "Demo agent started"},
    )
    print("  Logged agent_started event")

    # Query audit events
    from isolated_agents_sdk.adapters.audit.types import AuditQuery
    query = AuditQuery(session_id="demo-session")
    events = await audit.query_events(query)
    print(f"  Found {len(events)} audit events")

    # Policy operations
    print("\nPolicy adapter operations:")
    from isolated_agents_sdk.models import Policy

    test_policy = Policy(
        cpu_cores=2.0,
        memory_mb=1024,
    )

    result = await policy.validate_policy(test_policy)
    print(f"  Policy valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Warnings: {len(result.warnings)}")

    # Cleanup
    import shutil
    if Path("./demo_storage").exists():
        shutil.rmtree("./demo_storage")
    if Path("./demo_logs").exists():
        shutil.rmtree("./demo_logs")

    print()


async def example_6_switching_adapters():
    """Example 6: Switch between different adapter implementations."""
    print("=" * 70)
    print("Example 6: Switching adapter implementations")
    print("=" * 70)

    # Reset registry
    AdapterRegistry.reset_instance()
    registry = get_registry()

    # Register multiple storage adapters
    local_storage = AdapterFactory.create_storage_adapter(
        "local",
        base_path="./storage1"
    )
    registry.register_storage_adapter("local1", local_storage)

    local_storage2 = AdapterFactory.create_storage_adapter(
        "local",
        base_path="./storage2"
    )
    registry.register_storage_adapter("local2", local_storage2)

    # Use first storage adapter
    print("Using storage adapter 'local1':")
    storage1 = registry.get_storage_adapter("local1")
    print(f"  Adapter type: {type(storage1).__name__}")

    # Switch to second storage adapter
    registry.set_default_storage_adapter("local2")
    print("\nSwitched to storage adapter 'local2':")
    storage2 = registry.get_storage_adapter()
    print(f"  Adapter type: {type(storage2).__name__}")

    # List all registered adapters
    print("\nAll registered adapters:")
    adapters = registry.list_adapters()
    for adapter_type, names in adapters.items():
        print(f"  {adapter_type}: {names}")
    print()


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("ISOLATED AGENTS SDK - ADAPTER USAGE EXAMPLES")
    print("=" * 70 + "\n")

    await example_1_load_from_config_file()
    await example_2_programmatic_configuration()
    await example_3_factory_pattern()
    await example_4_environment_variables()
    await example_5_adapter_operations()
    await example_6_switching_adapters()

    print("=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
