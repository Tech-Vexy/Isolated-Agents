"""Example of a recursive agent using the Sub-Agent Spawn API."""

import time
from isolated_agents_sdk import run_agent, Policy, spawn_sub_agent

def child_agent(message: str):
    """Simple agent that returns a message."""
    print(f"Child agent received: {message}")
    return {"status": "success", "received": message}

def parent_agent():
    """Agent that spawns a sub-agent."""
    print("Parent agent starting...")

    # In a real scenario, this would trigger the Spawn Daemon IPC
    # which in turn calls run_agent on the host.
    try:
        result = spawn_sub_agent(
            agent=child_agent,
            args=("Hello from the sandbox!",),
            policy=Policy(cpu_cores=0.5, memory_mb=256)
        )
        print(f"Sub-agent execution finished with result: {result.output}")
        return {
            "parent_status": "done",
            "child_result": result.artifacts
        }
    except Exception as e:
        print(f"Failed to spawn sub-agent: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    # We enable allow_sub_agents in the policy to mount the spawn socket
    policy = Policy(
        allow_sub_agents=True,
        pip_packages=["cloudpickle"]
    )

    print("Running parent agent...")
    result = run_agent(parent_agent, policy=policy)

    print("\nFinal Result:")
    print(result.output)
    if result.artifacts:
        print(f"Artifacts: {result.artifacts}")
