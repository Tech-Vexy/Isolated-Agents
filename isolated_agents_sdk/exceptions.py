"""Custom exception classes for the Isolated Agents SDK."""

from __future__ import annotations


class PodmanNotFoundError(RuntimeError):
    """Raised when Podman is not installed or not accessible on PATH."""


class PolicyValidationError(ValueError):
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
        super().__init__(message)
        self.field_name = field_name
        self.expected_type = expected_type


class SpawnContextError(RuntimeError):
    """Raised when ``spawn_sub_agent()`` is called outside an active parent
    session context (i.e. the ``ISOLATED_AGENTS_SPAWN_SOCKET`` environment
    variable is not set or the socket is unreachable).
    """


class NestingDepthExceededError(RuntimeError):
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
        super().__init__(message)
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


class SubAgentCancelledError(RuntimeError):
    """Raised when a sub-agent is explicitly cancelled via
    ``SubAgentHandle.cancel()`` and the caller awaits the result.
    """


class WorkingDirectoryError(FileNotFoundError):
    """Raised when the specified working directory does not exist."""


class OutputSizeLimitError(RuntimeError):
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
        super().__init__(message)
        self.total_bytes = total_bytes
        self.limit_bytes = limit_bytes


class ContainerError(RuntimeError):
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
        super().__init__(message)
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
