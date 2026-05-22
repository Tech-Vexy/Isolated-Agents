"""
Example demonstrating real-time streamed outputs from an isolated agent.
This is useful for long-running tasks where you want to see progress in real-time.
"""

import time
import logging
from isolated_agents_sdk import run_agent, Policy
from isolated_agents_sdk.logging import setup_logging

def processing_agent(steps=5):
    """Agent that performs a multi-step task and prints progress."""
    print(f"Starting intensive processing of {steps} steps...")
    for i in range(1, steps + 1):
        time.sleep(1) # Simulate expensive work
        print(f"[STEP {i}/{steps}] Processing chunk {i*20}% complete...")
    print("All tasks finished successfully.")
    return "SUCCESS"

def main():
    setup_logging(level=logging.INFO)
    
    # Custom callback to capture stream
    output_buffer = []
    
    def my_stream_handler(chunk):
        # You could send this to a WebSocket, UI, or just filter it
        if "STEP" in chunk:
            print(f">>> UI Update: {chunk.strip()}")
        output_buffer.append(chunk)

    print("--- Launching Agent with Streamed Outputs ---")
    
    result = run_agent(
        agent=processing_agent,
        working_dir="./stream_workspace",
        agent_kwargs={"steps": 3},
        on_stdout=my_stream_handler, # Register the stream callback
        policy=Policy(memory_mb=256)
    )

    print("\n--- Final Summary ---")
    print(f"Exit Code: {result.exit_code}")
    print(f"Total chunks captured: {len(output_buffer)}")

if __name__ == "__main__":
    main()
