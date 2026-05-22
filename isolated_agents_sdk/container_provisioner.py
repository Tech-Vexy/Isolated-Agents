"""Container Provisioner for the Isolated Agents SDK.

Builds and executes rootless Podman container commands from a validated Policy.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.container.types import (
    ContainerHandle,
    Mount,
    NetworkConfig,
    ResourceLimits,
    SecurityConfig,
)
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.exceptions import (
    ContainerError,
    PodmanNotFoundError,
    WorkingDirectoryError,
)
from isolated_agents_sdk.models import Policy

DEFAULT_IMAGE = "python:3.11-slim"


class ContainerProvisioner:
    """Provisions and initializes isolated containers for agent execution.

    The provisioner is responsible for mapping a high-level :class:`Policy` into
    a low-level container configuration. It handles:
    - Host-to-container path mapping and mount setup.
    - Resource limit enforcement (CPU, Memory).
    - Network isolation and allowlisting.
    - Security hardening (User mapping, Capabilities, Seccomp).
    - Environment variable injection.

    It returns a :class:`ContainerHandle` which captures the live container state.
    """

    def __init__(
        self,
        adapter: Optional[ContainerRuntimeAdapter] = None,
        audit_logger: Optional[AuditLogger] = None,
        base_image: str = DEFAULT_IMAGE,
    ) -> None:
        self._adapter = adapter or PodmanAdapter(base_image=base_image)
        self._audit_logger = audit_logger or AuditLogger()
        self._base_image = base_image

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def provision(
        self,
        working_dir: str | Path,
        policy: Policy,
        session_id: str,
        agent_id: str,
        spawn_socket_path: Optional[str] = None,
    ) -> ContainerHandle:
        """Provision a container for the given policy.

        Args:
            working_dir: Host path to the working directory to mount.
            policy: Validated Policy object describing resource/network/fs constraints.
            session_id: Unique identifier for this session.
            agent_id: Identifier for the agent being launched.

        Returns:
            A :class:`ContainerHandle` containing the container ID.

        Raises:
            ContainerError: If container creation fails.
            WorkingDirectoryError: If *working_dir* does not exist.
        """
        working_dir = Path(working_dir)
        if not working_dir.exists():
            raise WorkingDirectoryError(
                f"Working directory does not exist: {working_dir}"
            )

        # Initialize adapter if needed
        try:
            await self._adapter.initialize()
        except PodmanNotFoundError:
            raise
        except Exception as e:
            raise ContainerError(f"Failed to initialize container adapter: {e}")

        # Map Policy to Adapter types
        image = policy.base_image or self._base_image
        
        # 1. Base mounts (Workspace and Policy mounts)
        mounts = [
            Mount(source=str(working_dir), target="/workspace", readonly=False)
        ]
        
        # If we have an output path in container, ensure it's writable and limited.
        # Note: If read_only_rootfs is True, the adapter might also try to create a tmpfs 
        # at /output. The provisioner's explicit mount here will handle the size constraint.
        if policy.output_path_in_container:
            mounts.append(Mount(
                source="tmpfs",
                target=policy.output_path_in_container,
                readonly=False,
                size_mb=policy.tmpfs_size_mb
            ))

        for mount_path in policy.readonly_mounts:
            mounts.append(Mount(source=mount_path, target=mount_path, readonly=True))

        # 2. Add System-Protected Internal Tmpfs (v0.2.1 Hardening)
        # This hidden mount holds bootstrap scripts, source code, and internal IPC sockets.
        # It is isolated from the user's /tmp and /workspace to prevent collisions.
        from isolated_agents_sdk.models import INTERNAL_BASE_PATH
        internal_tmpfs = Mount(
            source="tmpfs", 
            target=INTERNAL_BASE_PATH, 
            readonly=False,
            size_mb=64  # 64MB is plenty for internal sockets and scripts
        )
        mounts.append(internal_tmpfs)

        # 3. Add Spawn Socket mount if recursion is enabled
        if spawn_socket_path and policy.allow_sub_agents:
            from isolated_agents_sdk.models import CONTAINER_SPAWN_SOCKET_PATH
            mounts.append(Mount(
                source=spawn_socket_path, 
                target=CONTAINER_SPAWN_SOCKET_PATH, 
                readonly=False
            ))

        resources = ResourceLimits(
            cpu_cores=policy.cpu_cores,
            memory_mb=policy.memory_mb,
            memory_swap_mb=policy.memory_mb,  # Disable swap
        )

        network = NetworkConfig(
            disabled=policy.network.disabled,
            allowed_endpoints=policy.network.allowed_endpoints,
            websockets=policy.network.websockets,
            grpc=policy.network.grpc,
            ingress_ports=policy.network.ingress_ports,
        )

        security = SecurityConfig(
            cap_drop=policy.cap_drop,
            cap_add=policy.cap_add,
            read_only_rootfs=policy.read_only_rootfs,
            no_new_privileges=True,
            seccomp_profile=policy.seccomp_profile,
            user=policy.container_user,
            tmpfs_size_mb=policy.tmpfs_size_mb,
        )

        # Environment variables
        env = {}
        # Forward from host
        for var in policy.allowed_env_vars:
            value = os.environ.get(var)
            if value is not None:
                env[var] = value
        
        # Add explicit variables
        env.update(policy.env_vars)
        
        # Add metadata for sub-agents and durable execution
        env["ISOLATED_AGENTS_SESSION_ID"] = session_id
        env["ISOLATED_AGENTS_AGENT_ID"] = agent_id
        if spawn_socket_path and policy.allow_sub_agents:
            from isolated_agents_sdk.models import CONTAINER_SPAWN_SOCKET_PATH
            env["ISOLATED_AGENTS_SPAWN_SOCKET"] = CONTAINER_SPAWN_SOCKET_PATH

        try:
            handle = await self._adapter.provision_container(
                image=image,
                command=["tail", "-f", "/dev/null"],
                mounts=mounts,
                resources=resources,
                network=network,
                security=security,
                env=env,
                working_dir="/workspace",
            )
        except Exception as e:
            raise ContainerError(
                f"Failed to provision container via {self._adapter.get_adapter_name()}: {e}"
            )

        await self._audit_logger.log_event(
            event_type="container_created",
            session_id=session_id,
            agent_id=agent_id,
            payload={
                "container_id": handle.container_id,
                "image": image,
                "working_dir": str(working_dir),
                "adapter": self._adapter.get_adapter_name(),
            },
        )

        return handle
