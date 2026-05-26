"""Framework-agnostic hello world example.

This example demonstrates:
- Running a simple shell command/script
- No cloudpickle serialization
- File output

Usage:
    python examples/hello_world_agnostic.py
"""

from pathlib import Path
import sys

if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy
    import os

    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)

    print("Launching framework-agnostic hello agent...")

    # Use entrypoint to run a simple python command inside the container
    # This avoids cloudpickle serialization issues.
    result = run_agent(
        agent=None, # No callable
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            timeout_seconds=60,
            entrypoint=[
                "python3", "-c",
                "import platform; from pathlib import Path; "
                "out = Path('/output'); out.mkdir(parents=True, exist_ok=True); "
                "msg = f'Hello from agnostic container on {platform.system()}!'; "
                "Path('/output/greeting.txt').write_text(msg); "
                "print(msg)"
            ]
        )
    )

    print(f"\nAgent completed with exit code {result.exit_code}")

    greeting_path = result.artifacts.get("greeting.txt")
    if greeting_path and Path(greeting_path).exists():
        print(f"\nSuccess! Greeting from container:\n{Path(greeting_path).read_text()}")
    else:
        print("\nArtifact greeting.txt not found on host.")

    sys.exit(result.exit_code)
