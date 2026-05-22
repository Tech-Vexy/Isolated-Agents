"""Podman Container Runtime Adapter."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Callable, Optional

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
        remote_url: Optional[str] = None,
        use_remote: bool = False,
        timeout: float = _PODMAN_TIMEOUT_SECONDS,
        **kwargs
    ):
        """Initialize Podman adapter.
        
        Args:
            base_image: Default container image to use
            socket_path: Path to Podman socket
            remote_url: URL for remote Podman (e.g., "ssh://user@host")
            use_remote: Whether to use Podman remote
            timeout: Default timeout for container operations
            **kwargs: Additional configuration parameters
        """
        super().__init__()
        self._base_image = base_image
        self._socket_path = socket_path
        self._remote_url = remote_url
        self._use_remote = use_remote
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
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> ExecResult:
        """Execute a command in a running container.
        
        Args:
            container_id: Container ID
            command: Command to execute
            working_dir: Working directory for command
            env: Environment variables
            timeout: Command timeout
            user: User to run the command as (e.g. "root")
            on_stdout: Callback for real-time stdout
            on_stderr: Callback for real-time stderr
        
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
        
        stdout, stderr, returncode = await self._run_podman(
            cmd, 
            timeout=timeout or self._timeout,
            on_stdout=on_stdout,
            on_stderr=on_stderr,
        )
        
        return ExecResult(
            exit_code=returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )

    async def interactive_exec(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
        user: Optional[str] = None,
    ) -> int:
        """Execute an interactive command in a running container."""
        import subprocess

        cmd = ["podman", "exec", "-it"]
        
        if user:
            cmd.extend(["--user", user])
            
        if working_dir:
            cmd.extend(["--workdir", working_dir])
        
        if env:
            for key, value in env.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        cmd.append(container_id)
        cmd.extend(command)
        
        # We use a synchronous subprocess call here because it handles TTY/stdin
        # much more reliably than asyncio for interactive sessions.
        # This will block the event loop, but that's expected for an interactive shell.
        try:
            return subprocess.call(cmd)
        except Exception as e:
            raise AdapterOperationError(f"Interactive Podman command failed: {e}")
    
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

    def destroy_container_sync(
        self,
        container_id: str,
        force: bool = True,
    ) -> None:
        """Destroy container synchronously (emergency/atexit fallback)."""
        cmd = ["podman", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_id)
        
        try:
            import subprocess
            subprocess.run(cmd, capture_output=True, check=False)
        except Exception:
            pass
    
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
            # All user-writable mounts MUST have a size limit to prevent host DoS (Issue 4)
            size_opt = f"size={security_config.tmpfs_size_mb}m"
            cmd.extend(["--tmpfs", f"/tmp:rw,nosuid,nodev,{size_opt}"])
            cmd.extend(["--tmpfs", "/run:rw,noexec,nosuid,nodev,size=64m"])
            
            # v0.2.1 Filter: Only add the default /output tmpfs if it wasn't already 
            # explicitly requested as a mount. This prevents "duplicate mount destination" errors.
            explicit_targets = [m.target for m in mounts]
            if "/output" not in explicit_targets:
                cmd.extend(["--tmpfs", f"/output:rw,noexec,nosuid,nodev,{size_opt}"])
        
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
            
            # Ingress Ports: Expose ports on the container
            for port in network_config.ingress_ports:
                # Mapping host port same as container port for simplicity in basic adapter
                cmd.extend(["-p", f"{port}:{port}"])
        
        # Resources
        cmd.append(f"--cpus={resource_limits.cpu_cores}")
        
        # CPU Optimization: Assign CPU shares proportional to the core count
        # (1024 shares = 1 core). This improves scheduled latency under load.
        cpu_shares = int(resource_limits.cpu_cores * 1024)
        cmd.append(f"--cpu-shares={cpu_shares}")
        
        cmd.append(f"--memory={resource_limits.memory_mb}m")
        cmd.append(f"--memory-swap={resource_limits.memory_mb}m")
        
        # Optimization: Set reserved memory (soft limit) to 25% of hard limit 
        # for better host density and faster startup, except for heavy workloads.
        memory_reservation = int(resource_limits.memory_mb * 0.25)
        cmd.append(f"--memory-reservation={memory_reservation}m")
        
        shm_size = int(resource_limits.memory_mb * 0.5)
        cmd.append(f"--shm-size={shm_size}m")
        
        # Mounts
        for mount in mounts:
            if mount.source == "tmpfs":
                # Security Hardening: Apply nosuid, nodev to all ephemeral mounts
                opts = "rw,nosuid,nodev"
                if mount.size_mb:
                    opts += f",size={mount.size_mb}m"
                cmd.extend(["--tmpfs", f"{mount.target}:{opts}"])
            else:
                mode = "ro" if mount.readonly else "rw"
                # Compatibility: Use :Z suffix for SELinux relabeling if needed
                cmd.extend(["-v", f"{mount.source}:{mount.target}:{mode},nosuid,nodev"])
        
        # Environment
        for key, value in environment.items():
            cmd.extend(["-e", f"{key}={value}"])
        
        # Working directory
        if working_dir:
            cmd.extend(["--workdir", working_dir])
        
        # Image
        # Optimization: Use --pull=never if possible to avoid network latency during startup
        # for images that should already be present.
        cmd.append("--pull=missing")
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
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> tuple[bytes, bytes, int]:
        """Run a Podman command and return (stdout, stderr, returncode)."""
        # Inject remote flags if configured
        full_cmd = []
        if cmd[0] == "podman":
            full_cmd.append("podman")
            if self._use_remote:
                full_cmd.append("--remote")
            if self._remote_url:
                full_cmd.extend(["--url", self._remote_url])
            full_cmd.extend(cmd[1:])
        else:
            full_cmd = cmd

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout_data = bytearray()
            stderr_data = bytearray()

            async def read_stream(stream, callback, data):
                while True:
                    chunk = await stream.read(4096)
                    if not chunk:
                        break
                    data.extend(chunk)
                    if callback:
                        try:
                            callback(chunk.decode(errors="replace"))
                        except Exception:
                            pass

            # Use wait_for on the gather of stream readers and process wait
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(proc.stdout, on_stdout, stdout_data),
                    read_stream(proc.stderr, on_stderr, stderr_data),
                    proc.wait(),
                ),
                timeout=timeout,
            )
            
            return bytes(stdout_data), bytes(stderr_data), proc.returncode or 0
        
        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            raise AdapterOperationError(
                f"Podman command timed out after {timeout}s: {' '.join(full_cmd)}"
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
