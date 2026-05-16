"""Podman Container Runtime Adapter."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Optional

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
from isolated_agents_sdk.adapters.exceptions import (
    AdapterError,
    AdapterInitializationError,
    AdapterOperationError,
)
from isolated_agents_sdk.exceptions import PodmanNotFoundError

DEFAULT_IMAGE = "python:3.11-slim"
_PODMAN_TIMEOUT_SECONDS = 300


class PodmanAdapter(ContainerRuntimeAdapter):
    """Podman container runtime adapter.
    
    Wraps Podman CLI commands to provide container lifecycle management.
    """
    
    def __init__(
        self, 
        base_image: str = DEFAULT_IMAGE, 
        socket_path: Optional[str] = None,
        timeout: float = _PODMAN_TIMEOUT_SECONDS,
        **kwargs
    ):
        """Initialize Podman adapter.
        
        Args:
            base_image: Default container image to use
            socket_path: Path to Podman socket (unused in CLI-based adapter)
            timeout: Default timeout for container operations
            **kwargs: Additional configuration parameters
        """
        super().__init__()
        self._base_image = base_image
        self._socket_path = socket_path
        self._timeout = timeout
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the adapter and verify Podman is available."""
        if self._initialized:
            return
        
        # Check if Podman is installed
        if shutil.which("podman") is None:
            raise PodmanNotFoundError(
                "Podman is not installed or not accessible on PATH. "
                "Please install Podman to use this adapter."
            )
        
        # Verify connectivity
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
        except Exception as e:
            raise PodmanNotFoundError(f"Failed to execute Podman: {e}") from e

        # Verify cgroups v2 support
        await self._check_cgroups_v2()
        
        self._initialized = True
    
    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if the adapter is healthy and ready to use."""
        return await self.check_availability()

    async def check_availability(self) -> bool:
        """Check if Podman is available and accessible."""
        try:
            cmd = ["podman", "version"]
            stdout, stderr, returncode = await self._run_podman(cmd, timeout=5.0)
            return returncode == 0
        except Exception:
            return False
    
    async def provision_container(
        self,
        image: str,
        command: list[str],
        mounts: list[Mount],
        resources: ResourceLimits,
        network: NetworkConfig,
        security: SecurityConfig,
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
    ) -> ContainerHandle:
        """Provision a new container.
        
        Args:
            image: Container image to use
            mounts: List of volume mounts
            resource_limits: CPU and memory limits
            network_config: Network configuration
            security_config: Security settings
            environment: Environment variables
            working_dir: Working directory inside container
            command: Command to run (default: tail -f /dev/null)
        
        Returns:
            ContainerHandle with container ID
        
        Raises:
            AdapterOperationError: If container creation fails
        """
        if not self._initialized:
            await self.initialize()
        
        cmd = self._build_run_command(
            image=image,
            mounts=mounts,
            resource_limits=resources,
            network_config=network,
            security_config=security,
            environment=env or {},
            working_dir=working_dir,
            command=command,
        )
        
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        if returncode != 0:
            raise AdapterOperationError(
                f"Failed to create container (exit {returncode}): {stderr.decode()}"
            )
        
        container_id = stdout.decode().strip()
        return ContainerHandle(container_id=container_id, image=image)
    
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[float] = None,
        user: Optional[str] = None,
    ) -> ExecResult:
        """Execute a command in a running container.
        
        Args:
            container_id: Container ID
            command: Command to execute
            working_dir: Working directory for command
            environment: Environment variables
            user: User to run the command as (e.g. "root")
        
        Returns:
            ExecResult with exit code and output
        """
        cmd = ["podman", "exec"]
        
        if user:
            cmd.extend(["--user", user])
            
        if working_dir:
            cmd.extend(["--workdir", working_dir])
        
        if env:
            for key, value in env.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        cmd.append(container_id)
        cmd.extend(command)
        
        stdout, stderr, returncode = await self._run_podman(cmd, timeout=timeout or self._timeout)
        
        return ExecResult(
            exit_code=returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )
    
    async def copy_from_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy files from container to host.
        
        Args:
            container_id: Container ID
            src_path: Path inside container
            dest_path: Destination path on host
        """
        cmd = ["podman", "cp", f"{container_id}:{src_path}", dest_path]
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        if returncode != 0:
            raise AdapterOperationError(
                f"Failed to copy from container: {stderr.decode()}"
            )
    
    async def copy_to_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy files from host to container.
        
        Args:
            container_id: Container ID
            src_path: Source path on host
            dest_path: Destination path inside container
        """
        cmd = ["podman", "cp", src_path, f"{container_id}:{dest_path}"]
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        if returncode != 0:
            raise AdapterOperationError(
                f"Failed to copy to container: {stderr.decode()}"
            )
    
    async def get_container_stats(self, container_id: str) -> ContainerStats:
        """Get resource usage statistics for a container.
        
        Args:
            container_id: Container ID
        
        Returns:
            ContainerStats with CPU and memory usage
        """
        cmd = ["podman", "stats", "--no-stream", "--format", "json", container_id]
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        if returncode != 0:
            raise AdapterOperationError(
                f"Failed to get container stats: {stderr.decode()}"
            )
        
        try:
            stats_list = json.loads(stdout.decode())
            if not stats_list:
                return ContainerStats(cpu_percent=0.0, memory_mb=0.0, memory_limit_mb=0.0)
            stats_data = stats_list[0]
        except (json.JSONDecodeError, IndexError):
            return ContainerStats(cpu_percent=0.0, memory_mb=0.0, memory_limit_mb=0.0)
        
        return ContainerStats(
            cpu_percent=float(stats_data.get("CPUPerc", "0").rstrip("%")),
            memory_mb=self._parse_memory(stats_data.get("MemUsage", "0B")),
            memory_limit_mb=self._parse_memory(stats_data.get("MemLimit", "0B")),
            network_rx_bytes=0,
            network_tx_bytes=0,
        )
    
    async def destroy_container(
        self,
        container_id: str,
        force: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        """Destroy a container.
        
        Args:
            container_id: Container ID
            force: Force removal even if running
            timeout: Timeout for graceful shutdown (unused for force=True)
        """
        cmd = ["podman", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_id)
        
        await self._run_podman(cmd, timeout=timeout or self._timeout)
    
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    
    def _build_run_command(
        self,
        image: str,
        mounts: list[Mount],
        resource_limits: ResourceLimits,
        network_config: NetworkConfig,
        security_config: SecurityConfig,
        environment: dict[str, str],
        working_dir: Optional[str],
        command: Optional[list[str]],
    ) -> list[str]:
        """Build podman run command from parameters."""
        cmd = [
            "podman", "run",
            "--detach",
            "--userns=keep-id",
            "--pid=private",
            "--security-opt=no-new-privileges",
        ]
        
        # User
        if security_config.user:
            cmd.append(f"--user={security_config.user}")
        else:
            try:
                uid = os.getuid()
                gid = os.getgid()
            except AttributeError:
                uid, gid = 1000, 1000
            cmd.append(f"--user={uid}:{gid}")
        
        # Capabilities
        for cap in security_config.cap_drop:
            cmd.append(f"--cap-drop={cap}")
        for cap in security_config.cap_add:
            cmd.append(f"--cap-add={cap}")
        
        # Seccomp
        if security_config.seccomp_profile:
            cmd.append(f"--security-opt=seccomp={security_config.seccomp_profile}")
        
        # Read-only rootfs
        if security_config.read_only_rootfs:
            cmd.append("--read-only")
            cmd.extend(["--tmpfs", "/tmp:rw,nosuid,size=512m"])
            cmd.extend(["--tmpfs", "/run:rw,noexec,nosuid,size=64m"])
            cmd.extend(["--tmpfs", "/output:rw,noexec,nosuid,size=256m"])
        
        # Network
        if network_config.disabled:
            cmd.append("--network=none")
        else:
            # Use 'bridge' network which is more standard across Podman installations
            cmd.append("--network=bridge")
            cmd.append("--dns=8.8.8.8")
            
            if network_config.allowed_endpoints:
                # Note: Podman --add-host requires host:IP format.
                # Since we use 8.8.8.8 DNS, we don't need to manually map public endpoints.
                # True network whitelisting should be handled by a network policy provider.
                pass
        
        # Resources
        cmd.append(f"--cpus={resource_limits.cpu_cores}")
        cmd.append(f"--memory={resource_limits.memory_mb}m")
        cmd.append(f"--memory-swap={resource_limits.memory_mb}m")
        
        shm_size = int(resource_limits.memory_mb * 0.5)
        cmd.append(f"--shm-size={shm_size}m")
        
        # Mounts
        for mount in mounts:
            mode = "ro" if mount.readonly else "rw"
            cmd.extend(["-v", f"{mount.source}:{mount.target}:{mode}"])
        
        # Environment
        for key, value in environment.items():
            cmd.extend(["-e", f"{key}={value}"])
        
        # Working directory
        if working_dir:
            cmd.extend(["--workdir", working_dir])
        
        # Image
        cmd.append(image)
        
        # Command
        if command:
            cmd.extend(command)
        else:
            cmd.extend(["tail", "-f", "/dev/null"])
        
        return cmd
    
    async def _run_podman(
        self,
        cmd: list[str],
        timeout: float = _PODMAN_TIMEOUT_SECONDS,
    ) -> tuple[bytes, bytes, int]:
        """Run a Podman command and return (stdout, stderr, returncode)."""
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            
            return stdout, stderr, proc.returncode or 0
        
        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            raise AdapterOperationError(
                f"Podman command timed out after {timeout}s: {' '.join(cmd)}"
            )
        except Exception as e:
            raise AdapterOperationError(f"Podman command failed: {e}")
    
    async def _check_cgroups_v2(self) -> None:
        """Check if cgroups v2 is available (required for rootless resource limits)."""
        cgroup_path = Path("/sys/fs/cgroup/cgroup.controllers")
        if not cgroup_path.exists():
            # cgroups v2 not available, but don't fail - just log warning
            pass
    
    def _parse_memory(self, mem_str: str) -> float:
        """Parse memory string like '123.4MiB' to MB."""
        mem_str = mem_str.strip()
        if mem_str.endswith("GiB"):
            return float(mem_str[:-3]) * 1024
        elif mem_str.endswith("MiB"):
            return float(mem_str[:-3])
        elif mem_str.endswith("KiB"):
            return float(mem_str[:-3]) / 1024
        elif mem_str.endswith("B"):
            return float(mem_str[:-1]) / (1024 * 1024)
        return 0.0
