"""Example: Using the adapter-aware public API.

This example demonstrates how to use the new adapter configuration
features in the public API while maintaining backward compatibility.
"""

import asyncio
from pathlib import Path
from isolated_agents_sdk import (
    run_agent,
    async_run_agent,
    configure_adapters,
    get_adapter_registry,
    Policy,
)


def my_agent():
    """Simple agent that creates output."""
    with open("/output/result.txt", "w") as f:
        f.write("Hello from agent!")
    return 0


# ---------------------------------------------------------------------------
# Example 1: Basic usage (backward compatible - no adapter configuration)
# ---------------------------------------------------------------------------

def example_basic():
    """Basic usage without adapter configuration (uses defaults)."""
    print("Example 1: Basic usage (backward compatible)")
    
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
        policy=Policy(timeout_seconds=30),
    )
    
    print(f"Exit code: {result.exit_code}")
    print(f"Artifacts: {list(result.artifacts.keys())}")
    print()


# ---------------------------------------------------------------------------
# Example 2: Global adapter configuration
# ---------------------------------------------------------------------------

def example_global_config():
    """Configure adapters globally for all subsequent runs."""
    print("Example 2: Global adapter configuration")
    
    # Configure adapters once at application startup
    configure_adapters(config={
        "container": {
            "type": "podman",
            "config": {
                "base_image": "python:3.11-slim"
            }
        },
        "storage": {
            "type": "local",
            "config": {
                "base_path": "/tmp/agent_storage"
            }
        },
        "audit": {
            "type": "file",
            "config": {
                "log_path": "./audit.log"
            }
        },
        "policy": {
            "type": "default"
        }
    })
    
    # All subsequent runs use the configured adapters
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
    )
    
    print(f"Exit code: {result.exit_code}")
    print()


# ---------------------------------------------------------------------------
# Example 3: Per-run adapter configuration
# ---------------------------------------------------------------------------

def example_per_run_config():
    """Configure adapters for a specific run only."""
    print("Example 3: Per-run adapter configuration")
    
    # This configuration applies only to this specific run
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
        adapter_config={
            "container": {"type": "podman"},
            "storage": {"type": "local"},
        }
    )
    
    print(f"Exit code: {result.exit_code}")
    print()


# ---------------------------------------------------------------------------
# Example 4: Configuration from file
# ---------------------------------------------------------------------------

def example_config_from_file():
    """Load adapter configuration from a YAML or JSON file."""
    print("Example 4: Configuration from file")
    
    # Load configuration from YAML file
    configure_adapters(config_file="./config.yaml")
    
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
    )
    
    print(f"Exit code: {result.exit_code}")
    print()


# ---------------------------------------------------------------------------
# Example 5: Configuration from environment variables
# ---------------------------------------------------------------------------

def example_config_from_env():
    """Load adapter configuration from environment variables."""
    print("Example 5: Configuration from environment")
    
    # Set environment variables:
    # ISOLATED_AGENTS_CONTAINER_TYPE=podman
    # ISOLATED_AGENTS_STORAGE_TYPE=local
    # ISOLATED_AGENTS_AUDIT_TYPE=file
    # ISOLATED_AGENTS_POLICY_TYPE=default
    
    configure_adapters(from_env=True)
    
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
    )
    
    print(f"Exit code: {result.exit_code}")
    print()


# ---------------------------------------------------------------------------
# Example 6: Async API with adapter configuration
# ---------------------------------------------------------------------------

async def example_async_with_adapters():
    """Use async API with adapter configuration."""
    print("Example 6: Async API with adapters")
    
    # Configure adapters for async execution
    result = await async_run_agent(
        agent=my_agent,
        working_dir="./workspace",
        adapter_config={
            "container": {"type": "podman"},
            "storage": {"type": "local"},
        }
    )
    
    print(f"Exit code: {result.exit_code}")
    print()


# ---------------------------------------------------------------------------
# Example 7: Accessing the adapter registry
# ---------------------------------------------------------------------------

def example_registry_access():
    """Access the adapter registry for advanced use cases."""
    print("Example 7: Accessing adapter registry")
    
    # Get the global registry
    registry = get_adapter_registry()
    
    if registry:
        # Access individual adapters
        container_adapter = registry.get_container_adapter()
        storage_adapter = registry.get_storage_adapter()
        audit_adapter = registry.get_audit_adapter()
        policy_adapter = registry.get_policy_adapter()
        
        print(f"Container adapter: {type(container_adapter).__name__}")
        print(f"Storage adapter: {type(storage_adapter).__name__}")
        print(f"Audit adapter: {type(audit_adapter).__name__}")
        print(f"Policy adapter: {type(policy_adapter).__name__}")
    else:
        print("Adapter support not available")
    
    print()


# ---------------------------------------------------------------------------
# Example 8: Mixed usage (backward compatible)
# ---------------------------------------------------------------------------

def example_mixed_usage():
    """Mix old and new API styles (fully backward compatible)."""
    print("Example 8: Mixed usage")
    
    # Old style - still works perfectly
    result1 = run_agent(
        agent=my_agent,
        working_dir="./workspace",
    )
    print(f"Old style exit code: {result1.exit_code}")
    
    # New style - with adapter configuration
    result2 = run_agent(
        agent=my_agent,
        working_dir="./workspace",
        adapter_config={"container": {"type": "podman"}}
    )
    print(f"New style exit code: {result2.exit_code}")
    
    print()


# ---------------------------------------------------------------------------
# Example 9: Error handling
# ---------------------------------------------------------------------------

def example_error_handling():
    """Handle errors when adapter support is not available."""
    print("Example 9: Error handling")
    
    try:
        configure_adapters(config={
            "container": {"type": "podman"}
        })
        print("Adapters configured successfully")
    except ImportError as e:
        print(f"Adapter support not available: {e}")
        print("Falling back to default behavior")
        
        # Still works with default implementations
        result = run_agent(
            agent=my_agent,
            working_dir="./workspace",
        )
        print(f"Exit code: {result.exit_code}")
    
    print()


# ---------------------------------------------------------------------------
# Example 10: Production deployment pattern
# ---------------------------------------------------------------------------

def example_production_pattern():
    """Recommended pattern for production deployments."""
    print("Example 10: Production deployment pattern")
    
    # 1. Configure adapters once at application startup
    try:
        # Try to load from environment (12-factor app pattern)
        configure_adapters(from_env=True)
        print("Loaded configuration from environment")
    except (ImportError, ValueError):
        try:
            # Fall back to configuration file
            configure_adapters(config_file="./config.yaml")
            print("Loaded configuration from file")
        except (ImportError, FileNotFoundError):
            # Fall back to defaults
            print("Using default configuration")
    
    # 2. Run agents normally - configuration is already set
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
        policy=Policy(
            cpu_cores=2.0,
            memory_mb=1024,
            timeout_seconds=300,
        ),
    )
    
    print(f"Exit code: {result.exit_code}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Run all examples."""
    print("=" * 70)
    print("Adapter-Aware Public API Examples")
    print("=" * 70)
    print()
    
    # Note: These examples assume workspace directory exists
    workspace = Path("./workspace")
    workspace.mkdir(exist_ok=True)
    
    # Run synchronous examples
    example_basic()
    # example_global_config()  # Uncomment to test
    # example_per_run_config()  # Uncomment to test
    # example_config_from_file()  # Uncomment to test (requires config.yaml)
    # example_config_from_env()  # Uncomment to test (requires env vars)
    example_registry_access()
    example_mixed_usage()
    example_error_handling()
    example_production_pattern()
    
    # Run async example
    print("Running async example...")
    asyncio.run(example_async_with_adapters())
    
    print("=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()

# Made with Bob
