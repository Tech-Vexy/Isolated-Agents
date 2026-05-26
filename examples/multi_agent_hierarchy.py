"""
Example demonstrating a Hierarchical Multi-Agent pattern (v0.2.1 Hardening).

Features:
- Parent Manager at Level 0 (allocated 1.0 CPU, 1024MB Memory).
- Specialized Workers spawned at Level 1.
- Hierarchical Resource Pooling: Worker budgets are subtracted from Manager's remaining budget.
- Reliable IPC: Uses 4-byte framing for large artifacts.
- Cascading Teardown: If Manager times out, all Workers are automatically reaped.
"""

import asyncio
import logging
from isolated_agents_sdk import AgentRuntime, Policy
from isolated_agents_sdk.sub_agent_client import spawn_sub_agent
from isolated_agents_sdk.logging import setup_logging

# --- Worker Agent Logic ---
def researcher_worker(topic: str):
    print(f"[Researcher] Analyzing topic: {topic}")
    # Simulating a payload to demonstrate reliable 4-byte framing (v0.2.1)
    large_data = "x" * (128 * 1024) # 128KB payload
    return {
        "source": "Academic Journals",
        "entities": ["Concept A", "Entity B"],
        "summary": f"Found 3 relevant papers on {topic}.",
        "raw_data_size": len(large_data)
    }

def writer_worker(data: dict):
    print("[Writer] Crafting report from research data...")
    summary = data.get("summary", "No data")
    return f"FINAL REPORT: Based on research stating '{summary}', we conclude that... (Processed {data.get('raw_data_size')} bytes)"

# --- Manager Agent Logic (Recursive Host) ---
def manager_agent(task: str):
    print(f"[Manager] Received task: {task}")

    # 1. Spawn Researcher Sub-Agent
    # v0.2.1: This request for 256MB is validated against the Manager's 1024MB budget.
    print("[Manager] Spawning Researcher...")
    research_result = spawn_sub_agent(
        agent=researcher_worker,
        kwargs={"topic": task},
        policy=Policy(memory_mb=256)
    )

    if research_result.exit_code != 0:
        return f"Error in Research: {research_result.error}"

    data = research_result.output

    # 2. Spawn Writer Sub-Agent with Researcher's output
    print("[Manager] Spawning Writer...")
    write_result = spawn_sub_agent(
        agent=writer_worker,
        kwargs={"data": data},
        policy=Policy(memory_mb=256)
    )

    if write_result.exit_code != 0:
        return f"Error in Writing: {write_result.error}"

    return write_result.output

async def main():
    setup_logging(level=logging.INFO)

    # The runtime host mediates all sub-agent spawns and IPC
    runtime = AgentRuntime(working_dir="./multi_agent_workspace")
    await runtime.start()

    try:
        # v0.2.1 Resource Pooling:
        # Manager gets 1024MB.
        # Combined sub-agents (256+256=512MB) are safely within this hierarchical budget.
        policy = Policy(
            allow_sub_agents=True,
            memory_mb=1024,
            timeout_seconds=60 # If manager times out, all workers will be reaped.
        )

        print("--- Launching Hierarchical Multi-Agent System (v0.2.1) ---")
        result = await runtime.run_agent(
            agent=manager_agent,
            kwargs={"task": "Quantum Computing Trends"},
            policy=policy
        )

        if result.exit_code == 0:
            print("\n--- Final Aggregated Result ---")
            print(result.output)
        else:
            print(f"\n--- System Failure: {result.error} ---")

    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())

