"""Example demonstrating structured (JSON) logging."""

import logging
import asyncio
from isolated_agents_sdk import setup_logging, run_agent, Policy

def simple_agent():
    # Inside the agent, we just do something
    print("Agent is running...")
    return {"status": "success"}

async def main():
    # 1. Enable structured logging
    # This will output logs as JSON objects, ideal for ELK/Splunk/CloudWatch
    setup_logging(level=logging.INFO, structured=True)
    
    logger = logging.getLogger("isolated_agents_sdk.example")
    logger.info("Starting structured logging demo")
    
    # 2. Log with extra fields
    # Using the 'extra' parameter allows adding arbitrary metadata to the JSON line
    logger.info("Executing agent with metadata", extra={"agent_type": "python", "demo_mode": True})
    
    # 3. Run an agent
    # The SDK's internal logs will now also be JSON
    run_agent(simple_agent, working_dir="./workspace")
    
    logger.info("Demo completed")

if __name__ == "__main__":
    asyncio.run(main())
吐