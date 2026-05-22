"""
Example demonstrating v0.2.0 Durable Execution and Checkpointing.
The agent saves its progress, and if interrupted, it can resume from the last checkpoint.
"""

import asyncio
import os
import time
from isolated_agents_sdk import AgentRuntime, Policy, setup_logging
from isolated_agents_sdk.sub_agent_client import save_checkpoint, load_checkpoint

def durable_agent(target_count: int = 10):
    """An agent that performs a long-running task with checkpointing."""
    print(f"Agent starting. Goal: reach {target_count}")
    
    # 1. Try to load existing checkpoint
    checkpoint = load_checkpoint()
    if checkpoint:
        start_at = checkpoint.get("current_count", 0) + 1
        print(f"Resuming from checkpoint: {start_at-1}")
    else:
        start_at = 0
        print("No checkpoint found. Starting from scratch.")
        
    # 2. Perform work
    for i in range(start_at, target_count):
        print(f"Processing item {i}...")
        time.sleep(1) # Simulate work
        
        # 3. Save progress
        if i % 3 == 0:
            print(f"Saving checkpoint at {i}")
            save_checkpoint({"current_count": i})
            
    print("Agent finished successfully.")
    return f"Processed {target_count} items."

async def main():
    setup_logging()
    
    # Use a persistent working directory
    workspace = "./durable_demo"
    runtime = AgentRuntime(working_dir=workspace)
    await runtime.start()
    
    # Policy with 'durable' enabled
    policy = Policy(
        durable=True,
        timeout_seconds=60,
        allow_sub_agents=True # Required for IPC (checkpointing)
    )
    
    print("\n--- Running Durable Agent (Part 1) ---")
    # In a real scenario, you might stop the runtime here to simulate a crash.
    # We will just run it once.
    result = await runtime.run_agent(
        agent=durable_agent,
        kwargs={"target_count": 5},
        policy=policy
    )
    print(f"Result: {result.output}")
    
    # Verify state files exist
    state_dir = os.path.join(workspace, "state")
    print(f"\nChecking state directory: {state_dir}")
    if os.path.exists(state_dir):
        print(f"Files: {os.listdir(state_dir)}")

    await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
吐