"""Isolated Agents SDK — Public API.

Securely run AI agents in rootless containers with advanced telemetry,
structured output validation, and framework-agnostic support.

Main Functions:
  - run_agent()        — Synchronous execution, blocks until agent completion.
  - async_run_agent()  — Asynchronous execution using asyncio.
  - list_sessions()    — Retrieve all currently active agent sessions.

Decorators:
  - @isolated_agent    — Run a function as an isolated agent.
  - @policy, @network  — Configure environment and sandbox constraints.
  - @resources, @retry — Manage resource limits and resilience.
  - @langchain, @crewai — Pre-configure for specific agent frameworks.
  - @structured_output — Enforce JSON Schema validation on return values.

Telemetry & Adapters:
  - configure_adapters() — Configure custom container, storage, or audit backends.
  - get_adapter_registry() — Access initialized adapter instances.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union

from isolated_agents_sdk.agent_runner import AgentRunner
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.container_provisioner import ContainerHandle, ContainerProvisioner
from isolated_agents_sdk.exceptions import (
    ContainerError,
    OutputSizeLimitError,
    PodmanNotFoundError,
    PolicyValidationError,
    WorkingDirectoryError,
)
from isolated_agents_sdk.logging import setup_logging
from isolated_agents_sdk.models import (
    AgentResult,
    AuditEvent,
    NetworkPolicy,
    Policy,
    SessionInfo,
    SessionMetrics,
)
from isolated_agents_sdk.output_collector import OutputCollector
from isolated_agents_sdk.policy_validator import PolicyValidator
from isolated_agents_sdk.runtime import AgentRuntime
from isolated_agents_sdk.scheduler import AgentScheduler, ScheduledTask
from isolated_agents_sdk.session_manager import IsolatedSession, SessionManager

# Initialize default logging on import
setup_logging()

# Import decorators
# Simplified Agent API
from isolated_agents_sdk.agent import Agent
from isolated_agents_sdk.agent import agent as agent_decorator

# Composability API
from isolated_agents_sdk.composability import StateGraph, chain, parallel
from isolated_agents_sdk.decorators import (
    base_image,
    cache,
    crewai,
    dependencies,
    entrypoint,
    env_vars,
    forward_env,
    interactive,
    isolated_agent,
    langchain,
    llamaindex,
    network,
    node,
    policy,
    resources,
    retry,
    selenium,
    structured_output,
    telemetry,
    timeout,
)

# Sub-Agent API (for use within agents)
from isolated_agents_sdk.sub_agent_client import spawn_sub_agent

# Adapter support (optional, backward compatible)
try:
    from isolated_agents_sdk.adapters import (
        AdapterConfig,
        AdapterRegistry,
        get_registry,
    )

    _ADAPTERS_AVAILABLE = True
    _get_registry = get_registry
    _AdapterConfig = AdapterConfig
except ImportError:
    _ADAPTERS_AVAILABLE = False
    _get_registry = None  # type: ignore
    _AdapterConfig = None  # type: ignore
    AdapterRegistry = None  # type: ignore

# ---------------------------------------------------------------------------
# Module-level singletons — shared across all calls in the same process
# ---------------------------------------------------------------------------

_session_manager = SessionManager()
_policy_validator = PolicyValidator()
_adapter_config_applied = False


# ---------------------------------------------------------------------------
# Adapter Configuration API
# ---------------------------------------------------------------------------


def configure_adapters(
    config: dict[str, Any] | None = None,
    config_file: str | Path | None = None,
    from_env: bool = False,
) -> None:
    """Configure adapters for the SDK (optional, backward compatible).

    This function allows you to configure custom adapters for container runtime,
    storage, audit logging, and policy validation. If not called, the SDK uses
    default implementations (Podman, local filesystem, file-based audit, schema validation).

    Args:
        config: Dictionary with adapter configuration. Example:
            {
                "container": {"type": "podman", "config": {...}},
                "storage": {"type": "local", "config": {...}},
                "audit": {"type": "file", "config": {...}},
                "policy": {"type": "default", "config": {...}},
                "database_adapters": {
                    "main_db": {"type": "sql", "url": "sqlite:///:memory:"}
                }
            }
        config_file: Path to YAML or JSON configuration file
        from_env: Load configuration from environment variables (ISOLATED_AGENTS_*)

    Raises:
        ImportError: If adapter support is not available
        ValueError: If configuration is invalid

    Example:
        >>> configure_adapters(config={
        ...     "container": {"type": "podman"},
        ...     "storage": {"type": "local"}
        ... })
    """
    global _adapter_config_applied

    if not _ADAPTERS_AVAILABLE or _get_registry is None or _AdapterConfig is None:
        raise ImportError(
            "Adapter support is not available. "
            "Ensure isolated_agents_sdk.adapters package is installed."
        )

    registry = _get_registry()

    # Load configuration
    if config_file:
        adapter_config = _AdapterConfig.from_file(str(config_file))
    elif from_env:
        adapter_config = _AdapterConfig.from_env()
    elif config:
        adapter_config = _AdapterConfig.from_dict(config)
    else:
        raise ValueError("Must provide config, config_file, or from_env=True")

    # Initialize adapters in registry
    registry.initialize_from_config(adapter_config)
    _adapter_config_applied = True


def get_adapter_registry() -> Any | None:
    """Get the global adapter registry (if adapters are available).

    Returns:
        AdapterRegistry instance or None if adapters not available

    Example:
        >>> registry = get_adapter_registry()
        >>> if registry:
        ...     container_adapter = registry.get_container_adapter()
    """
    if not _ADAPTERS_AVAILABLE or _get_registry is None:
        return None
    return _get_registry()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_agent(
    agent: Callable | None,
    working_dir: str | Path,
    policy: Policy | None = None,
    host_output_path: str | Path | None = None,
    adapter_config: dict[str, Any] | None = None,
    agent_args: tuple = (),
    agent_kwargs: dict[str, Any] | None = None,
    spawn_socket_path: str | None = None,
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
) -> AgentResult:
    """Launch *agent* in an isolated rootless Podman container and block until completion.

    Args:
        agent: Any callable to execute inside the container (ignored if policy.entrypoint is set).
        working_dir: Host path to the working directory to mount into the container.
        policy: Optional :class:`Policy` describing resource/network/fs constraints.
            Defaults are applied when ``None`` is passed.
        host_output_path: Optional host directory where output artifacts are written
            and persist after this call returns.  When ``None``, a temporary directory
            is used — artifacts are still returned as in-memory bytes in
            ``AgentResult.artifacts``, but no files are kept on disk.
        adapter_config: Optional adapter configuration for this specific run.
            If provided, temporarily configures adapters for this execution only.
        agent_args: Positional arguments to pass to the *agent* callable.
        agent_kwargs: Keyword arguments to pass to the *agent* callable.

    Returns:
        An :class:`AgentResult` with the agent's exit code and any output artifacts.

    Raises:
        PodmanNotFoundError: If Podman is not installed or not on PATH.
        PolicyValidationError: If the policy contains unknown or invalid fields.
        WorkingDirectoryError: If *working_dir* does not exist.
        OutputSizeLimitError: If output exceeds the policy's ``max_output_bytes`` limit.
        RuntimeError: If called from within a running asyncio event loop.  Use
            ``await async_run_agent(...)`` instead in that context.

    Example:
        >>> # Basic usage (uses default adapters)
        >>> result = run_agent(my_agent, "./workspace")

        >>> # With custom adapter configuration
        >>> result = run_agent(
        ...     my_agent,
        ...     "./workspace",
        ...     adapter_config={
        ...         "container": {"type": "podman"},
        ...         "storage": {"type": "local"}
        ...     }
        ... )
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        raise RuntimeError(
            "run_agent() cannot be called from within a running asyncio event loop "
            "(e.g. inside an async function, Jupyter notebook, or async framework). "
            "Use 'await async_run_agent(...)' instead."
        )

    return asyncio.run(
        async_run_agent(
            agent,
            working_dir,
            policy,
            host_output_path,
            adapter_config,
            agent_args,
            agent_kwargs,
            spawn_socket_path,
            on_stdout,
            on_stderr,
        )
    )


async def async_run_agent(
    agent: Callable | None,
    working_dir: str | Path,
    policy: Policy | None = None,
    host_output_path: str | Path | None = None,
    adapter_config: dict[str, Any] | None = None,
    agent_args: tuple = (),
    agent_kwargs: dict[str, Any] | None = None,
    agent_payload_hex: str | None = None,
    spawn_socket_path: str | None = None,
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
    audit_logger: AuditLogger | None = None,
    session_id: str | None = None,
    parent_session_id: str | None = None,
) -> AgentResult:
    """Launch *agent* in an isolated container asynchronously."""
    if adapter_config and _ADAPTERS_AVAILABLE:
        # Per-call config used to override globals only when no global registry
        # has been initialized — avoids racing concurrent callers who would
        # otherwise overwrite each other's adapter selections.
        if not _adapter_config_applied:
            configure_adapters(config=adapter_config)

    registry = get_adapter_registry() if _ADAPTERS_AVAILABLE else None
    container_adapter = registry.get_container_adapter() if registry else None
    # If host_output_path is provided, we'll let OutputCollector create a local adapter for it
    storage_adapter = (
        registry.get_storage_adapter() if (registry and not host_output_path) else None
    )

    validated_policy = await _policy_validator.validate(policy)

    # Advanced Logging: Setup audit logger with telemetry if enabled
    if audit_logger:
        pass  # use the passed in logger
    elif validated_policy.enable_telemetry and _ADAPTERS_AVAILABLE:
        from isolated_agents_sdk.adapters.audit.composite import CompositeAuditAdapter
        from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
        from isolated_agents_sdk.adapters.audit.telemetry import TelemetryAuditAdapter

        adapters = [TelemetryAuditAdapter()]
        if validated_policy.log_output_path:
            adapters.append(FileAuditAdapter(log_file=validated_policy.log_output_path))

        audit_logger = AuditLogger(adapter=CompositeAuditAdapter(adapters))
    else:
        audit_logger = AuditLogger(log_output_path=validated_policy.log_output_path)

    if not session_id:
        session_id = str(uuid.uuid4())

    # Handle Sub-Agent Spawn Socket if enabled but no path provided (Host-initiated)
    if validated_policy.allow_sub_agents and not spawn_socket_path:
        from isolated_agents_sdk.runtime import get_runtime_async

        runtime = await get_runtime_async(working_dir=working_dir)
        if not runtime._is_running:
            await runtime.start()
        spawn_socket_path = await runtime._create_session_socket(session_id)

    if validated_policy.entrypoint:
        agent_id = " ".join(validated_policy.entrypoint[:2])
    else:
        agent_id = getattr(agent, "__name__", "agent")

    # Log session creation for telemetry
    await audit_logger.log_event(
        event_type="session_created",
        session_id=session_id,
        agent_id=agent_id,
        payload={
            "runtime": container_adapter.get_adapter_name() if container_adapter else "Podman",
            "storage": "Local Filesystem",
            "logger": "Composite" if validated_policy.enable_telemetry else "File",
        },
    )

    # Log policy details for telemetry
    await audit_logger.log_event(
        event_type="policy_validated",
        session_id=session_id,
        agent_id=agent_id,
        payload={
            "cpu_cores": validated_policy.cpu_cores,
            "memory_mb": validated_policy.memory_mb,
            "network_enabled": not validated_policy.network.disabled,
            "timeout_seconds": validated_policy.timeout_seconds,
        },
    )

    provisioner = ContainerProvisioner(adapter=container_adapter, audit_logger=audit_logger)
    handle = await provisioner.provision(
        working_dir=working_dir,
        policy=validated_policy,
        session_id=session_id,
        agent_id=agent_id,
        spawn_socket_path=spawn_socket_path,
    )

    runner = AgentRunner(handle=handle, adapter=container_adapter, audit_logger=audit_logger)

    # Update global session manager with current adapter if needed
    if container_adapter:
        _session_manager._adapter = container_adapter

    # Register the session so cleanup handlers are in place before execution
    _session_manager.register_session(
        session_id=session_id,
        container_id=handle.container_id,
        agent_id=agent_id,
        process=None,
        policy=validated_policy,
        audit_logger=audit_logger,
        parent_session_id=parent_session_id,
    )

    exit_code = 1
    result: AgentResult | None = None
    run_error: str | None = "Execution failed during setup"
    try:
        run_result = await runner.run(
            agent=agent,
            policy=validated_policy,
            session_id=session_id,
            agent_id=agent_id,
            agent_args=agent_args,
            agent_kwargs=agent_kwargs,
            agent_payload_hex=agent_payload_hex,
            spawn_socket_path=spawn_socket_path,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
        )
        exit_code = run_result.exit_code
        run_error = run_result.error

        # Collect output artifacts from the container.
        collector = OutputCollector(
            container_adapter=container_adapter,
            storage_adapter=storage_adapter,
            audit_logger=audit_logger,
        )

        # If host_output_path is not provided, create a temporary directory
        effective_host_output_path = host_output_path
        if effective_host_output_path is None:
            effective_host_output_path = tempfile.mkdtemp(prefix="agent_output_")

        result = await collector.collect(
            container_id=handle.container_id,
            policy=validated_policy,
            host_output_path=effective_host_output_path,
            exit_code=exit_code,
            session_id=session_id,
            agent_id=agent_id,
            error=run_error,
        )
    finally:
        await _session_manager.complete_session(session_id, exit_code, error=run_error)

    return result  # type: ignore[return-value]


def list_sessions() -> list[SessionInfo]:
    """Return all currently active sessions and their associated container identifiers.

    Returns:
        A list of :class:`SessionInfo` objects, one per active session.
    """
    return _session_manager.list_sessions()


async def get_session_metrics(session_id: str) -> SessionMetrics:
    """Return CPU and memory usage metrics for an active session.

    Args:
        session_id: The session to query.

    Returns:
        A :class:`SessionMetrics` with ``cpu_percent`` and ``memory_mb``.

    Raises:
        KeyError: If *session_id* is not found in the active registry.
    """
    return await _session_manager.get_session_metrics(session_id)


async def exec_in_session(
    session_id: str,
    command: list[str],
) -> tuple[int, str, str]:
    """Execute a command inside an existing, isolated container.

    Args:
        session_id: The active session ID.
        command: The command list to execute.

    Returns:
        A tuple of (exit_code, stdout, stderr).
    """
    return await _session_manager.exec_in_session(session_id, command)


async def sync_artifact(
    session_id: str,
    container_path: str,
    host_path: str | Path,
) -> None:
    """Copy a specific file from a running agent's workspace to the host.

    Args:
        session_id: The active session ID.
        container_path: Path to the file inside the container.
        host_path: Destination path on the host.
    """
    await _session_manager.sync_artifact(session_id, container_path, host_path)


# ---------------------------------------------------------------------------
# Scheduling API
# ---------------------------------------------------------------------------

_agent_scheduler = AgentScheduler(async_run_agent)


async def start_scheduler() -> None:
    """Start the background agent scheduler.

    Must be called within an active asyncio event loop.
    """
    await _agent_scheduler.start()


async def stop_scheduler() -> None:
    """Stop the background agent scheduler."""
    await _agent_scheduler.stop()


def schedule_agent_in(
    delay: int | float | timedelta,
    agent: Callable | None,
    working_dir: str | Path,
    policy: Policy | None = None,
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
) -> str:
    """Schedule an agent to run after a delay.

    Args:
        delay: Delay in seconds or timedelta.
        agent: Agent callable or None (if entrypoint in policy).
        working_dir: Path to the agent workspace.
        policy: Optional execution policy.
        args/kwargs: Agent arguments.

    Returns:
        Task ID string.
    """
    return _agent_scheduler.schedule_in(
        delay=delay,
        agent=agent,
        working_dir=str(working_dir),
        policy=policy,
        args=args,
        kwargs=kwargs,
    )


def schedule_agent_at(
    run_at: datetime,
    agent: Callable | None,
    working_dir: str | Path,
    policy: Policy | None = None,
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
) -> str:
    """Schedule an agent to run at a specific UTC time."""
    return _agent_scheduler.schedule_at(
        run_at=run_at,
        agent=agent,
        working_dir=str(working_dir),
        policy=policy,
        args=args,
        kwargs=kwargs,
    )


def schedule_agent_interval(
    interval: int | float | timedelta,
    agent: Callable | None,
    working_dir: str | Path,
    policy: Policy | None = None,
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
    start_at: datetime | None = None,
) -> str:
    """Schedule an agent to run repeatedly at fixed intervals."""
    return _agent_scheduler.schedule_interval(
        interval=interval,
        agent=agent,
        working_dir=str(working_dir),
        policy=policy,
        args=args,
        kwargs=kwargs,
        start_at=start_at,
    )


def cancel_scheduled_agent(task_id: str) -> bool:
    """Cancel a pending or recurring scheduled agent task."""
    return _agent_scheduler.cancel(task_id)


def list_scheduled_agents() -> list[ScheduledTask]:
    """Return all currently scheduled and completed tasks."""
    return _agent_scheduler.list_tasks()


async def start_agent_daemon(
    agent: Callable | None,
    working_dir: str | Path,
    policy: Policy | None = None,
    spawn_socket_path: str | None = None,
) -> SessionInfo:
    """Start an agent in the background and return a handle immediately.

    Args:
        agent: Any callable to execute inside the container (ignored if policy.entrypoint is set).
        working_dir: Host path to the working directory.
        policy: Optional :class:`Policy`.
        spawn_socket_path: Optional path to the host-side spawn socket.
    """
    validated_policy = await _policy_validator.validate(policy)

    # Advanced Logging: Setup audit logger with telemetry if enabled
    if validated_policy.enable_telemetry and _ADAPTERS_AVAILABLE:
        from isolated_agents_sdk.adapters.audit.composite import CompositeAuditAdapter
        from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
        from isolated_agents_sdk.adapters.audit.telemetry import TelemetryAuditAdapter

        adapters = [TelemetryAuditAdapter()]
        if validated_policy.log_output_path:
            adapters.append(FileAuditAdapter(log_file=validated_policy.log_output_path))

        audit_logger = AuditLogger(adapter=CompositeAuditAdapter(adapters))
    else:
        audit_logger = AuditLogger(log_output_path=validated_policy.log_output_path)

    session_id = str(uuid.uuid4())
    if validated_policy.entrypoint:
        agent_id = " ".join(validated_policy.entrypoint[:2])
    else:
        agent_id = getattr(agent, "__name__", "agent")

    provisioner = ContainerProvisioner(audit_logger=audit_logger)
    handle = await provisioner.provision(
        working_dir=working_dir,
        policy=validated_policy,
        session_id=session_id,
        agent_id=agent_id,
        spawn_socket_path=spawn_socket_path,
    )

    # Register the session
    _session_manager.register_session(
        session_id=session_id,
        container_id=handle.container_id,
        agent_id=agent_id,
        process=None,
        policy=validated_policy,
    )

    # Launch the agent in the background
    async def _background_runner():
        runner = AgentRunner(handle=handle, audit_logger=audit_logger)
        exit_code = 1
        try:
            run_result = await runner.run(
                agent=agent,
                policy=validated_policy,
                session_id=session_id,
                agent_id=agent_id,
            )
            exit_code = run_result.exit_code
        finally:
            await _session_manager.complete_session(session_id, exit_code)

    asyncio.create_task(_background_runner())

    # Return the session info immediately
    sessions = _session_manager.list_sessions()
    for s in sessions:
        if s.session_id == session_id:
            return s

    raise RuntimeError("Failed to retrieve session info after registration.")


__all__ = [
    # Entry-point functions
    "run_agent",
    "async_run_agent",
    "start_agent_daemon",
    # Simplified Agent API
    "Agent",
    "agent_decorator",
    # Decorators
    "isolated_agent",
    "policy",
    "network",
    "resources",
    "dependencies",
    "env_vars",
    "forward_env",
    "timeout",
    "telemetry",
    "interactive",
    "list_sessions",
    "get_session_metrics",
    "exec_in_session",
    "sync_artifact",
    # Adapter configuration (optional)
    "configure_adapters",
    "get_adapter_registry",
    # Models
    "NetworkPolicy",
    "Policy",
    "AgentResult",
    "SessionInfo",
    "SessionMetrics",
    "AuditEvent",
    # Exceptions
    "IsolatedAgentsError",
    "PodmanNotFoundError",
    "PolicyValidationError",
    "WorkingDirectoryError",
    "OutputSizeLimitError",
    "ContainerError",
    "NetworkAccessDeniedError",
    "PackageInstallationError",
    "ResourceLimitExceededError",
    "AgentImportError",
    # Components (for advanced use)
    "PolicyValidator",
    "AuditLogger",
    "ContainerProvisioner",
    "ContainerHandle",
    "AgentRunner",
    "OutputCollector",
    "SessionManager",
    "IsolatedSession",
]
