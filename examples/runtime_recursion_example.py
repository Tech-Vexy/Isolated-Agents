"""
Example demonstrating Recursive Orchestration & Budget Hardening (v0.2.1).

Features:
- Hierarchical Budgeting: Sub-agents consume resources from the parent's slice.
- IPC Framing: 4-byte length-prefixed protocol for large payload support (>64KB).
- Cascading Cleanup: If the parent times out, all child containers are reaped instantly.
"""

import asyncio
import logging
import os
from isolated_agents_sdk import AgentRuntime, Policy
from isolated_agents_sdk.sub_agent_client import spawn_sub_agent
from isolated_agents_sdk.logging import setup_logging

# Agent logic that will run INSIDE the container
def recursive_agent(level=0):
    print(f"--- Agent Level {level} starting (PID {os.getpid()}) ---")

    # In v0.2.1, we can check our remaining hierarchical budget
    # (Future API: get_remaining_slice())

    if level < 2:
        print(f"Level {level} spawning sub-agent for level {level+1}...")
        try:
            # v0.2.1 Enhancement: IPC now uses 4-byte prefixes.
            # This allows huge prompt strings or large result sets to pass between levels.
            result = spawn_sub_agent(
                agent=recursive_agent,
                kwargs={"level": level + 1},
                policy=Policy(
                    allow_sub_agents=True,
                    memory_mb=128 # Sub-agent takes 128MB from Parent's allocation
                )
            )
            print(f"Child {level+1} returned code: {result.exit_code}")
            return f"L{level} success (Child L{level+1} done)"
        except Exception as e:
            print(f"L{level} spawn error: {e}")
            return "Spawn Failure"

    # Generate a large output to test IPC Framing (>64KB)
    large_payload = "X" * 100_000 # 100KB
    print(f"Level {level} (Leaf) returning 100KB payload via framed IPC...")
    return {"status": "Complete", "data": large_payload}

async def main():
    setup_logging(level=logging.INFO)

    # Initialize the v0.2.1 Runtime
    # All internal state (sockets, pkls) now hidden in /run/isolated_agents_internal/
    runtime = AgentRuntime(working_dir="./runtime_workspace")
    await runtime.start()

    try:
        print("Launching top-level agent (Total Budget: 512MB RAM)...")
        policy = Policy(
            allow_sub_agents=True,
            memory_mb=512,
            cpu_quota=1.0
        )

        result = await runtime.run_agent(
            agent=recursive_agent,
            policy=policy,
            kwargs={"level": 0}
        )

        print("\n--- Execution Summary ---")
        print(f"Exit Code: {result.exit_code}")
        if result.exit_code == 0:
            print(f"Result Length: {len(result.output['data'])} bytes (Successfully framed)")

    finally:
        print("\nStopping Runtime & Reaping Orphaned Containers...")
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
