"""Scheduler for the Isolated Agents SDK.

Enables scheduling agents to run at specific times or intervals in background tasks.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from isolated_agents_sdk.models import AgentResult, Policy
from isolated_agents_sdk.logging import get_logger

logger = get_logger("scheduler")


class ScheduledTask:
    """Represents an agent task scheduled for execution.
    
    Attributes:
        task_id: Unique identifier for the task.
        agent: The agent callable to execute.
        working_dir: The host path used as workspace for the agent.
        policy: The isolation policy for the task.
        args: Positional arguments for the agent.
        kwargs: Keyword arguments for the agent.
        next_run: Timestamp of the next scheduled execution.
        interval: Time between recurring executions.
        status: Current status ("scheduled", "running", "completed", "cancelled").
    """
    
    def __init__(
        self,
        task_id: str,
        agent: Optional[Callable],
        working_dir: str,
        policy: Optional[Policy] = None,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        run_at: Optional[datetime] = None,
        interval: Optional[timedelta] = None,
    ):
        self.task_id = task_id
        self.agent = agent
        self.working_dir = working_dir
        self.policy = policy
        self.args = args
        self.kwargs = kwargs or {}
        self.interval = interval
        self.status = "scheduled"
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = run_at
        self.results: deque[AgentResult] = deque(maxlen=10)

    def __repr__(self) -> str:
        return f"<ScheduledTask {self.task_id} status={self.status} next={self.next_run}>"


class AgentScheduler:
    """Lightweight background scheduler for isolated agents.
    
    This scheduler runs as an asyncio background task and manages the execution 
    of agents based on their scheduled times and intervals.
    """
    
    def __init__(self, run_agent_coro: Callable, max_concurrent_agents: int = 10):
        """Initialize the scheduler.
        
        Args:
            run_agent_coro: The async function used to run the agent (typically async_run_agent).
            max_concurrent_agents: Maximum number of agents to run simultaneously (default 10).
        """
        self._run_agent_coro = run_agent_coro
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._max_concurrent = max_concurrent_agents
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def start(self) -> None:
        """Start the background scheduler loop.
        
        This must be called within an active asyncio event loop.
        """
        if self._running:
            return
        self._running = True
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"Agent Scheduler started (max_concurrent={self._max_concurrent}).")

    async def stop(self) -> None:
        """Stop the background scheduler loop and cancel all pending tasks."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all scheduled tasks
        for task in self._tasks.values():
            if task.status == "scheduled":
                task.status = "cancelled"
        
        logger.info("Agent Scheduler stopped.")

    def schedule_in(
        self,
        delay: Union[int, float, timedelta],
        agent: Optional[Callable],
        working_dir: str,
        policy: Optional[Policy] = None,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Schedule an agent to run once after a delay.
        
        Args:
            delay: Delay in seconds or as a timedelta.
            agent: The agent function to run.
            working_dir: Path to the workspace for the agent.
            policy: Optional security policy.
            args/kwargs: Arguments for the agent.
            
        Returns:
            The unique task_id for tracking or cancellation.
        """
        if isinstance(delay, (int, float)):
            delay = timedelta(seconds=delay)
        
        run_at = datetime.now(timezone.utc) + delay
        return self.schedule_at(run_at, agent, working_dir, policy, args, kwargs)

    def schedule_at(
        self,
        run_at: datetime,
        agent: Optional[Callable],
        working_dir: str,
        policy: Optional[Policy] = None,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Schedule an agent to run once at a specific UTC time."""
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
            
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            agent=agent,
            working_dir=working_dir,
            policy=policy,
            args=args,
            kwargs=kwargs,
            run_at=run_at
        )
        self._tasks[task_id] = task
        logger.info(f"Task {task_id} scheduled for {run_at}")
        return task_id

    def schedule_interval(
        self,
        interval: Union[int, float, timedelta],
        agent: Optional[Callable],
        working_dir: str,
        policy: Optional[Policy] = None,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        start_at: Optional[datetime] = None,
    ) -> str:
        """Schedule an agent to run repeatedly at a fixed interval.
        
        Args:
            interval: Time between runs (seconds or timedelta).
            agent: The agent function to run.
            working_dir: Path to the workspace for the agent.
            start_at: Optional first run time (defaults to immediately).
        """
        if isinstance(interval, (int, float)):
            interval = timedelta(seconds=interval)
        
        if start_at is None:
            start_at = datetime.now(timezone.utc)
        elif start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
            
        task_id = str(uuid.uuid4())
        task = ScheduledTask(
            task_id=task_id,
            agent=agent,
            working_dir=working_dir,
            policy=policy,
            args=args,
            kwargs=kwargs,
            run_at=start_at,
            interval=interval
        )
        self._tasks[task_id] = task
        logger.info(f"Task {task_id} scheduled every {interval} starting {start_at}")
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task. Returns True if task was cancelled."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            if task.status == "scheduled":
                task.status = "cancelled"
                logger.info(f"Task {task_id} cancelled.")
                return True
        return False

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Retrieve a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self) -> List[ScheduledTask]:
        """List all active and completed scheduled tasks."""
        return list(self._tasks.values())

    async def _scheduler_loop(self) -> None:
        """Main background loop."""
        while self._running:
            now = datetime.now(timezone.utc)
            to_run = []
            
            for task in self._tasks.values():
                if task.status == "scheduled" and task.next_run and task.next_run <= now:
                    to_run.append(task)
            
            for task in to_run:
                # Update task state for the current run
                task.last_run = now
                if task.interval:
                    task.next_run = now + task.interval
                else:
                    task.status = "completed"
                    task.next_run = None
                
                # Execute in background task to avoid blocking the scheduler loop
                asyncio.create_task(self._execute_task(task))
                
            await asyncio.sleep(1)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Single execution handler for a task."""
        if self._semaphore is None:
             self._semaphore = asyncio.Semaphore(self._max_concurrent)

        async with self._semaphore:
            try:
                logger.info(f"Running scheduled task {task.task_id}")
                result = await self._run_agent_coro(
                    task.agent,
                    task.working_dir,
                    policy=task.policy,
                    agent_args=task.args,
                    agent_kwargs=task.kwargs
                )
                task.results.append(result)
                logger.info(f"Task {task.task_id} execution finished.")
            except Exception as e:
                logger.error(f"Error executing scheduled task {task.task_id}: {e}")
