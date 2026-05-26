"""Agnostic File Summariser Launcher.

This version avoids cloudpickle issues by running a standalone script inside the container.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy


def main():
    """Main entrypoint for the agnostic file summariser."""
    # Load from examples/.env
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY not found in .env or environment")
        sys.exit(1)

    # Determine workspace to summarise (default to project root)
    workspace_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent

    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)

    print(f"Launching agnostic summariser on: {workspace_path.absolute()}")

    result = run_agent(
        agent=None,  # No callable, use entrypoint instead
        working_dir=workspace_path,
        host_output_path=host_output,
        policy=Policy(
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["GROQ_API_KEY", "GROQ_API_BASE"],
            pip_packages=["langchain-groq", "langchain-core"],
            # The agent logic script is in the working_dir/examples/
            entrypoint=[
                "python3", "examples/summariser_agent_logic.py"
            ]
        )
    )

    print(f"\nAgent completed with exit code {result.exit_code}")

    if result.artifacts:
        summary_path = result.artifacts.get("summary.md")
        if summary_path:
            print("\n" + "="*50)
            print("SUMMARY FROM CONTAINER:")
            print("="*50 + "\n")
            print(Path(summary_path).read_text(encoding="utf-8"))

if __name__ == "__main__":
    main()
