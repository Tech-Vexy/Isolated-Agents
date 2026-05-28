"""Custom exception classes for the Isolated Agents SDK."""

from __future__ import annotations

from typing import Optional


class IsolatedAgentsError(Exception):
    """Base exception for all Isolated Agents SDK errors.

    Attributes:
        message: The error message
        suggestion: Optional suggestion for how to fix the error
    """

    def __init__(self, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.suggestion = suggestion

    def __str__(self) -> str:
        msg = super().__str__()
        if self.suggestion:
            msg += f"\n\n💡 Suggestion: {self.suggestion}"
        return msg


class PodmanNotFoundError(IsolatedAgentsError):
    """Raised when Podman is not installed or not accessible on PATH."""

    def __init__(self, message: str = "Container runtime not found"):
        suggestion = (
            "Install Podman or Docker:\n"
            "  • Linux: sudo apt-get install podman\n"
            "  • macOS: brew install podman\n"
            "  • Windows: choco install podman\n"
            "Then verify with: podman --version"
        )
        super().__init__(message, suggestion=suggestion)


class PolicyValidationError(IsolatedAgentsError):
    """Raised when a Policy object contains an unrecognised field or a field
    with the wrong type.

    Attributes:
        field_name: The name of the offending field.
        expected_type: A human-readable description of the expected type (may
            be ``None`` for unknown-field errors where no expected type exists).
    """

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        expected_type: str | None = None,
    ) -> None:
        suggestion = None
        if field_name and expected_type:
            suggestion = (
                f"The field '{field_name}' expects type '{expected_type}'. "
                f"Check the Policy documentation for valid values."
            )
        elif field_name:
            suggestion = (
                f"The field '{field_name}' is not recognized. "
                f"Check for typos or refer to the Policy documentation."
            )

        super().__init__(message, suggestion=suggestion)
        self.field_name = field_name
        self.expected_type = expected_type


class SpawnContextError(IsolatedAgentsError):
    """Raised when ``spawn_sub_agent()`` is called outside an active parent
    session context (i.e. the ``ISOLATED_AGENTS_SPAWN_SOCKET`` environment
    variable is not set or the socket is unreachable).
    """

    def __init__(self, message: str = "Not running in a sub-agent context"):
        suggestion = (
            "spawn_sub_agent() can only be called from within an agent that has "
            "allow_sub_agents=True in its policy. Make sure:\n"
            "  1. The parent agent's policy has allow_sub_agents=True\n"
            "  2. You're calling spawn_sub_agent() from inside the agent function"
        )
        super().__init__(message, suggestion=suggestion)


class NestingDepthExceededError(IsolatedAgentsError):
    """Raised when spawning a sub-agent would exceed the configured
    ``max_sub_agent_depth`` limit.

    Attributes:
        current_depth: The nesting depth at the time of the failed spawn attempt.
        max_depth: The configured maximum nesting depth.
    """

    def __init__(
        self,
        message: str,
        current_depth: int | None = None,
        max_depth: int | None = None,
    ) -> None:
        suggestion = None
        if current_depth and max_depth:
            suggestion = (
                f"Current nesting depth ({current_depth}) exceeds maximum ({max_depth}). "
                f"Increase max_sub_agent_depth in your policy or restructure your agent hierarchy."
            )
        super().__init__(message, suggestion=suggestion)
        self.current_depth = current_depth
        self.max_depth = max_depth


class SubAgentCountExceededError(RuntimeError):
    """Raised when spawning a sub-agent would exceed the configured
    ``max_sub_agents`` limit for the parent session.

    Attributes:
        current_count: The number of sub-agents already spawned.
        max_agents: The configured maximum number of sub-agents.
    """

    def __init__(
        self,
        message: str,
        current_count: int | None = None,
        max_agents: int | None = None,
    ) -> None:
        super().__init__(message)
        self.current_count = current_count
        self.max_agents = max_agents


class SubAgentTimeoutError(RuntimeError):
    """Raised by ``SubAgentHandle.wait()`` when the specified timeout elapses
    before the sub-agent session completes.

    Attributes:
        sub_session_id: The identifier of the timed-out sub-agent session.
        timeout_seconds: The timeout value that was exceeded.
    """

    def __init__(
        self,
        message: str,
        sub_session_id: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.sub_session_id = sub_session_id
        self.timeout_seconds = timeout_seconds


class SpawnCommunicationError(RuntimeError):
    """Raised when IPC communication between the in-container Spawn API client
    and the host-side Spawn Daemon fails (e.g. socket write/read error,
    unexpected response format).
    """


class SubAgentCancelledError(IsolatedAgentsError):
    """Raised when a sub-agent is explicitly cancelled via
    ``SubAgentHandle.cancel()`` and the caller awaits the result.
    """

    def __init__(self, message: str = "Sub-agent was cancelled"):
        suggestion = "The sub-agent was cancelled before completion. This is expected if you called cancel()."
        super().__init__(message, suggestion=suggestion)


class NetworkAccessDeniedError(IsolatedAgentsError):
    """Raised when network access is blocked by policy.

    Attributes:
        endpoint: The endpoint that was blocked
        policy: The network policy that blocked access
    """

    def __init__(self, endpoint: str, message: str | None = None):
        if not message:
            message = f"Network access denied to {endpoint}"

        suggestion = (
            f"To allow access to {endpoint}, update your policy:\n"
            f"  policy = Policy(\n"
            f"      network=NetworkPolicy(\n"
            f"          disabled=False,\n"
            f"          allowed_endpoints=['{endpoint}']\n"
            f"      )\n"
            f"  )"
        )
        super().__init__(message, suggestion=suggestion)
        self.endpoint = endpoint


class PackageInstallationError(IsolatedAgentsError):
    """Raised when pip package installation fails.

    Attributes:
        package: The package that failed to install
        error: The error message from pip
    """

    def __init__(self, package: str, error: str):
        message = f"Failed to install package '{package}': {error}"

        suggestion = (
            f"Package installation failed. Try:\n"
            f"  • Check package name spelling: '{package}'\n"
            f"  • Specify version: '{package}==1.0.0'\n"
            f"  • Check if package exists on PyPI\n"
            f"  • Increase timeout if network is slow"
        )
        super().__init__(message, suggestion=suggestion)
        self.package = package
        self.error = error


class ResourceLimitExceededError(IsolatedAgentsError):
    """Raised when agent exceeds resource limits.

    Attributes:
        resource: The resource that was exceeded (cpu, memory, timeout)
        limit: The configured limit
        actual: The actual usage
    """

    def __init__(self, resource: str, limit: float, actual: float):
        message = f"{resource.capitalize()} limit exceeded: {actual} > {limit}"

        suggestion = None
        if resource == "memory":
            suggestion = (
                f"Memory limit ({limit}MB) exceeded. Increase memory in policy:\n"
                f"  policy = Policy(memory_mb={int(limit * 1.5)})  # Increase by 50%"
            )
        elif resource == "cpu":
            suggestion = (
                f"CPU limit ({limit} cores) exceeded. Increase CPU in policy:\n"
                f"  policy = Policy(cpu_cores={limit * 1.5})  # Increase by 50%"
            )
        elif resource == "timeout":
            suggestion = (
                f"Execution timeout ({int(limit)}s) exceeded. Increase timeout:\n"
                f"  policy = Policy(timeout_seconds={int(limit * 2)})  # Double timeout"
            )

        super().__init__(message, suggestion=suggestion)
        self.resource = resource
        self.limit = limit
        self.actual = actual


class AgentImportError(IsolatedAgentsError):
    """Raised when agent function cannot import required modules.

    Attributes:
        module: The module that failed to import
        agent_name: The name of the agent function
    """

    def __init__(self, module: str, agent_name: str | None = None):
        message = f"Agent failed to import module '{module}'"
        if agent_name:
            message += f" in function '{agent_name}'"

        suggestion = (
            f"Module '{module}' not found. Add it to pip_packages:\n"
            f"  policy = Policy(pip_packages=['{module}'])\n\n"
            f"Remember: imports must be inside the agent function, not at module level."
        )
        super().__init__(message, suggestion=suggestion)
        self.module = module
        self.agent_name = agent_name


class SubAgentCancelledError(RuntimeError):
    """Raised when a sub-agent is explicitly cancelled via
    ``SubAgentHandle.cancel()`` and the caller awaits the result.
    """


class WorkingDirectoryError(IsolatedAgentsError):
    """Raised when the specified working directory does not exist."""

    def __init__(self, message: str, path: str | None = None):
        suggestion = None
        if path:
            suggestion = (
                f"The directory '{path}' does not exist. Create it with:\n"
                f"  from pathlib import Path\n"
                f"  Path('{path}').mkdir(parents=True, exist_ok=True)"
            )
        super().__init__(message, suggestion=suggestion)


class OutputSizeLimitError(IsolatedAgentsError):
    """Raised when the total size of output files exceeds the Policy's
    ``max_output_bytes`` limit.

    Attributes:
        total_bytes: Actual total size of the output in bytes.
        limit_bytes: The ``max_output_bytes`` limit that was exceeded.
    """

    def __init__(
        self,
        message: str,
        total_bytes: int | None = None,
        limit_bytes: int | None = None,
    ) -> None:
        suggestion = None
        if total_bytes and limit_bytes:
            mb_total = total_bytes / (1024 * 1024)
            mb_limit = limit_bytes / (1024 * 1024)
            suggestion = (
                f"Output size ({mb_total:.1f}MB) exceeds limit ({mb_limit:.1f}MB). "
                f"Either increase max_output_bytes in your policy or reduce output size."
            )
        super().__init__(message, suggestion=suggestion)
        self.total_bytes = total_bytes
        self.limit_bytes = limit_bytes


class ContainerError(IsolatedAgentsError):
    """Raised when a Podman command fails during container lifecycle management.

    Attributes:
        command: The full command list that was executed.
        exit_code: The process exit code returned by Podman.
        stderr: The raw stderr output from Podman.
    """

    def __init__(
        self,
        message: str,
        command: list[str] | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        suggestion = None

        # Provide helpful suggestions based on common errors
        if stderr:
            if "permission denied" in stderr.lower():
                suggestion = (
                    "Permission denied. Try:\n"
                    "  • Linux: sudo usermod -aG docker $USER (then log out/in)\n"
                    "  • Check container runtime is running: podman ps"
                )
            elif "no such file or directory" in stderr.lower():
                suggestion = (
                    "File or directory not found. Check that:\n"
                    "  • The workspace directory exists\n"
                    "  • All mounted paths are valid"
                )
            elif "network" in stderr.lower() and "unreachable" in stderr.lower():
                suggestion = (
                    "Network unreachable. Check that:\n"
                    "  • Network is enabled in policy: network=NetworkPolicy(disabled=False)\n"
                    "  • Endpoints are in allowed_endpoints list"
                )

        super().__init__(message, suggestion=suggestion)
        self.command = command or []
        self.exit_code = exit_code
        self.stderr = stderr or ""

    def __str__(self) -> str:
        base = super().__str__()
        parts = [base]
        if self.command:
            # Redact -e VAR=VALUE entries so secrets don't appear in tracebacks.
            redacted = _redact_env_flags(self.command)
            parts.append(f"  command: {' '.join(redacted)}")
        if self.exit_code is not None:
            parts.append(f"  exit_code: {self.exit_code}")
        if self.stderr:
            parts.append(f"  stderr: {self.stderr.strip()}")
        return "\n".join(parts)


def _redact_env_flags(cmd: list[str]) -> list[str]:
    """Return a copy of *cmd* with ``-e VAR=VALUE`` values replaced by
    ``-e VAR=<redacted>`` so that secrets do not appear in error messages."""
    result: list[str] = []
    i = 0
    while i < len(cmd):
        arg = cmd[i]
        if arg == "-e" and i + 1 < len(cmd):
            result.append(arg)
            kv = cmd[i + 1]
            if "=" in kv:
                key = kv.split("=", 1)[0]
                result.append(f"{key}=<redacted>")
            else:
                result.append(kv)
            i += 2
        else:
            result.append(arg)
            i += 1
    return result
