"""
Example demonstrating the AgentScheduler with Memory Leak Protection (v0.2.1).

The scheduler now uses a rolling results buffer (maxlen=10) to prevent
unbounded memory growth for long-running monitoring tasks.
"""

import asyncio
import logging
from datetime import timedelta
from isolated_agents_sdk import AgentScheduler, Policy, async_run_agent
from isolated_agents_sdk.logging import setup_logging

# Simple task logic
def disk_check_agent():
    import shutil
    total, used, free = shutil.disk_usage("/")
    print(f"--- [Background Agent] Disk Check: {used // (2**30)}GB used / {free // (2**30)}GB free ---")
    return {"used_gb": used // (2**30), "free_gb": free // (2**30)}

async def main():
    setup_logging(level=logging.INFO)
    
    # Initialize the scheduler (v0.2.1: results are stored in a rolling buffer)
    scheduler = AgentScheduler(run_agent_coro=async_run_agent)
    await scheduler.start()
    
    # 1. Schedule a task to run every 5 seconds
    # v0.2.1 fix ensures that even if this runs 1 million times, only the last 10 outcomes are in RAM.
    scheduler.schedule_interval(
        interval=5,
        agent=disk_check_agent,
        working_dir="./scheduler_workspace",
        policy=Policy(memory_mb=128)
    )
    
    print("--- Scheduler active (Memory Leak Protection Enabled) ---")
    
    try:
        # Monitor the rolling buffer for a few cycles
        for _ in range(3):
            await asyncio.sleep(15)
            tasks = scheduler.list_tasks()
            for t in tasks:
                results_count = len(t.results)
                print(f"Task {t.task_id} has {results_count} historical results in buffer (Max: 10).")
    finally:
        print("\nStopping scheduler...")
        await scheduler.stop()

if __name__ == "__main__":
    asyncio.run(main())
