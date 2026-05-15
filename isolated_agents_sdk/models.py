"""Data models for the Isolated Agents SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, asdict
from typing import Optional, Any

from isolated_agents_sdk.exceptions import PolicyValidationError


# ---------------------------------------------------------------------------
# NetworkPolicy
# ---------------------------------------------------------------------------

@dataclass
class NetworkPolicy:
    disabled: bool = True
    # Allowlisted endpoints in "host:port" or CIDR notation
    allowed_endpoints: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

# Mapping of Policy field name → expected Python type (used for validation)
_POLICY_FIELD_TYPES: dict[str, type] = {
    "cpu_cores": float,
    "memory_mb": int,
    "network": dict,          # serialised as a nested dict in JSON
    "readonly_mounts": list,
    "allowed_env_vars": list,
    "pip_packages": list,      # packages to install in the container before running the agent
    "output_path_in_container": str,
    "max_output_bytes": int,   # Optional[int] — None is allowed, but the value must be int when present
    "timeout_seconds": int,    # Optional[int]
    "log_output_path": str,    # Optional[str]
    "entrypoint": list,        # Optional[list[str]] — e.g. ["node", "agent.js"]
    "base_image": str,         # Container image to use
    "requires_display": bool,  # Support for Xvfb virtual display
    "tmpfs_secrets": dict,     # Sensitive variables moved to memory-only tmpfs
    "proxy_url": str,          # MITM Proxy URL (e.g. http://host.containers.internal:8080)
    "proxy_ca_cert": str,      # Custom CA certificate for proxy decryption
    "enable_session_replay": bool,  # Record terminal session for replay
    # Security hardening
    "cap_drop": list,          # Linux capabilities to drop (default: ["ALL"])
    "cap_add": list,           # Linux capabilities to add back after drop (default: [])
    "seccomp_profile": str,    # Path to a seccomp JSON profile, or "unconfined" to disable
    "read_only_rootfs": bool,  # Mount the container root filesystem read-only (default: True)
    "resource_monitor_interval": int,  # Seconds between resource-usage polls (default: 5)
    "cpu_threshold_percent": float,    # Emit audit event when CPU% exceeds this (default: 90.0)
    "memory_threshold_percent": float, # Emit audit event when memory% exceeds this (default: 90.0)
    # Container identity
    "container_user": str,   # UID:GID string for --user (default: derived from host caller)
    # pip hardening
    "pip_index_url": str,    # Private PyPI mirror URL; None → use public PyPI
    "pip_require_hashes": bool,  # Require --hash= on every pip_packages entry (default: False)
    # Sub-agent nesting limits
    "max_sub_agent_depth": int,  # Maximum nesting depth for sub-agents (default: 3)
    "max_sub_agents": int,       # Maximum total sub-agents per parent session (default: 10)
}

_NETWORK_POLICY_FIELD_TYPES: dict[str, type] = {
    "disabled": bool,
    "allowed_endpoints": list,
}


def _validate_and_coerce_policy_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw dict destined for Policy construction.

    Raises PolicyValidationError for unknown fields or wrong value types.
    Returns a (possibly coerced) copy ready for dataclass construction.
    """
    known_fields = set(_POLICY_FIELD_TYPES.keys())
    for key in data:
        if key not in known_fields:
            raise PolicyValidationError(
                f"Unknown policy field: '{key}'",
                field_name=key,
                expected_type=None,
            )

    result: dict[str, Any] = {}
    for key, value in data.items():
        expected = _POLICY_FIELD_TYPES[key]
        if value is None:
            # Optional fields may be None
            result[key] = None
            continue
        # bool is a subclass of int in Python; guard against accepting True/False for int fields
        if expected is int and isinstance(value, bool):
            raise PolicyValidationError(
                f"Field '{key}' expects {expected.__name__}, got bool",
                field_name=key,
                expected_type=expected.__name__,
            )
        if expected is float:
            # Accept int as float (JSON numbers without decimal point are int)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PolicyValidationError(
                    f"Field '{key}' expects float, got {type(value).__name__}",
                    field_name=key,
                    expected_type="float",
                )
            result[key] = float(value)
            continue
        if not isinstance(value, expected):
            raise PolicyValidationError(
                f"Field '{key}' expects {expected.__name__}, got {type(value).__name__}",
                field_name=key,
                expected_type=expected.__name__,
            )
        result[key] = value

    return result


def _validate_network_policy_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw dict destined for NetworkPolicy construction."""
    known_fields = set(_NETWORK_POLICY_FIELD_TYPES.keys())
    for key in data:
        if key not in known_fields:
            raise PolicyValidationError(
                f"Unknown network policy field: '{key}'",
                field_name=f"network.{key}",
                expected_type=None,
            )

    result: dict[str, Any] = {}
    for key, value in data.items():
        expected = _NETWORK_POLICY_FIELD_TYPES[key]
        if not isinstance(value, expected):
            raise PolicyValidationError(
                f"Field 'network.{key}' expects {expected.__name__}, got {type(value).__name__}",
                field_name=f"network.{key}",
                expected_type=expected.__name__,
            )
        result[key] = value
    return result


@dataclass
class Policy:
    # Resource limits
    cpu_cores: float = 1.0
    memory_mb: int = 512

    # Network
    network: NetworkPolicy = field(default_factory=NetworkPolicy)

    # Filesystem
    readonly_mounts: list[str] = field(default_factory=list)

    # Environment variables forwarded into the container
    allowed_env_vars: list[str] = field(default_factory=list)

    # Packages to install inside the container before running the agent
    pip_packages: list[str] = field(default_factory=list)

    # Output
    output_path_in_container: str = "/output"
    max_output_bytes: Optional[int] = None

    # Session
    timeout_seconds: Optional[int] = None

    # Logging
    log_output_path: Optional[str] = None  # None → stderr

    # Framework Agnosticism
    # If provided, overrides the Python callable injection
    entrypoint: Optional[list[str]] = None
    # Container image to use. If None, the provisioner's default is used.
    base_image: str = "python:3.11-slim"

    # Advanced Capabilities
    requires_display: bool = False
    tmpfs_secrets: Optional[dict[str, str]] = None
    proxy_url: Optional[str] = None
    proxy_ca_cert: Optional[str] = None
    enable_session_replay: bool = False

    # Security hardening
    # Capabilities: drop ALL by default; add back only what is explicitly needed.
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    cap_add: list[str] = field(default_factory=list)
    # seccomp_profile: path to a JSON profile, "unconfined" to disable, or None
    # to use Podman's built-in default profile.
    seccomp_profile: Optional[str] = None
    # Mount the container root filesystem read-only.  Writable paths (/tmp,
    # /run, /output, /workspace) are provided via explicit tmpfs or bind mounts.
    read_only_rootfs: bool = True

    # Continuous resource monitoring
    # Interval in seconds between podman-stats polls (0 = disabled).
    resource_monitor_interval: int = 5
    # Emit a resource_limit_exceeded audit event when CPU% exceeds this value.
    cpu_threshold_percent: float = 90.0
    # Emit a resource_limit_exceeded audit event when memory usage exceeds this
    # percentage of the policy's memory_mb limit.
    memory_threshold_percent: float = 90.0

    # Container identity
    # UID:GID string passed to --user.  When None the provisioner derives it
    # from the host caller's os.getuid()/os.getgid() at provision time so the
    # process inside the container is never root even if the image defaults to
    # root.  Set to "0:0" only if the image genuinely requires root (not
    # recommended).
    container_user: Optional[str] = None

    # pip hardening
    # Private PyPI mirror.  None → use the default public index.
    pip_index_url: Optional[str] = None
    # When True every entry in pip_packages must carry a --hash= specifier and
    # pip is invoked with --require-hashes so the install fails if any hash
    # is missing or wrong.
    pip_require_hashes: bool = False

    # Sub-agent nesting limits
    # Maximum number of nesting levels permitted for sub-agents spawned within
    # this session.  A value of 3 means the parent is depth 0, its children
    # are depth 1, grandchildren depth 2, and great-grandchildren depth 3 (the
    # last permitted level).
    max_sub_agent_depth: int = 3
    # Maximum total number of sub-agents that may be spawned within a single
    # parent session (across all nesting levels).
    max_sub_agents: int = 10

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Policy":
        # Separate out the nested network dict before top-level validation
        raw = dict(data)
        network_raw: dict[str, Any] | None = raw.pop("network", None)

        validated = _validate_and_coerce_policy_dict(raw)

        if network_raw is not None:
            if not isinstance(network_raw, dict):
                raise PolicyValidationError(
                    f"Field 'network' expects dict, got {type(network_raw).__name__}",
                    field_name="network",
                    expected_type="dict",
                )
            net_validated = _validate_network_policy_dict(network_raw)
            validated["network"] = NetworkPolicy(**net_validated)

        return cls(**validated)

    def to_json(self) -> str:
        """Serialise this Policy to a JSON string."""
        return json.dumps(self._to_dict())

    @classmethod
    def from_json(cls, data: str) -> "Policy":
        """Deserialise a Policy from a JSON string.

        Raises PolicyValidationError for unknown fields or wrong value types.
        """
        try:
            raw = json.loads(data)
        except json.JSONDecodeError as exc:
            raise PolicyValidationError(f"Invalid JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise PolicyValidationError("Policy JSON must be a JSON object")

        return cls._from_dict(raw)


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    exit_code: int
    artifacts: dict[str, str]  # filename -> host path
    session_id: str


# ---------------------------------------------------------------------------
# Sub-Agent data models
# ---------------------------------------------------------------------------

@dataclass
class SubAgentError:
    """Error payload captured when the sub-agent raises an unhandled exception."""
    exception_type: str    # e.g. "ValueError"
    message: str


@dataclass
class SubAgentResult:
    """Result returned to the parent agent when a sub-agent session completes."""
    exit_code: int
    artifacts: dict[str, bytes]       # filename -> content
    sub_session_id: str
    status: str                        # "completed" | "failed" | "timeout" | "cancelled"
    error: Optional[SubAgentError] = None


@dataclass
class SubSessionInfo:
    """Session info for a sub-agent, as returned by list_sub_sessions()."""
    sub_session_id: str
    parent_session_id: str
    container_id: str
    agent_id: str
    started_at: str          # ISO 8601 UTC
    status: str              # "running" | "completed" | "failed" | "timeout" | "cancelled"
    nesting_depth: int


@dataclass
class ClampEvent:
    """Describes a single field that was clamped by PolicyCapEnforcer."""
    parent_session_id: str
    sub_session_id: str
    field: str               # e.g. "cpu_cores"
    requested_value: object
    clamped_value: object


# ---------------------------------------------------------------------------
# SubAgentPolicy
# ---------------------------------------------------------------------------

# Mapping of SubAgentPolicy field name -> expected Python type (for validation)
_SUB_AGENT_POLICY_FIELD_TYPES: dict[str, type] = {
    "cpu_cores": float,
    "memory_mb": int,
    "network": dict,
    "readonly_mounts": list,
    "allowed_env_vars": list,
    "output_path_in_container": str,
    "max_output_bytes": int,    # Optional[int]
    "timeout_seconds": int,     # Optional[int]
    "log_output_path": str,     # Optional[str]
    "max_sub_agent_depth": int,
    "max_sub_agents": int,
}


def _validate_sub_agent_policy_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw dict destined for SubAgentPolicy construction.

    Raises PolicyValidationError for unknown fields, wrong value types, or
    non-positive integer values for max_sub_agent_depth / max_sub_agents.
    Returns a (possibly coerced) copy ready for dataclass construction.
    """
    known_fields = set(_SUB_AGENT_POLICY_FIELD_TYPES.keys())
    for key in data:
        if key not in known_fields:
            raise PolicyValidationError(
                f"Unknown SubAgentPolicy field: '{key}'",
                field_name=key,
                expected_type=None,
            )

    result: dict[str, Any] = {}
    for key, value in data.items():
        expected = _SUB_AGENT_POLICY_FIELD_TYPES[key]
        if value is None:
            result[key] = None
            continue
        # bool is a subclass of int -- guard against accepting True/False for int fields
        if expected is int and isinstance(value, bool):
            raise PolicyValidationError(
                f"Field '{key}' expects {expected.__name__}, got bool",
                field_name=key,
                expected_type=expected.__name__,
            )
        if expected is float:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise PolicyValidationError(
                    f"Field '{key}' expects float, got {type(value).__name__}",
                    field_name=key,
                    expected_type="float",
                )
            result[key] = float(value)
            continue
        if not isinstance(value, expected):
            raise PolicyValidationError(
                f"Field '{key}' expects {expected.__name__}, got {type(value).__name__}",
                field_name=key,
                expected_type=expected.__name__,
            )
        result[key] = value

    # Validate that max_sub_agent_depth and max_sub_agents are positive integers.
    # None is not permitted for these fields — they must always be a positive int.
    for limit_field in ("max_sub_agent_depth", "max_sub_agents"):
        if limit_field in result:
            val = result[limit_field]
            if val is None or not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                raise PolicyValidationError(
                    f"Field '{limit_field}' must be a positive integer, got {val!r}",
                    field_name=limit_field,
                    expected_type="positive int",
                )

    return result


@dataclass
class SubAgentPolicy:
    """Policy applied to a sub-agent session.

    Identical schema to Policy (minus pip/display/proxy/replay fields);
    validated against the parent Policy by PolicyCapEnforcer before the
    sub-agent container is created.
    """
    cpu_cores: float = 1.0
    memory_mb: int = 512
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    readonly_mounts: list[str] = field(default_factory=list)
    allowed_env_vars: list[str] = field(default_factory=list)
    output_path_in_container: str = "/output"
    max_output_bytes: Optional[int] = None
    timeout_seconds: Optional[int] = None
    log_output_path: Optional[str] = None
    max_sub_agent_depth: int = 3
    max_sub_agents: int = 10

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "SubAgentPolicy":
        raw = dict(data)
        network_raw: dict[str, Any] | None = raw.pop("network", None)

        validated = _validate_sub_agent_policy_dict(raw)

        if network_raw is not None:
            if not isinstance(network_raw, dict):
                raise PolicyValidationError(
                    f"Field 'network' expects dict, got {type(network_raw).__name__}",
                    field_name="network",
                    expected_type="dict",
                )
            net_validated = _validate_network_policy_dict(network_raw)
            validated["network"] = NetworkPolicy(**net_validated)

        return cls(**validated)

    def to_json(self) -> str:
        """Serialise this SubAgentPolicy to a JSON string."""
        return json.dumps(self._to_dict())

    @classmethod
    def from_json(cls, data: str) -> "SubAgentPolicy":
        """Deserialise a SubAgentPolicy from a JSON string.

        Raises PolicyValidationError for unknown fields, wrong value types, or
        non-positive integer values for max_sub_agent_depth / max_sub_agents.
        """
        try:
            raw = json.loads(data)
        except json.JSONDecodeError as exc:
            raise PolicyValidationError(f"Invalid JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise PolicyValidationError("SubAgentPolicy JSON must be a JSON object")

        return cls._from_dict(raw)


# ---------------------------------------------------------------------------
# SessionInfo
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    session_id: str
    container_id: str
    agent_id: str
    started_at: str   # ISO 8601 UTC
    status: str       # "running" | "completed" | "failed" | "terminated"
    sub_sessions: list[SubSessionInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------

@dataclass
class SessionMetrics:
    cpu_percent: float
    memory_mb: float


@dataclass
class AuditEvent:
    event_type: str   # e.g. "container_created", "network_denied", ...
    timestamp: str    # ISO 8601 UTC
    session_id: str
    agent_id: str
    payload: dict     # event-specific fields


# ---------------------------------------------------------------------------
# AuditEvent event_type constants for sub-agent events
# ---------------------------------------------------------------------------

# Emitted when a sub-agent container is created.
# Payload includes: parent_session_id, sub_session_id, nesting_depth
AUDIT_SUB_AGENT_SPAWNED = "sub_agent_spawned"

# Emitted when a sub-agent session ends (any terminal state).
# Payload includes: sub_session_id, status, exit_code
AUDIT_SUB_AGENT_COMPLETED = "sub_agent_completed"

# Emitted for each field clamped by PolicyCapEnforcer.
# Payload includes: parent_session_id, sub_session_id, field,
#                   requested_value, clamped_value
AUDIT_POLICY_CAP_CLAMPED = "policy_cap_clamped"

# Emitted when a sub-agent is explicitly cancelled by the parent.
# Payload includes: sub_session_id, parent_session_id
AUDIT_SUB_AGENT_CANCELLED = "sub_agent_cancelled"

# Emitted when a spawn attempt is rejected due to nesting depth limit.
# Payload includes: parent_session_id, current_depth, max_depth
AUDIT_NESTING_DEPTH_EXCEEDED = "nesting_depth_exceeded"

# Emitted when a spawn attempt is rejected due to sub-agent count limit.
# Payload includes: parent_session_id, current_count, max_agents
AUDIT_SUB_AGENT_COUNT_EXCEEDED = "sub_agent_count_exceeded"
