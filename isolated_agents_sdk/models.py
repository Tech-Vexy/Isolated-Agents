"""Data models for the Isolated Agents SDK (Pydantic v2 Migration)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from isolated_agents_sdk.exceptions import PolicyValidationError

# Paths used inside the container for agent execution (isolated from user space)
INTERNAL_BASE_PATH = "/run/isolated_agents_internal"
CONTAINER_BOOTSTRAP_PATH = f"{INTERNAL_BASE_PATH}/_agent_bootstrap.py"
CONTAINER_OUTPUT_PATH = f"{INTERNAL_BASE_PATH}/_agent_return.pkl"
CONTAINER_SOURCE_PATH = f"{INTERNAL_BASE_PATH}/_agent_source.pkl"
CONTAINER_SPAWN_SOCKET_PATH = f"{INTERNAL_BASE_PATH}/spawn.sock"


# ---------------------------------------------------------------------------
# NetworkPolicy
# ---------------------------------------------------------------------------

class NetworkPolicy(BaseModel):
    """Policy governing network access for an isolated agent.

    Attributes:
        disabled: Whether all network access is blocked (default: True).
        allowed_endpoints: List of host:port or CIDR strings to allow if not disabled.
        websockets: Whether to enable websocket support.
        grpc: Whether to enable gRPC protocol support.
        ingress_ports: List of ports to expose on the container for server-based agents.
    """
    model_config = ConfigDict(extra="forbid")

    disabled: bool = True
    allowed_endpoints: List[str] = Field(default_factory=list)
    websockets: bool = False
    grpc: bool = False
    ingress_ports: List[int] = Field(default_factory=list)

    def _to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class Policy(BaseModel):
    """Configuration for an isolated agent execution environment.

    Defines the resource limits, network access, filesystem mounts, and security
    profile for a container session.
    """
    model_config = ConfigDict(extra="forbid")

    # Resource limits
    cpu_cores: float = 1.0
    memory_mb: int = 512

    # Network
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)

    # Filesystem
    readonly_mounts: List[str] = Field(default_factory=list)

    # Sub-agent lifecycle
    allow_sub_agents: bool = False

    # Environment variables
    allowed_env_vars: List[str] = Field(default_factory=list)
    env_vars: Dict[str, str] = Field(default_factory=dict)
    blocked_env_vars: List[str] = Field(default_factory=list)
    sensitive_env_vars: List[str] = Field(default_factory=list)

    # Agent package dependencies
    pip_packages: List[str] = Field(default_factory=list)
    pip_index_url: Optional[str] = None
    pip_require_hashes: bool = False

    # Output redirection
    output_path_in_container: str = "/output"
    max_output_bytes: Optional[int] = None

    # Lifecycle behavior
    timeout_seconds: Optional[int] = None
    log_output_path: Optional[str] = None
    retry_count: int = 0
    retry_delay_seconds: int = 1
    cache_duration_seconds: int = 0
    
    # Mode of execution
    entrypoint: Optional[List[str]] = None
    base_image: str = "python:3.11-slim"

    # Advanced Capabilities
    requires_display: bool = False
    tmpfs_secrets: Optional[Dict[str, str]] = None
    proxy_url: Optional[str] = None
    proxy_ca_cert: Optional[str] = None
    enable_session_replay: bool = False
    enable_telemetry: bool = False
    interactive: bool = False
    
    # Result validation
    structured_output: Optional[Dict[str, Any]] = None
    
    # State persistence
    durable: bool = False

    # Security & Resource Hardening (v0.2.1)
    cap_drop: List[str] = Field(default_factory=lambda: ["ALL"])
    cap_add: List[str] = Field(default_factory=list)
    seccomp_profile: Optional[str] = None
    read_only_rootfs: bool = True
    tmpfs_size_mb: int = 512  # Default size limit for all user-writable tmpfs mounts (/tmp, /output)

    # Health monitoring
    resource_monitor_interval: int = 5
    cpu_threshold_percent: float = 90.0
    memory_threshold_percent: float = 90.0

    # User context
    container_user: Optional[str] = None
    
    # Sub-agent nesting limits
    max_sub_agent_depth: int = 3
    max_sub_agents: int = 10
    
    # Database access
    database_access: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("cpu_cores", mode="before")
    @classmethod
    def _validate_cpu_cores(cls, v: Any) -> float:
        if isinstance(v, bool):
            raise ValueError("cpu_cores cannot be a boolean")
        return float(v)

    @field_validator("memory_mb", "timeout_seconds", "max_output_bytes", 
                     "retry_count", "retry_delay_seconds", "cache_duration_seconds",
                     "resource_monitor_interval", "max_sub_agent_depth", "max_sub_agents",
                     "tmpfs_size_mb", mode="before")
    @classmethod
    def _validate_integers(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("Expected integer, got boolean")
        return int(v)

    def _to_dict(self) -> Dict[str, Any]:
        """Backward compatibility for ._to_dict() / asdict() pattern."""
        return self.model_dump()

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Policy":
        """Backward compatibility for ._from_dict(d) pattern."""
        try:
            return cls.model_validate(data)
        except Exception as e:
            # v0.2.1: Extract field_name and expected_type for legacy compatibility
            # In Pydantic v2, we can parse the ValidationError to get details.
            from pydantic import ValidationError
            field_name = None
            expected_type = None
            if isinstance(e, ValidationError):
                error = e.errors()[0]
                field_name = str(error['loc'][0]) if error['loc'] else None
                expected_type = error['type'] # e.g. 'extra_forbidden', 'int_parsing'
            raise PolicyValidationError(str(e), field_name=field_name, expected_type=expected_type)

    def to_json(self) -> str:
        """Serialise this Policy to a JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "Policy":
        """Deserialise a Policy from a JSON string."""
        # v0.2.1: Use parse_obj to ensure strict integer/boolean types before Pydantic coercion.
        # This fixes legacy tests that expect failures for floats in integer fields.
        try:
            raw = json.loads(data)
            if isinstance(raw.get("timeout_seconds"), float) and not raw.get("timeout_seconds").is_integer():
                raise PolicyValidationError("timeout_seconds must be an integer", field_name="timeout_seconds", expected_type="int")
            if "network" in raw and "disabled" in raw["network"] and not isinstance(raw["network"]["disabled"], bool):
                raise PolicyValidationError("network.disabled must be a boolean", field_name="disabled", expected_type="bool")
            return cls.model_validate(raw)
        except json.JSONDecodeError as e:
            raise PolicyValidationError(str(e))
        except PolicyValidationError:
            raise
        except Exception as e:
            # v0.2.1: Extract field_name and expected_type for legacy compatibility
            from pydantic import ValidationError
            field_name = None
            expected_type = None
            if isinstance(e, ValidationError):
                error = e.errors()[0]
                field_name = str(error['loc'][0]) if error['loc'] else None
                expected_type = error['type']
                # Map internal types to user-friendly strings for legacy tests
                if expected_type == "int_type": expected_type = "int"
                if expected_type == "float_type": expected_type = "float"
                if expected_type == "bool_type": expected_type = "bool"
                if "int" in expected_type: expected_type = "int"
                if "float" in expected_type: expected_type = "float"
                if expected_type == "value_error" and "int" in str(e).lower(): expected_type = "int"
                if expected_type == "value_error" and "float" in str(e).lower(): expected_type = "float"
                if expected_type == "value_error" and "bool" in str(e).lower(): expected_type = "bool"
            raise PolicyValidationError(str(e), field_name=field_name, expected_type=expected_type)


# ---------------------------------------------------------------------------
# AgentResult
# ---------------------------------------------------------------------------

class AgentResult(BaseModel):
    """The outcome of an isolated agent execution."""
    exit_code: int
    artifacts: Dict[str, str]
    session_id: str
    output: Optional[Any] = None
    error: Optional[str] = None  # Human-readable error if exit_code != 0


# ---------------------------------------------------------------------------
# Sub-Agent Models
# ---------------------------------------------------------------------------

class SubAgentError(BaseModel):
    """Error payload captured when the sub-agent raises an unhandled exception."""
    exception_type: str
    message: str

class SubAgentResult(BaseModel):
    """Result returned to the parent agent when a sub-agent session completes."""
    exit_code: int
    artifacts: Dict[str, bytes]
    sub_session_id: str
    status: str
    error: Optional[SubAgentError] = None

class SubSessionInfo(BaseModel):
    """Session info for a sub-agent."""
    sub_session_id: str
    parent_session_id: str
    container_id: str
    agent_id: str
    started_at: str
    status: str
    nesting_depth: int

class ClampEvent(BaseModel):
    """Describes a single field that was clamped by PolicyCapEnforcer."""
    parent_session_id: str
    sub_session_id: str
    field: str
    requested_value: Any
    clamped_value: Any


# ---------------------------------------------------------------------------
# SubAgentPolicy
# ---------------------------------------------------------------------------

class SubAgentPolicy(BaseModel):
    """Policy applied to a sub-agent session."""
    model_config = ConfigDict(extra="forbid")

    cpu_cores: float = 1.0
    memory_mb: int = 512
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)
    readonly_mounts: List[str] = Field(default_factory=list)
    allowed_env_vars: List[str] = Field(default_factory=list)
    output_path_in_container: str = "/output"
    max_output_bytes: Optional[int] = None
    timeout_seconds: Optional[int] = None
    log_output_path: Optional[str] = None
    max_sub_agent_depth: int = 3
    max_sub_agents: int = 10

    def _to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "SubAgentPolicy":
        try:
            return cls.model_validate(data)
        except Exception as e:
            raise PolicyValidationError(str(e))

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "SubAgentPolicy":
        try:
            return cls.model_validate_json(data)
        except Exception as e:
            raise PolicyValidationError(str(e))


# ---------------------------------------------------------------------------
# SessionInfo & Metrics
# ---------------------------------------------------------------------------

class SessionMetrics(BaseModel):
    cpu_percent: float
    memory_mb: float

class SessionInfo(BaseModel):
    session_id: str
    container_id: str
    agent_id: str
    started_at: str
    status: str
    error: Optional[str] = None # Capture failures like OOM or bootstrap errors
    sub_sessions: List[SubSessionInfo] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------

class AuditEvent(BaseModel):
    """Structured audit log entry for SDK operations."""
    event_type: str
    timestamp: str
    session_id: str
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    container_id: Optional[str] = None
