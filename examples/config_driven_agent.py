"""Config-Driven Agent Example.

This example demonstrates how to load agent configurations from a TOML file
and initialize agents dynamically.
"""

from pathlib import Path

from isolated_agents_sdk import Agent
from isolated_agents_sdk.config import load_config

# ---------------------------------------------------------------------------
# Agent Functions
# ---------------------------------------------------------------------------


def my_scraper_agent():
    """A simulated scraper agent."""
    import json
    from pathlib import Path

    # Simulating work...
    data = {"status": "success", "items_scraped": 42}

    # Output is automatically placed in workspace/output/
    output_file = Path("/workspace/output/scraper_results.json")
    output_file.write_text(json.dumps(data))

    print("Scraping completed!")
    return 42


def my_data_processor_agent():
    """A simulated data processor agent."""
    from pathlib import Path

    # Output is automatically placed in workspace/output/
    output_file = Path("/workspace/output/processed.txt")
    output_file.write_text("Processed data...")

    print("Processing completed!")
    return True


# ---------------------------------------------------------------------------
# Example Runner
# ---------------------------------------------------------------------------


def run_config_example():
    print("\n--- Running Config-Driven Agent Example ---")

    config_path = Path(__file__).parent / "agent_config.toml"

    if not config_path.exists():
        print(f"Please ensure {config_path} exists before running.")
        return

    # 1. Load the configuration
    print(f"Loading configuration from {config_path}...")
    config = load_config(config_path)

    print("Available agents in config:", config.list_agents())

    # 2. Instantiate and run the scraper agent
    print("\nInitializing Scraper Agent...")
    scraper = Agent.from_config(config, "web_scraper", my_scraper_agent)

    print("Scraper Agent Policy:")
    print(" - Memory (MB):", scraper._memory_mb)
    print(" - Network:", "Enabled" if scraper._network_enabled else "Disabled")
    print(" - Endpoints:", scraper._allowed_endpoints)

    try:
        # Run it! (Will fail if no container runtime is available)
        result = scraper.run()
        if result.exit_code == 0:
            print("Scraper finished successfully!")
    except Exception as e:
        print(f"Execution skipped/failed: {e}")


if __name__ == "__main__":
    run_config_example()
