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
    """Provisions containers via a ContainerRuntimeAdapter from a validated Policy.

    Args:
        adapter: ContainerRuntimeAdapter instance (defaults to PodmanAdapter).
        audit_logger: AuditLogger instance for emitting lifecycle events.
        base_image: Container image to use. Defaults to ``python:3.11-slim``.
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
        
        mounts = [
            Mount(source=str(working_dir), target="/workspace", readonly=False)
        ]
        for mount_path in policy.readonly_mounts:
            mounts.append(Mount(source=mount_path, target=mount_path, readonly=True))

        resources = ResourceLimits(
            cpu_cores=policy.cpu_cores,
            memory_mb=policy.memory_mb,
            memory_swap_mb=policy.memory_mb,  # Disable swap
        )

        network = NetworkConfig(
            disabled=policy.network.disabled,
            allowed_endpoints=policy.network.allowed_endpoints,
        )

        security = SecurityConfig(
            cap_drop=policy.cap_drop,
            cap_add=policy.cap_add,
            read_only_rootfs=policy.read_only_rootfs,
            no_new_privileges=True,
            seccomp_profile=policy.seccomp_profile,
            user=policy.container_user,
        )

        # Environment variables
        env = {}
        for var in policy.allowed_env_vars:
            value = os.environ.get(var)
            if value is not None:
                env[var] = value

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

        self._audit_logger.log_event(
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
