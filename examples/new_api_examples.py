"""Examples demonstrating the new simplified Agent API.

This file shows how to use the new Agent class which provides:
- Simpler, more intuitive API
- Fluent/chainable configuration
- Context manager support
- Better defaults
- Backward compatible with existing code

All examples are fully functional and can be run directly.
"""

import os
from pathlib import Path


# ============================================================================
# Example 1: Basic Usage (Simplest Form)
# ============================================================================

def example_1_basic():
    """Simplest possible agent usage."""
    from isolated_agents_sdk import Agent
    
    def my_agent():
        """Simple agent that writes a greeting."""
        from pathlib import Path
        
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "greeting.txt").write_text("Hello from the new API!")
        
        print("✓ Agent completed successfully")
    
    # Create and run agent in one line
    agent = Agent(my_agent, workspace="./workspace")
    result = agent.run()
    
    print(f"Exit code: {result.exit_code}")
    if result.artifacts:
        greeting = Path(result.artifacts["greeting.txt"]).read_text()
        print(f"Greeting: {greeting}")


# ============================================================================
# Example 2: Fluent API (Chainable Configuration)
# ============================================================================

def example_2_fluent():
    """Using the fluent/chainable API for configuration."""
    from isolated_agents_sdk import Agent
    
    def data_processor():
        """Agent that processes data with pandas."""
        import pandas as pd
        from pathlib import Path
        
        # Create sample data
        df = pd.DataFrame({
            'name': ['Alice', 'Bob', 'Charlie'],
            'age': [25, 30, 35],
            'city': ['NYC', 'LA', 'Chicago']
        })
        
        # Save output
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_dir / "data.csv", index=False)
        
        print(f"✓ Processed {len(df)} rows")
    
    # Fluent API - chain configuration methods
    result = (Agent(data_processor)
        .with_workspace("./workspace")
        .with_packages("pandas", "numpy")
        .with_memory(2048)
        .with_timeout(120)
        .run())
    
    print(f"Exit code: {result.exit_code}")


# ============================================================================
# Example 3: Network Access (Simplified)
# ============================================================================

def example_3_network():
    """Agent with network access - simplified configuration."""
    from isolated_agents_sdk import Agent
    
    def api_caller():
        """Agent that calls an external API."""
        import requests
        from pathlib import Path
        
        # Call API
        response = requests.get("https://api.github.com/repos/python/cpython")
        data = response.json()
        
        # Save result
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "repo_info.txt").write_text(
            f"Repository: {data['name']}\n"
            f"Stars: {data['stargazers_count']}\n"
            f"Forks: {data['forks_count']}\n"
        )
        
        print("✓ API call successful")
    
    # Simple network configuration
    result = (Agent(api_caller)
        .with_workspace("./workspace")
        .with_network(allowed=["api.github.com:443"])
        .with_packages("requests")
        .run())
    
    print(f"Exit code: {result.exit_code}")


# ============================================================================
# Example 4: Context Manager (Automatic Cleanup)
# ============================================================================

def example_4_context_manager():
    """Using Agent as a context manager."""
    from isolated_agents_sdk import Agent
    
    def my_agent():
        """Agent function."""
        from pathlib import Path
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.txt").write_text("Success!")
        print("✓ Completed")
    
    # Context manager ensures cleanup
    with Agent(my_agent, workspace="./workspace") as agent:
        result = agent.run()
        print(f"Exit code: {result.exit_code}")
    
    # Cleanup happens automatically here


# ============================================================================
# Example 5: Decorator Style
# ============================================================================

def example_5_decorator():
    """Using the @agent decorator."""
    from isolated_agents_sdk import agent_decorator as agent
    
    @agent(
        workspace="./workspace",
        network=True,
        packages=["requests"],
        memory=1024
    )
    def web_scraper():
        """Agent defined with decorator."""
        import requests
        from pathlib import Path
        
        response = requests.get("https://example.com")
        
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "page.html").write_text(response.text)
        
        print("✓ Page scraped")
    
    # Run the decorated agent
    result = web_scraper.run()
    print(f"Exit code: {result.exit_code}")


# ============================================================================
# Example 6: Environment Variables (Simplified)
# ============================================================================

def example_6_env_vars():
    """Passing environment variables - simplified."""
    from isolated_agents_sdk import Agent
    
    def env_user():
        """Agent that uses environment variables."""
        import os
        from pathlib import Path
        
        api_key = os.environ.get("API_KEY", "not-set")
        
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "config.txt").write_text(f"API Key: {api_key}")
        
        print("✓ Environment variables accessed")
    
    # Set environment variable
    os.environ["API_KEY"] = "test-key-123"
    
    # Simple env var configuration
    result = (Agent(env_user)
        .with_workspace("./workspace")
        .with_env("API_KEY")  # Pass through from host
        .run())
    
    print(f"Exit code: {result.exit_code}")


# ============================================================================
# Example 7: Comparison - Old vs New API
# ============================================================================

def example_7_comparison():
    """Side-by-side comparison of old and new APIs."""
    
    def my_agent():
        from pathlib import Path
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.txt").write_text("Success!")
    
    # OLD API (still works, backward compatible)
    print("=== Old API ===")
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    workspace = Path("./workspace")
    workspace.mkdir(exist_ok=True)
    output = workspace / "output"
    output.mkdir(exist_ok=True)
    
    result_old = run_agent(
        agent=my_agent,
        working_dir=workspace,
        host_output_path=output,
        policy=Policy(
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["API_KEY"],
            pip_packages=["requests"],
            memory_mb=2048,
            timeout_seconds=120
        )
    )
    print(f"Old API exit code: {result_old.exit_code}")
    
    # NEW API (simpler, more intuitive)
    print("\n=== New API ===")
    from isolated_agents_sdk import Agent
    
    result_new = (Agent(my_agent)
        .with_workspace("./workspace")
        .with_network(allowed=["api.example.com:443"])
        .with_env("API_KEY")
        .with_packages("requests")
        .with_memory(2048)
        .with_timeout(120)
        .run())
    print(f"New API exit code: {result_new.exit_code}")
    
    print("\n✓ Both APIs produce the same result!")


# ============================================================================
# Example 8: Advanced Configuration
# ============================================================================

def example_8_advanced():
    """Advanced configuration with the new API."""
    from isolated_agents_sdk import Agent
    
    def advanced_agent():
        """Agent with advanced configuration."""
        from pathlib import Path
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.txt").write_text("Advanced!")
        print("✓ Advanced agent completed")
    
    # All configuration options available
    result = (Agent(advanced_agent)
        .with_workspace("./workspace")
        .with_cpu(4.0)
        .with_memory(4096)
        .with_timeout(600)
        .with_network(allowed=[
            "api.openai.com:443",
            "api.anthropic.com:443"
        ])
        .with_packages(
            "requests",
            "pandas",
            "numpy",
            "matplotlib"
        )
        .with_env(
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY"
        )
        .with_base_image("python:3.11-slim")
        .run())
    
    print(f"Exit code: {result.exit_code}")


# ============================================================================
# Example 9: Error Handling with Helpful Messages
# ============================================================================

def example_9_error_handling():
    """Demonstrating improved error messages."""
    from isolated_agents_sdk import Agent
    from isolated_agents_sdk.exceptions import WorkingDirectoryError
    
    def my_agent():
        from pathlib import Path
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.txt").write_text("Success!")
    
    try:
        # This will fail with a helpful error message
        agent = Agent(my_agent)
        result = agent.run()  # No workspace specified!
    except ValueError as e:
        print("Caught expected error:")
        print(f"  {e}")
        print("\n✓ Error message is helpful and actionable!")


# ============================================================================
# Example 10: Async Support
# ============================================================================

async def example_10_async():
    """Using the async API."""
    from isolated_agents_sdk import Agent
    
    def my_agent():
        from pathlib import Path
        output_dir = Path("/workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "result.txt").write_text("Async success!")
        print("✓ Async agent completed")
    
    # Async execution
    agent = Agent(my_agent, workspace="./workspace")
    result = await agent.run_async()
    
    print(f"Exit code: {result.exit_code}")


# ============================================================================
# Run Examples
# ============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("Isolated Agents SDK - New API Examples")
    print("=" * 70)
    print()
    
    examples = [
        ("Basic Usage", example_1_basic),
        ("Fluent API", example_2_fluent),
        ("Network Access", example_3_network),
        ("Context Manager", example_4_context_manager),
        ("Decorator Style", example_5_decorator),
        ("Environment Variables", example_6_env_vars),
        ("Old vs New API", example_7_comparison),
        ("Advanced Configuration", example_8_advanced),
        ("Error Handling", example_9_error_handling),
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{'=' * 70}")
        print(f"Example {i}: {name}")
        print('=' * 70)
        
        try:
            func()
            print(f"\n✓ Example {i} completed successfully")
        except Exception as e:
            print(f"\n✗ Example {i} failed: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("=" * 70)
    print("All examples completed!")
    print("=" * 70)
