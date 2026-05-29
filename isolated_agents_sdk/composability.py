"""Composability engine for the Isolated Agents SDK.

Provides high-level utilities for chaining, parallelizing, and nesting agents.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Callable
from typing import Any, Dict, List, Optional, TypeVar

from isolated_agents_sdk.models import AgentResult

F = TypeVar("F", bound=Callable[..., Any])


def _run_sync(coro):
    """Safely run a coroutine from a synchronous context, even if a loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if loop.is_running():
        # Running inside another event loop (e.g. Jupyter, another async task).
        # We must offload to a thread to run a new event loop.
        import threading
        from concurrent.futures import Future

        def target():
            try:
                # Use asyncio.run which creates its own loop
                res = asyncio.run(coro)
                fut.set_result(res)
            except Exception as e:
                fut.set_exception(e)

        fut = Future()
        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join()
        return fut.result()
    else:
        return loop.run_until_complete(coro)


def chain(
    agents: list[Callable],
    data_flow: str = "sequential",
) -> Callable[[F], Callable[..., Any]]:
    """Decorator to compose multiple agents into a sequential pipeline.

    Args:
        agents: Ordered list of agent callables to execute.
        data_flow: How data flows between agents.
            "sequential": The return value of agent N is passed as the first argument to agent N+1.
            "independent": Each agent receives the original arguments.

    Example:
        @chain(agents=[researcher, writer, editor])
        def content_pipeline(topic: str):
            pass
    """

    def decorator(func: F) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> list[AgentResult]:
            results = []
            current_args = args
            current_kwargs = kwargs

            for i, agent in enumerate(agents):
                if i > 0 and data_flow == "sequential":
                    prev_result = results[-1]
                    current_args = (prev_result.output,)
                    current_kwargs = {}

                if inspect.iscoroutinefunction(agent):
                    res = await agent(*current_args, **current_kwargs)
                else:
                    res = agent(*current_args, **current_kwargs)
                results.append(res)

            return results

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> list[AgentResult]:
            # If any agent is async or func was intended to be async, run them loop-safely
            if any(inspect.iscoroutinefunction(a) for a in agents):
                return _run_sync(async_wrapper(*args, **kwargs))

            results = []
            current_args = args
            current_kwargs = kwargs

            for i, agent in enumerate(agents):
                if i > 0 and data_flow == "sequential":
                    prev_result = results[-1]
                    current_args = (prev_result.output,)
                    current_kwargs = {}

                res = agent(*current_args, **current_kwargs)
                results.append(res)

            return results

        # Decide which wrapper to return based on the original function type.
        # If the USER defined 'async def func', they want an async result.
        if inspect.iscoroutinefunction(func):
            return async_wrapper

        # If it's a 'def func', they want a sync call.
        return sync_wrapper

    return decorator


def parallel(
    agents: list[Callable],
    max_concurrent: int | None = None,
) -> Callable[[F], Callable[..., Any]]:
    """Decorator to execute multiple agents concurrently.

    Args:
        agents: List of agent callables to execute in parallel.
        max_concurrent: Maximum number of concurrent agents (None for unlimited).
    """

    def decorator(func: F) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> list[AgentResult]:
            if max_concurrent:
                semaphore = asyncio.Semaphore(max_concurrent)

                async def sem_agent(a):
                    async with semaphore:
                        if inspect.iscoroutinefunction(a):
                            return await a(*args, **kwargs)
                        return a(*args, **kwargs)

                tasks = [sem_agent(agent) for agent in agents]
            else:

                async def maybe_async(a):
                    if inspect.iscoroutinefunction(a):
                        return await a(*args, **kwargs)
                    return a(*args, **kwargs)

                tasks = [maybe_async(agent) for agent in agents]

            return await asyncio.gather(*tasks)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> list[AgentResult]:
            return _run_sync(async_wrapper(*args, **kwargs))

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class StateGraph:
    """Graph-based multi-agent orchestrator.

    Allows defining nodes (agents) and transitions (edges) and maintains
    a shared state across the execution.
    """

    def __init__(self, state_schema: Any = None):
        self.nodes: dict[str, Callable] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, tuple[Callable, dict[str, str]]] = {}
        self.entry_point: str | None = None
        self.finish_node = "__END__"
        self.state_schema = state_schema

    def add_node(self, name: str, agent: Callable) -> None:
        """Add a named node (agent) to the graph."""
        self.nodes[name] = agent

    def add_edge(self, start: str, end: str) -> None:
        """Add a direct transition between two nodes."""
        self.edges[start] = end

    def add_conditional_edges(self, start: str, router: Callable, mapping: dict[str, str]) -> None:
        """Add a conditional transition based on a router function."""
        self.conditional_edges[start] = (router, mapping)

    def set_entry_point(self, name: str) -> None:
        """Set the starting node for graph execution."""
        self.entry_point = name

    def compile(self, max_steps: int = 50) -> Callable[..., Any]:
        """Compiles the graph into a runnable async function.

        Args:
            max_steps: Maximum number of node transitions before failing (default 50).
        """
        if not self.entry_point:
            raise ValueError("Entry point not set for graph.")

        async def runnable(initial_state: Any = None, **kwargs: Any) -> dict[str, Any]:
            current_state = initial_state or {}
            if not isinstance(current_state, dict):
                current_state = {"input": current_state}

            # Mix in extra kwargs into state
            current_state.update(kwargs)

            current_node = self.entry_point
            steps = 0

            while current_node and current_node != self.finish_node:
                if steps >= max_steps:
                    raise RuntimeError(
                        f"StateGraph exceeded max_steps ({max_steps}). "
                        "Possible infinite loop or complex graph without enough steps."
                    )
                steps += 1

                agent = self.nodes[current_node]

                # 1. Execute the agent node
                if inspect.iscoroutinefunction(agent):
                    res = await agent(current_state)
                else:
                    res = agent(current_state)

                # 2. Update state from result
                if isinstance(res, AgentResult):
                    # If AgentResult, we prefer the 'output' field if it is a dict
                    if isinstance(res.output, dict):
                        current_state.update(res.output)
                    else:
                        current_state[f"{current_node}_output"] = res.output
                elif isinstance(res, dict):
                    current_state.update(res)
                else:
                    current_state[f"{current_node}_result"] = res

                # 3. Determine next node
                if current_node in self.conditional_edges:
                    router, mapping = self.conditional_edges[current_node]
                    decision = router(current_state)
                    current_node = mapping.get(str(decision), self.finish_node)
                elif current_node in self.edges:
                    current_node = self.edges[current_node]
                else:
                    current_node = self.finish_node

            return current_state

        return runnable
