"""Docker Container Runtime Adapter."""

from __future__ import annotations

import asyncio
import json
import subprocess
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
    AdapterInitializationError,
    AdapterOperationError,
)

DEFAULT_IMAGE = "python:3.11-slim"
_DOCKER_TIMEOUT_SECONDS = 300


class DockerAdapter(ContainerRuntimeAdapter):
    """Docker container runtime adapter.

    Wraps Docker CLI commands to provide container lifecycle management.
    Supports remote Docker hosts via the host parameter or DOCKER_HOST env var.
    """

    def __init__(
        self,
        base_image: str = DEFAULT_IMAGE,
        host: str | None = None,
        timeout: float = _DOCKER_TIMEOUT_SECONDS,
        **kwargs,
    ):
        """Initialize Docker adapter.

        Args:
            base_image: Default container image to use
            host: Docker host URL (e.g., "tcp://host:2375" or "ssh://user@host")
            timeout: Default timeout for container operations
        """
        super().__init__()
        self._base_image = base_image
        self._host = host
        self._timeout = timeout
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the adapter and verify Docker is available."""
        if self._initialized:
            return

        try:
            # Check if docker is installed and daemon is reachable
            cmd = ["docker"]
            if self._host:
                cmd.extend(["-H", self._host])
            cmd.append("version")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)

            if proc.returncode != 0:
                raise AdapterInitializationError("Docker daemon not reachable")

            self._initialized = True
        except Exception as e:
            raise AdapterInitializationError(f"Failed to initialize Docker adapter: {e}")

    async def check_availability(self) -> bool:
        """Check if Docker is available."""
        try:
            await self.initialize()
            return True
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
        env: dict[str, str] | None = None,
        working_dir: str | None = None,
    ) -> ContainerHandle:
        """Create and start a Docker container."""
        await self.initialize()

        cmd = ["docker"]
        if self._host:
            cmd.extend(["-H", self._host])
        cmd.extend(["run", "--detach"])

        # Security defaults
        cmd.extend(["--security-opt", "no-new-privileges"])

        if security.read_only_rootfs:
            cmd.append("--read-only")

        for mount in mounts:
            mode = "ro" if mount.read_only else "rw"
            cmd.extend(["--volume", f"{mount.source}:{mount.target}:{mode}"])

        if resources.cpu_cores:
            cmd.extend(["--cpus", str(resources.cpu_cores)])

        if resources.memory_mb:
            cmd.extend(["--memory", f"{resources.memory_mb}m"])

        if network.disabled:
            cmd.extend(["--network", "none"])
        else:
            for port in network.ingress_ports:
                cmd.extend(["--publish", f"{port}:{port}"])

        if env:
            for k, v in env.items():
                cmd.extend(["--env", f"{k}={v}"])

        if working_dir:
            cmd.extend(["--workdir", working_dir])

        if security.user:
            cmd.extend(["--user", security.user])

        cmd.append(image)
        cmd.extend(command)

        stdout, stderr, returncode = await self._run_docker(cmd)
        if returncode != 0:
            raise AdapterOperationError(f"Failed to provision Docker container: {stderr.decode()}")

        container_id = stdout.decode().strip()
        return ContainerHandle(container_id=container_id, image=image)

    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: dict[str, str] | None = None,
        working_dir: str | None = None,
        timeout: float | None = None,
        user: str | None = None,
    ) -> ExecResult:
        """Execute command in Docker container."""
        cmd = ["docker"]
        if self._host:
            cmd.extend(["-H", self._host])
        cmd.extend(["exec"])

        if user:
            cmd.extend(["--user", user])

        if working_dir:
            cmd.extend(["--workdir", working_dir])

        if env:
            for k, v in env.items():
                cmd.extend(["--env", f"{k}={v}"])

        cmd.append(container_id)
        cmd.extend(command)

        stdout, stderr, returncode = await self._run_docker(cmd, timeout=timeout)
        return ExecResult(exit_code=returncode, stdout=stdout.decode(), stderr=stderr.decode())

    async def interactive_exec(
        self,
        container_id: str,
        command: list[str],
        env: dict[str, str] | None = None,
        working_dir: str | None = None,
        user: str | None = None,
    ) -> int:
        """Interactive exec in Docker."""
        cmd = ["docker"]
        if self._host:
            cmd.extend(["-H", self._host])
        cmd.extend(["exec", "-it"])

        if user:
            cmd.extend(["--user", user])
        if working_dir:
            cmd.extend(["--workdir", working_dir])
        if env:
            for k, v in env.items():
                cmd.extend(["--env", f"{k}={v}"])

        cmd.append(container_id)
        cmd.extend(command)

        return subprocess.call(cmd)

    async def copy_from_container(self, container_id: str, src_path: str, dest_path: str) -> None:
        """Copy files from Docker container."""
        cmd = ["docker"]
        if self._host:
            cmd.extend(["-H", self._host])
        cmd.extend(["cp", f"{container_id}:{src_path}", dest_path])

        _, stderr, returncode = await self._run_docker(cmd)
        if returncode != 0:
            raise AdapterOperationError(f"Failed to copy from Docker: {stderr.decode()}")

    async def destroy_container(
        self, container_id: str, force: bool = True, timeout: float | None = None
    ) -> None:
        """Destroy Docker container."""
        cmd = ["docker"]
        if self._host:
            cmd.extend(["-H", self._host])
        cmd.extend(["rm"])
        if force:
            cmd.append("-f")
        cmd.append(container_id)

        await self._run_docker(cmd)

    async def get_container_stats(self, container_id: str) -> ContainerStats:
        """Get stats for Docker container."""
        cmd = ["docker"]
        if self._host:
            cmd.extend(["-H", self._host])
        cmd.extend(["stats", "--no-stream", "--format", "json", container_id])

        stdout, _, returncode = await self._run_docker(cmd)
        if returncode != 0:
            return ContainerStats(0.0, 0.0, 0.0, 0, 0)

        try:
            data = json.loads(stdout.decode())
            # Parse memory usage like "1.23MiB / 7.788GiB"
            mem_use = data.get("MemUsage", "0 / 0").split(" / ")[0]
            mem_limit = data.get("MemUsage", "0 / 0").split(" / ")[1]

            return ContainerStats(
                cpu_percent=float(data.get("CPUPerc", "0").rstrip("%")),
                memory_mb=self._parse_mem(mem_use),
                memory_limit_mb=self._parse_mem(mem_limit),
                network_rx_bytes=0,
                network_tx_bytes=0,
            )
        except Exception:
            return ContainerStats(0.0, 0.0, 0.0, 0, 0)

    def _parse_mem(self, s: str) -> float:
        """Parse Docker memory strings (e.g. 1.2MiB, 10GB)."""
        s = s.strip().upper()
        if not s or s == "0B":
            return 0.0

        units = {
            "B": 1,
            "K": 1024,
            "M": 1024**2,
            "G": 1024**3,
            "T": 1024**4,
            "KI": 1024,
            "MI": 1024**2,
            "GI": 1024**3,
            "TI": 1024**4,
        }

        import re

        match = re.search(r"([0-9.]+)\s*([A-Z]*)", s)
        if not match:
            return 0.0

        val, unit = match.groups()
        return (float(val) * units.get(unit, 1)) / (1024**2)

    async def _run_docker(
        self, cmd: list[str], timeout: float | None = None
    ) -> tuple[bytes, bytes, int]:
        """Internal helper to run Docker commands."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout or self._timeout
            )
            return stdout, stderr, proc.returncode or 0
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError(f"Docker command timed out: {' '.join(cmd)}")

    def get_adapter_name(self) -> str:
        return "Docker"
