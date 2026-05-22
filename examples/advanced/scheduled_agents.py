"""Example demonstrating the Agent Scheduler."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from isolated_agents_sdk import (
    start_scheduler,
    stop_scheduler,
    schedule_agent_in,
    schedule_agent_interval,
    list_scheduled_agents,
    Policy
)

def hello_scheduled(name: str):
    """Simple agent to be run on a schedule."""
    print(f"[{datetime.now()}] Hello {name}! This agent was run from the scheduler.")
    return {"message": f"Hello {name}", "time": str(datetime.now())}

async def main():
    # 1. Start the background scheduler
    await start_scheduler()
    print("Scheduler started...")

    # Create a temporary workspace
    workspace = "./scheduled_workspace"
    os.makedirs(workspace, exist_ok=True)

    # 2. Schedule a one-off task in 5 seconds
    print("Scheduling one-off task for 5 seconds in the future...")
    task1 = schedule_agent_in(
        delay=5,
        agent=hello_scheduled,
        working_dir=workspace,
        args=("One-Off-Agent",)
    )

    # 3. Schedule a recurring task every 10 seconds
    print("Scheduling recurring task every 10 seconds...")
    task2 = schedule_agent_interval(
        interval=10,
        agent=hello_scheduled,
        working_dir=workspace,
        args=("Interval-Agent",)
    )

    # Monitor tasks for a while
    for i in range(25):
        tasks = list_scheduled_agents()
        print(f"\nTime: {i}s | Active Tasks: {len(tasks)}")
        for t in tasks:
            print(f"  - {t}")
        await asyncio.sleep(1)

    # 4. Stop the scheduler
    print("\nStopping scheduler...")
    await stop_scheduler()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
