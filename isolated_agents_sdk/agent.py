"""Simplified Agent API for easier usage.

This module provides a more intuitive, fluent API for running isolated agents
while maintaining backward compatibility with the existing run_agent() function.

Workspace Management:
    The workspace directory contains both input files and output subdirectory:

    workspace/
    ├── input_files/      # Your input data
    ├── config.json       # Configuration files
    └── output/           # Agent output (auto-created)

    Inside the container:
    - /workspace → mounted from host workspace directory
    - /workspace/output → where agents write results

Example:
    >>> from isolated_agents_sdk import Agent
    >>>
    >>> def my_agent():
    ...     from pathlib import Path
    ...     # Write to /workspace/output (auto-created)
    ...     Path("/workspace/output/result.txt").write_text("Success!")
    >>>
    >>> # Simple usage - output goes to workspace/output
    >>> agent = Agent(my_agent, workspace="./workspace")
    >>> result = agent.run()
    >>>
    >>> # Fluent API
    >>> result = (Agent(my_agent)
    ...     .with_workspace("./workspace")
    ...     .with_network(allowed=["api.example.com:443"])
    ...     .with_packages(["requests", "pandas"])
    ...     .with_env("API_KEY")
    ...     .with_memory(2048)
    ...     .with_timeout(300)
    ...     .run())
    >>>
    >>> # Context manager
    >>> with Agent(my_agent, workspace="./workspace") as agent:
    ...     result = agent.run()
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from isolated_agents_sdk.models import AgentResult, NetworkPolicy, Policy

# Import config support (optional)
try:
    from isolated_agents_sdk.config import AgentConfig, Config, load_config

    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False
    Config = None  # type: ignore
    AgentConfig = None  # type: ignore
    load_config = None  # type: ignore


class Agent:
    """Simplified agent wrapper with fluent API.

    This class provides a more intuitive interface for running isolated agents
    with sensible defaults and a chainable configuration API.

    Args:
        func: The agent function to execute in isolation
        workspace: Path to the working directory (optional, can be set later)
        output: Path to the output directory (optional, can be set later)
        **kwargs: Additional configuration options

    Example:
        >>> def my_agent():
        ...     from pathlib import Path
        ...     Path("/output/result.txt").write_text("Success!")
        >>>
        >>> agent = Agent(my_agent, workspace="./workspace")
        >>> result = agent.run()
        >>> print(result.exit_code)
        0
    """

    def __init__(self, func: Callable, workspace: str | Path | None = None, **kwargs):
        self.func = func
        self._workspace = Path(workspace) if workspace else None

        # Policy configuration
        self._cpu_cores: float = 1.0
        self._memory_mb: int = 512
        self._timeout_seconds: int | None = None

        # Network configuration
        self._network_enabled: bool = False
        self._allowed_endpoints: list[str] = []

        # Environment variables
        self._env_vars: list[str] = []
        self._env_dict: dict[str, str] = {}

        # Packages
        self._packages: list[str] = []

        # Advanced options
        self._base_image: str = "python:3.11-slim"
        self._entrypoint: list[str] | None = None
        self._interactive: bool = False

        # Apply any kwargs
        for key, value in kwargs.items():
            if hasattr(self, f"with_{key}"):
                getattr(self, f"with_{key}")(value)

    def with_workspace(self, path: str | Path) -> Agent:
        """Set the workspace directory.

        The output will automatically be placed in workspace/output/.

        Args:
            path: Path to the working directory

        Returns:
            Self for chaining
        """
        self._workspace = Path(path)
        return self

    def with_cpu(self, cores: float) -> Agent:
        """Set CPU core limit.

        Args:
            cores: Number of CPU cores (e.g., 2.0 for 2 cores)

        Returns:
            Self for chaining
        """
        self._cpu_cores = cores
        return self

    def with_memory(self, mb: int) -> Agent:
        """Set memory limit in megabytes.

        Args:
            mb: Memory limit in MB (e.g., 2048 for 2GB)

        Returns:
            Self for chaining
        """
        self._memory_mb = mb
        return self

    def with_timeout(self, seconds: int) -> Agent:
        """Set execution timeout.

        Args:
            seconds: Timeout in seconds

        Returns:
            Self for chaining
        """
        self._timeout_seconds = seconds
        return self

    def with_network(self, enabled: bool = True, allowed: list[str] | None = None) -> Agent:
        """Configure network access.

        Args:
            enabled: Whether to enable network access
            allowed: List of allowed endpoints (e.g., ["api.example.com:443"])

        Returns:
            Self for chaining

        Example:
            >>> agent.with_network(allowed=["api.openai.com:443"])
        """
        self._network_enabled = enabled
        if allowed:
            self._allowed_endpoints = allowed
        return self

    def with_env(self, *vars: str, **kwargs: str) -> Agent:
        """Add environment variables.

        Args:
            *vars: Environment variable names to pass through
            **kwargs: Environment variable key-value pairs to set

        Returns:
            Self for chaining

        Example:
            >>> agent.with_env("API_KEY", "SECRET_TOKEN")
            >>> agent.with_env(MY_VAR="value", OTHER_VAR="other")
        """
        self._env_vars.extend(vars)
        self._env_dict.update(kwargs)
        return self

    def with_packages(self, *packages: str) -> Agent:
        """Add pip packages to install.

        Args:
            *packages: Package names (e.g., "requests", "pandas==2.0.0")

        Returns:
            Self for chaining

        Example:
            >>> agent.with_packages("requests", "pandas", "numpy")
        """
        self._packages.extend(packages)
        return self

    def with_base_image(self, image: str) -> Agent:
        """Set the base container image.

        Args:
            image: Docker/Podman image name

        Returns:
            Self for chaining
        """
        self._base_image = image
        return self

    def with_entrypoint(self, *command: str) -> Agent:
        """Set custom entrypoint command.

        Args:
            *command: Command parts (e.g., "python", "-m", "mymodule")

        Returns:
            Self for chaining
        """
        self._entrypoint = list(command)
        return self

    def interactive(self, enabled: bool = True) -> Agent:
        """Enable interactive mode.

        Args:
            enabled: Whether to enable interactive mode

        Returns:
            Self for chaining
        """
        self._interactive = enabled
        return self

    def _build_policy(self) -> Policy:
        """Build Policy object from configuration."""
        network_policy = NetworkPolicy(
            disabled=not self._network_enabled, allowed_endpoints=self._allowed_endpoints
        )

        return Policy(
            cpu_cores=self._cpu_cores,
            memory_mb=self._memory_mb,
            timeout_seconds=self._timeout_seconds,
            network=network_policy,
            allowed_env_vars=self._env_vars,
            env_vars=self._env_dict,
            pip_packages=self._packages,
            base_image=self._base_image,
            entrypoint=self._entrypoint,
            interactive=self._interactive,
        )

    def run(self, workspace: str | Path | None = None, **kwargs) -> AgentResult:
        """Run the agent synchronously.

        Output will be automatically placed in workspace/output/.

        Args:
            workspace: Override workspace path
            **kwargs: Additional arguments passed to the agent function

        Returns:
            AgentResult with exit code and artifacts

        Raises:
            ValueError: If workspace is not set
            RuntimeError: If called from within an async event loop

        Example:
            >>> result = agent.run()
            >>> print(result.exit_code)
            0
        """
        # Import here to avoid circular import
        from isolated_agents_sdk import run_agent

        workspace_path = Path(workspace) if workspace else self._workspace

        if not workspace_path:
            raise ValueError(
                "Workspace path must be set either in constructor or run() call. "
                "Use Agent(func, workspace='./workspace') or agent.run(workspace='./workspace')"
            )

        # Create workspace directory if it doesn't exist
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Output goes to workspace/output
        output_path = workspace_path / "output"
        output_path.mkdir(parents=True, exist_ok=True)

        policy = self._build_policy()

        return run_agent(
            agent=self.func,
            working_dir=workspace_path,
            host_output_path=output_path,
            policy=policy,
            agent_kwargs=kwargs,
        )

    async def run_async(self, workspace: str | Path | None = None, **kwargs) -> AgentResult:
        """Run the agent asynchronously.

        Output will be automatically placed in workspace/output/.

        Args:
            workspace: Override workspace path
            **kwargs: Additional arguments passed to the agent function

        Returns:
            AgentResult with exit code and artifacts

        Raises:
            ValueError: If workspace is not set

        Example:
            >>> result = await agent.run_async()
            >>> print(result.exit_code)
            0
        """
        # Import here to avoid circular import
        from isolated_agents_sdk import async_run_agent

        workspace_path = Path(workspace) if workspace else self._workspace

        if not workspace_path:
            raise ValueError("Workspace path must be set either in constructor or run_async() call")

        # Create workspace directory if it doesn't exist
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Output goes to workspace/output
        output_path = workspace_path / "output"
        output_path.mkdir(parents=True, exist_ok=True)

        policy = self._build_policy()

        return await async_run_agent(
            agent=self.func,
            working_dir=workspace_path,
            host_output_path=output_path,
            policy=policy,
            agent_kwargs=kwargs,
        )

    def __enter__(self) -> Agent:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager (cleanup if needed)."""
        # Future: Add cleanup logic here
        pass

    async def __aenter__(self) -> Agent:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager (cleanup if needed)."""
        # Future: Add cleanup logic here
        pass

    def __repr__(self) -> str:
        """String representation."""
        func_name = getattr(self.func, "__name__", "unknown")
        return (
            f"Agent({func_name}, "
            f"workspace={self._workspace}, "
            f"memory={self._memory_mb}MB, "
            f"network={'enabled' if self._network_enabled else 'disabled'})"
        )

    @classmethod
    def from_config(
        cls,
        config: str | Path | Config,
        agent_name: str,
        func: Callable,
    ) -> Agent:
        """Create Agent from configuration file or Config object.

        Args:
            config: Path to config file or Config object
            agent_name: Name of agent in configuration
            func: Agent function to execute

        Returns:
            Configured Agent instance

        Raises:
            ImportError: If config support not available
            KeyError: If agent not found in config

        Example:
            >>> agent = Agent.from_config(
            ...     "isolated-agents.yaml",
            ...     "data_processor",
            ...     my_agent_func
            ... )
            >>> result = agent.run()
        """
        if not _CONFIG_AVAILABLE:
            raise ImportError(
                "Configuration file support requires PyYAML. Install it with: pip install pyyaml"
            )

        # Load config if path provided
        if isinstance(config, (str, Path)):
            config = load_config(config)

        # Get agent config
        agent_config = config.get_agent(agent_name)

        # Build policy
        policy = agent_config.build_policy(config.default_policy)

        # Create agent with workspace only (output is auto-managed)
        agent = cls(func, workspace=agent_config.workspace)

        # Apply policy settings
        agent._cpu_cores = policy.cpu_cores
        agent._memory_mb = policy.memory_mb
        agent._timeout_seconds = policy.timeout_seconds
        agent._network_enabled = not policy.network.disabled
        agent._allowed_endpoints = policy.network.allowed_endpoints
        agent._env_vars = policy.allowed_env_vars
        agent._env_dict = policy.env_vars
        agent._packages = policy.pip_packages
        agent._base_image = policy.base_image
        agent._entrypoint = policy.entrypoint
        agent._interactive = policy.interactive

        return agent


# Convenience function for quick agent creation
def agent(
    workspace: str | Path,
    network: bool = False,
    packages: list[str] | None = None,
    env_vars: list[str] | None = None,
    memory: int = 512,
    timeout: int | None = None,
) -> Callable[[Callable], Agent]:
    """Decorator to create an Agent from a function.

    Output will automatically be placed in workspace/output/.

    Args:
        workspace: Path to the working directory
        network: Whether to enable network access
        packages: List of pip packages to install
        env_vars: List of environment variables to pass through
        memory: Memory limit in MB
        timeout: Timeout in seconds

    Returns:
        Decorator function

    Example:
        >>> @agent(workspace="./workspace", network=True, packages=["requests"])
        ... def my_agent():
        ...     import requests
        ...     return requests.get("https://api.example.com").json()
        >>>
        >>> result = my_agent.run()
    """

    def decorator(func: Callable) -> Agent:
        a = Agent(func, workspace=workspace)

        if network:
            a.with_network(enabled=True)

        if packages:
            a.with_packages(*packages)

        if env_vars:
            a.with_env(*env_vars)

        a.with_memory(memory)

        if timeout:
            a.with_timeout(timeout)

        return a

    return decorator
