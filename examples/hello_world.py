"""Simple hello world example.

This example demonstrates:
- Basic agent execution
- File output
- No external dependencies

Usage:
    python examples/hello_world.py
"""

import sys
from pathlib import Path

def hello_agent():
    """Simple agent that writes a greeting to /output."""
    import platform
    import pathlib
    
    # Use explicit names to avoid confusion during serialization
    out_dir = pathlib.Path("/output")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    msg = f"Hello from isolated container running on {platform.system()} {platform.machine()}!"
    (out_dir / "greeting.txt").write_text(msg)
    
    print(msg)


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    import os
    
    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)
    
    print("Launching hello agent...")
    
    result = run_agent(
        agent=hello_agent,
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            timeout_seconds=60,
            network=NetworkPolicy(disabled=False),
            pip_packages=["cloudpickle"],
        )
    )
    
    print(f"\nAgent completed with exit code {result.exit_code}")
    
    # The SDK's AgentResult.artifacts currently seems to be empty in the log I saw.
    # Let me check if the file exists on the host.
    greeting_file = host_output / "greeting.txt"
    if greeting_file.exists():
        print(f"\nSuccess! Greeting from container:\n{greeting_file.read_text()}")
    else:
        print("\nArtifact greeting.txt not found on host.")
    
    sys.exit(result.exit_code)
