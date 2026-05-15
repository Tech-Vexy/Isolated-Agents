"""Type definitions for container runtime adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContainerHandle:
    """Handle to a running or stopped container.
    
    Attributes:
        container_id: Unique identifier for the container
        image: Container image name (e.g., "python:3.11-slim")
        created_at: ISO 8601 timestamp of container creation
    """
    container_id: str
    image: str
    created_at: str = ""


@dataclass
class ExecResult:
    """Result of executing a command in a container.
    
    Attributes:
        exit_code: Process exit code (0 = success)
        stdout: Standard output as string
        stderr: Standard error as string
    """
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class ContainerStats:
    """Container resource usage statistics.
    
    Attributes:
        cpu_percent: Current CPU usage as percentage (0-100+)
        memory_mb: Current memory usage in megabytes
        memory_limit_mb: Memory limit in megabytes
        network_rx_bytes: Network bytes received
        network_tx_bytes: Network bytes transmitted
    """
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: float
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0


@dataclass
class Mount:
    """Container mount specification.
    
    Attributes:
        source: Host path to mount
        target: Container path where source is mounted
        readonly: If True, mount is read-only
    """
    source: str
    target: str
    readonly: bool = False


@dataclass
class ResourceLimits:
    """Container resource limits.
    
    Attributes:
        cpu_cores: Maximum CPU cores (e.g., 1.0, 2.5)
        memory_mb: Maximum memory in megabytes
        memory_swap_mb: Maximum swap memory in megabytes (None = no swap)
    """
    cpu_cores: float
    memory_mb: int
    memory_swap_mb: Optional[int] = None


@dataclass
class NetworkConfig:
    """Container network configuration.
    
    Attributes:
        disabled: If True, container has no network access
        allowed_endpoints: List of allowed endpoints in "host:port" or CIDR format
    """
    disabled: bool = True
    allowed_endpoints: list[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """Container security configuration.
    
    Attributes:
        cap_drop: Linux capabilities to drop (default: ["ALL"])
        cap_add: Linux capabilities to add back after drop
        read_only_rootfs: If True, root filesystem is read-only
        no_new_privileges: If True, prevent privilege escalation
        seccomp_profile: Path to seccomp profile or "unconfined" to disable
        user: UID:GID string for container user (None = derive from host)
    """
    cap_drop: list[str] = field(default_factory=lambda: ["ALL"])
    cap_add: list[str] = field(default_factory=list)
    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    seccomp_profile: Optional[str] = None
    user: Optional[str] = None

# Made with Bob
