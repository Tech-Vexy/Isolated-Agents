"""Decorators for the Isolated Agents SDK.

Provides a Pythonic API for defining and running isolated agents via decorators.
"""

from __future__ import annotations

import functools
import inspect
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Union, cast

from isolated_agents_sdk.models import Policy, NetworkPolicy

# Type variable for the decorated agent function
F = TypeVar("F", bound=Callable[..., Any])

def isolated_agent(
    working_dir: str | Path,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str | Path] = None,
    async_mode: bool = False,
) -> Callable[[F], Union[F, Callable[..., Any]]]:
    """Decorator to run a function in an isolated container.

    Args:
        working_dir: Host path to the working directory.
        policy: Optional :class:`Policy`.
        host_output_path: Optional host path where artifacts are saved.
        async_mode: If True, the decorated function becomes an async function.
    """
    def decorator(func: F) -> Union[F, Callable[..., Any]]:
        # Check if we should override policy from other decorators
        effective_policy = policy or getattr(func, "_isolated_agent_policy", Policy())

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            from isolated_agents_sdk import async_run_agent
            return await async_run_agent(
                agent=func,
                working_dir=working_dir,
                policy=effective_policy,
                host_output_path=host_output_path,
                agent_args=args,
                agent_kwargs=kwargs,
            )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            from isolated_agents_sdk import run_agent
            return run_agent(
                agent=func,
                working_dir=working_dir,
                policy=effective_policy,
                host_output_path=host_output_path,
                agent_args=args,
                agent_kwargs=kwargs,
            )

        return cast(F, async_wrapper if async_mode or inspect.iscoroutinefunction(func) else sync_wrapper)

    return decorator

def policy(**kwargs: Any) -> Callable[[F], F]:
    """Decorator to set policy fields on an agent function.

    Example:
        @isolated_agent(working_dir="./workspace")
        @policy(memory_mb=1024, cpu_cores=2.0)
        def my_agent():
            pass
    """
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        # Apply kwargs to policy
        for k, v in kwargs.items():
            if hasattr(func._isolated_agent_policy, k):
                setattr(func._isolated_agent_policy, k, v)
        
        return func
    return decorator

def network(
    enabled: bool = True,
    allowed_endpoints: Optional[list[str]] = None,
    websockets: bool = False,
    grpc: bool = False,
) -> Callable[[F], F]:
    """Decorator to set network policy on an agent function.

    Example:
        @isolated_agent(working_dir="./workspace")
        @network(enabled=True, allowed_endpoints=["api.openai.com:443"], websockets=True)
        def my_agent():
            pass
    """
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.network = NetworkPolicy(
            disabled=not enabled,
            allowed_endpoints=allowed_endpoints or [],
            websockets=websockets,
            grpc=grpc
        )
        return func
    return decorator

def resources(
    cpu_cores: Optional[float] = None,
    memory_mb: Optional[int] = None,
) -> Callable[[F], F]:
    """Decorator to set resource limits on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        if cpu_cores is not None:
            func._isolated_agent_policy.cpu_cores = cpu_cores
        if memory_mb is not None:
            func._isolated_agent_policy.memory_mb = memory_mb
        return func
    return decorator

def dependencies(packages: list[str]) -> Callable[[F], F]:
    """Decorator to set pip dependencies on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.pip_packages = packages
        return func
    return decorator

def env_vars(vars: dict[str, str]) -> Callable[[F], F]:
    """Decorator to set explicit environment variables on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.env_vars.update(vars)
        return func
    return decorator

def forward_env(vars: list[str]) -> Callable[[F], F]:
    """Decorator to forward host environment variables to an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        for var in vars:
            if var not in func._isolated_agent_policy.allowed_env_vars:
                func._isolated_agent_policy.allowed_env_vars.append(var)
        return func
    return decorator

def timeout(seconds: int) -> Callable[[F], F]:
    """Decorator to set execution timeout on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.timeout_seconds = seconds
        return func
    return decorator

def telemetry(enabled: bool = True) -> Callable[[F], F]:
    """Decorator to enable real-time telemetry on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.enable_telemetry = enabled
        return func
    return decorator

def interactive(enabled: bool = True) -> Callable[[F], F]:
    """Decorator to enable interactive mode on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.interactive = enabled
        return func
    return decorator

def retry(count: int = 3, delay_seconds: int = 1) -> Callable[[F], F]:
    """Decorator to set retry policy on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.retry_count = count
        func._isolated_agent_policy.retry_delay_seconds = delay_seconds
        return func
    return decorator

def cache(duration_seconds: int = 3600) -> Callable[[F], F]:
    """Decorator to enable result caching on an agent function."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.cache_duration_seconds = duration_seconds
        return func
    return decorator

def structured_output(schema: dict[str, Any]) -> Callable[[F], F]:
    """Decorator to enforce a structured output schema on an agent's return value."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.structured_output = schema
        return func
    return decorator

# ---------------------------------------------------------------------------
# Framework & Runtime Decorators
# ---------------------------------------------------------------------------

def base_image(image: str) -> Callable[[F], F]:
    """Decorator to set the base container image for the agent."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        func._isolated_agent_policy.base_image = image
        return func
    return decorator

def entrypoint(command: list[str]) -> Callable[[F], F]:
    """Decorator to set a custom entrypoint (bypasses Python serialization)."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        func._isolated_agent_policy.entrypoint = command
        return func
    return decorator

def langchain(packages: Optional[list[str]] = None) -> Callable[[F], F]:
    """Decorator to pre-configure an agent for LangChain.
    
    Adds 'langchain' and 'langchain-openai' to dependencies by default.
    """
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        deps = packages or ["langchain", "langchain-openai"]
        current_deps = func._isolated_agent_policy.pip_packages or []
        func._isolated_agent_policy.pip_packages = list(set(current_deps + deps))
        
        # LangChain often needs high memory
        if func._isolated_agent_policy.memory_mb < 1024:
            func._isolated_agent_policy.memory_mb = 1024
            
        return func
    return decorator

def crewai() -> Callable[[F], F]:
    """Decorator to pre-configure an agent for CrewAI."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        deps = ["crewai"]
        current_deps = func._isolated_agent_policy.pip_packages or []
        func._isolated_agent_policy.pip_packages = list(set(current_deps + deps))
        
        # CrewAI often needs many subprocesses/threads
        if func._isolated_agent_policy.cpu_cores < 2.0:
            func._isolated_agent_policy.cpu_cores = 2.0
            
        return func
    return decorator

def node(version: str = "lts") -> Callable[[F], F]:
    """Decorator to set up a Node.js environment."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        func._isolated_agent_policy.base_image = f"node:{version}-alpine"
        return func
    return decorator

def llamaindex() -> Callable[[F], F]:
    """Decorator to pre-configure an agent for LlamaIndex."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        deps = ["llama-index"]
        current_deps = func._isolated_agent_policy.pip_packages or []
        func._isolated_agent_policy.pip_packages = list(set(current_deps + deps))
        
        if func._isolated_agent_policy.memory_mb < 2048:
            func._isolated_agent_policy.memory_mb = 2048
            
        return func
    return decorator

def selenium() -> Callable[[F], F]:
    """Decorator to pre-configure an agent for Selenium/Browser-based tasks."""
    def decorator(func: F) -> F:
        if not hasattr(func, "_isolated_agent_policy"):
            func._isolated_agent_policy = Policy()
        
        deps = ["selenium", "webdriver-manager"]
        current_deps = func._isolated_agent_policy.pip_packages or []
        func._isolated_agent_policy.pip_packages = list(set(current_deps + deps))
        
        func._isolated_agent_policy.requires_display = True
        
        if func._isolated_agent_policy.memory_mb < 2048:
            func._isolated_agent_policy.memory_mb = 2048
            
        return func
    return decorator
