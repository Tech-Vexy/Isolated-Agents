"""Simplified Agent API Example.

This example demonstrates how to use the new fluent Agent API and the @agent decorator
to easily create and run isolated agents without needing to construct a Policy object manually.
"""

from pathlib import Path

from isolated_agents_sdk import Agent
from isolated_agents_sdk import agent_decorator as agent

# ---------------------------------------------------------------------------
# Method 1: Using the Fluent API
# ---------------------------------------------------------------------------


def calculate_primes():
    """Agent function that calculates prime numbers and saves them to a file."""

    def is_prime(n):
        if n < 2:
            return False
        return all(n % i != 0 for i in range(2, int(n ** 0.5) + 1))

    primes = [str(n) for n in range(1, 100) if is_prime(n)]

    # The agent automatically places outputs in '/workspace/output/'
    output_file = Path("/workspace/output/primes.txt")
    output_file.write_text(", ".join(primes))

    print(f"Calculated {len(primes)} primes.")
    return len(primes)


def run_fluent_agent():
    print("\n--- Running Fluent API Agent ---")

    # Create the agent and chain configuration methods
    my_agent = (
        Agent(calculate_primes)
        .with_workspace("./workspace/fluent_example")
        .with_memory(256)
        .with_cpu(1.0)
        .with_timeout(30)
    )

    # Run the agent (synchronously)
    result = my_agent.run()

    if result.exit_code == 0:
        print("Agent executed successfully!")

        # Artifacts are automatically collected from workspace/output
        if "primes.txt" in result.artifacts:
            print("Primes collected:", result.artifacts["primes.txt"][:50], "...")
    else:
        print("Agent failed:", result.error)


# ---------------------------------------------------------------------------
# Method 2: Using the @agent Decorator
# ---------------------------------------------------------------------------


# The decorator automatically applies the configuration to the function
@agent(workspace="./workspace/decorator_example", network=True, packages=["requests"], memory=512)
def fetch_data_agent():
    """Agent function that fetches data from the internet."""
    import requests

    response = requests.get("https://jsonplaceholder.typicode.com/todos/1")
    data = response.json()

    Path("/workspace/output/data.json").write_text(str(data))
    return "Data fetched successfully!"


def run_decorated_agent():
    print("\n--- Running Decorated Agent ---")

    # The decorated function is now an Agent object, so we call .run()
    result = fetch_data_agent.run()

    if result.exit_code == 0:
        print("Agent executed successfully!")
        if "data.json" in result.artifacts:
            print("Data collected:", result.artifacts["data.json"])
    else:
        print("Agent failed:", result.error)


if __name__ == "__main__":
    run_fluent_agent()
    run_decorated_agent()
