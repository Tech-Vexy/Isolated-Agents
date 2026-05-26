"""
Example demonstrating v0.2.0 Real-time Observability and Metrics.
The AgentRuntime now tracks telemetry automatically via the AuditLogger.
"""

import asyncio
import logging
import json
from isolated_agents_sdk import AgentRuntime, Policy, setup_logging

def noisy_agent():
    """Agent that generates some logs."""
    print("Agent is doing things...")
    return "Done"

def violating_agent():
    """Agent that will trigger a policy violation (simulated)."""
    # In a real run, the monitor would catch this.
    # Here we show how the runtime observes the audit event.
    print("Agent finished.")
    return "Check violations count"

async def main():
    # 1. Setup structured logging for the host
    setup_logging(level=logging.INFO, structured=True)

    runtime = AgentRuntime(working_dir="./obs_demo")
    await runtime.start()

    print("\n--- Starting Observability Demo ---")

    try:
        # 1. Run a normal agent
        await runtime.run_agent(agent=noisy_agent)

        # 2. Simulate a violation event being logged
        # (Usually this comes from the Runner's monitor)
        await runtime.audit_logger.log_event(
            event_type="resource_limit_exceeded",
            session_id="obs-task-1",
            agent_id="violator",
            payload={"violation_type": "oom_kill", "attempted_action": "malloc"}
        )

        # 3. Retrieve real-time telemetry from the Runtime API
        status = runtime.get_status()

        print("\n--- Runtime Telemetry Export ---")
        print(json.dumps(status["telemetry"], indent=2))

        print(f"\nTotal Executions: {status['telemetry']['total_executions']}")
        print(f"Total Violations: {status['telemetry']['violation_count']}")

    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())

