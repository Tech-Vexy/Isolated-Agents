"""Isolated Agents SDK — public API.

Three entry-point functions:
  - run_agent()        — synchronous, blocks until agent completes
  - async_run_agent()  — async variant using asyncio
  - list_sessions()    — returns all currently active sessions

Adapter Support:
  - configure_adapters() — configure adapters from dict, file, or environment
  - get_adapter_registry() — access the global adapter registry
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional, Dict, Any

from isolated_agents_sdk.models import (
    NetworkPolicy,
    Policy,
    AgentResult,
    SessionInfo,
    SessionMetrics,
    AuditEvent,
)
from isolated_agents_sdk.exceptions import (
    PodmanNotFoundError,
    PolicyValidationError,
    WorkingDirectoryError,
    OutputSizeLimitError,
    ContainerError,
)
from isolated_agents_sdk.policy_validator import PolicyValidator
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.container_provisioner import ContainerProvisioner, ContainerHandle
from isolated_agents_sdk.agent_runner import AgentRunner
from isolated_agents_sdk.output_collector import OutputCollector
from isolated_agents_sdk.session_manager import SessionManager, IsolatedSession

# Adapter support (optional, backward compatible)
try:
    from isolated_agents_sdk.adapters import (
        AdapterRegistry,
        AdapterConfig,
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
    config: Optional[Dict[str, Any]] = None,
    config_file: Optional[str | Path] = None,
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
                "policy": {"type": "default", "config": {...}}
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


def get_adapter_registry() -> Optional[Any]:
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
    agent: Optional[Callable],
    working_dir: str | Path,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str | Path] = None,
    adapter_config: Optional[Dict[str, Any]] = None,
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
        async_run_agent(agent, working_dir, policy, host_output_path, adapter_config)
    )


async def async_run_agent(
    agent: Optional[Callable],
    working_dir: str | Path,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str | Path] = None,
    adapter_config: Optional[Dict[str, Any]] = None,
) -> AgentResult:
    """Launch *agent* in an isolated rootless Podman container asynchronously.

    Args:
        agent: Any callable to execute inside the container (ignored if policy.entrypoint is set).
        working_dir: Host path to the working directory to mount into the container.
        policy: Optional :class:`Policy` describing resource/network/fs constraints.
        host_output_path: Optional host directory where output artifacts are written
            and persist after this call returns.
        adapter_config: Optional adapter configuration for this specific run.

    Returns:
        An :class:`AgentResult` with the agent's exit code and any output artifacts.
    
    Example:
        >>> # Basic usage
        >>> result = await async_run_agent(my_agent, "./workspace")
        
        >>> # With adapter configuration
        >>> result = await async_run_agent(
        ...     my_agent,
        ...     "./workspace",
        ...     adapter_config={"container": {"type": "podman"}}
        ... )
    """
    # Apply adapter configuration if provided
    if adapter_config and _ADAPTERS_AVAILABLE:
        configure_adapters(config=adapter_config)
    
    validated_policy = _policy_validator.validate(policy)
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
    )

    runner = AgentRunner(handle=handle, audit_logger=audit_logger)

    # Register the session so cleanup handlers are in place before execution
    _session_manager.register_session(
        session_id=session_id,
        container_id=handle.container_id,
        agent_id=agent_id,
        process=None,  # updated below if needed
        policy=validated_policy,
    )

    exit_code = 1
    result: Optional[AgentResult] = None
    try:
        run_result = await runner.run(
            agent=agent,
            policy=validated_policy,
            session_id=session_id,
            agent_id=agent_id,
        )
        exit_code = run_result.exit_code

        # Collect output artifacts from the container.
        collector = OutputCollector(audit_logger=audit_logger)
        
        # If host_output_path is not provided, create a temporary directory
        # that will PERSIST until the caller cleans it up.
        effective_host_output_path = host_output_path
        if effective_host_output_path is None:
            effective_host_output_path = tempfile.mkdtemp(prefix="agent_output_")

        result = await collector.collect(
            container_id=handle.container_id,
            output_path_in_container=validated_policy.output_path_in_container,
            host_output_path=effective_host_output_path,
            max_output_bytes=validated_policy.max_output_bytes,
            exit_code=exit_code,
            session_id=session_id,
            agent_id=agent_id,
        )
    finally:
        await _session_manager.complete_session(session_id, exit_code)

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


async def start_agent_daemon(
    agent: Optional[Callable],
    working_dir: str | Path,
    policy: Optional[Policy] = None,
) -> SessionInfo:
    """Start an agent in the background and return a handle immediately.

    Args:
        agent: Any callable to execute inside the container (ignored if policy.entrypoint is set).
        working_dir: Host path to the working directory.
        policy: Optional :class:`Policy`.

    Returns:
        A :class:`SessionInfo` object describing the newly created session.
    """
    validated_policy = _policy_validator.validate(policy)
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
    "PodmanNotFoundError",
    "PolicyValidationError",
    "WorkingDirectoryError",
    "OutputSizeLimitError",
    "ContainerError",
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
