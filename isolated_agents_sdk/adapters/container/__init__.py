"""Container runtime adapters for the Isolated Agents SDK.

This package provides adapters for different container runtimes:
- PodmanAdapter: Podman CLI/API (default)
- DockerAdapter: Docker CLI/API
- KubernetesAdapter: Kubernetes Jobs/Pods (future)

Example usage:
    from isolated_agents_sdk.adapters.container import PodmanAdapter
    from isolated_agents_sdk.adapters.container.types import (
        Mount, ResourceLimits, NetworkConfig, SecurityConfig
    )
    
    adapter = PodmanAdapter()
    await adapter.initialize()
    
    handle = await adapter.provision_container(
        image="python:3.11-slim",
        command=["tail", "-f", "/dev/null"],
        mounts=[Mount(source="/tmp", target="/workspace")],
        resources=ResourceLimits(cpu_cores=1.0, memory_mb=512),
        network=NetworkConfig(disabled=True),
        security=SecurityConfig(),
    )
"""

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import (
    ContainerHandle,
    ContainerStats,
    ExecResult,
    Mount,
    NetworkConfig,
    ResourceLimits,
    SecurityConfig,
)

__all__ = [
    "ContainerRuntimeAdapter",
    "ContainerHandle",
    "ContainerStats",
    "ExecResult",
    "Mount",
    "NetworkConfig",
    "ResourceLimits",
    "SecurityConfig",
]

# Made with Bob
