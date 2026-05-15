# Architectural Refactoring Guide

## Overview

This guide provides **step-by-step instructions** for refactoring the Isolated Agents SDK to use the adapter pattern. Follow these steps sequentially to maintain backward compatibility while introducing the new architecture.

---

## 🎯 Refactoring Strategy

### **Principles**
1. **Backward Compatibility** - Existing code must continue to work
2. **Incremental Changes** - Small, testable changes
3. **Test-Driven** - Write tests before refactoring
4. **Documentation** - Update docs as you go

### **Approach**
1. Create adapter interfaces alongside existing code
2. Implement adapters that wrap existing functionality
3. Add factory and registry for adapter management
4. Update components to use adapters (with fallback to direct implementation)
5. Deprecate direct implementation
6. Remove deprecated code in next major version

---

## 📋 Phase 1: Container Runtime Adapter (Week 1)

### **Step 1.1: Create Podman Adapter Implementation**

**File:** `isolated_agents_sdk/adapters/container/podman.py`

```python
"""Podman Container Runtime Adapter."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import (
    ContainerHandle,
    ExecResult,
    ContainerStats,
    Mount,
    ResourceLimits,
    NetworkConfig,
    SecurityConfig,
)
from isolated_agents_sdk.adapters.exceptions import (
    AdapterError,
    AdapterOperationError,
    AdapterInitializationError,
)
from isolated_agents_sdk.models import Policy

DEFAULT_IMAGE = "python:3.11-slim"
_PODMAN_TIMEOUT_SECONDS = 300


class PodmanAdapter(ContainerRuntimeAdapter):
    """Podman container runtime adapter.
    
    Wraps Podman CLI commands to provide container lifecycle management.
    """
    
    def __init__(self, base_image: str = DEFAULT_IMAGE):
        """Initialize Podman adapter.
        
        Args:
            base_image: Default container image to use
        """
        super().__init__()
        self._base_image = base_image
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the adapter and verify Podman is available."""
        if self._initialized:
            return
        
        # Check if Podman is installed
        if shutil.which("podman") is None:
            raise AdapterInitializationError(
                "Podman is not installed or not accessible on PATH. "
                "Please install Podman to use this adapter."
            )
        
        # Verify cgroups v2 support
        await self._check_cgroups_v2()
        
        self._initialized = True
    
    async def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if Podman is healthy and accessible."""
        try:
            cmd = ["podman", "version"]
            stdout, stderr, returncode = await self._run_podman(cmd, timeout=5.0)
            return returncode == 0
        except Exception:
            return False
    
    async def provision_container(
        self,
        image: str,
        mounts: list[Mount],
        resource_limits: ResourceLimits,
        network_config: NetworkConfig,
        security_config: SecurityConfig,
        environment: dict[str, str],
        working_dir: Optional[str] = None,
        command: Optional[list[str]] = None,
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
            resource_limits=resource_limits,
            network_config=network_config,
            security_config=security_config,
            environment=environment,
            working_dir=working_dir,
            command=command,
        )
        
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        if returncode != 0:
            raise AdapterOperationError(
                f"Failed to create container (exit {returncode}): {stderr.decode()}"
            )
        
        container_id = stdout.decode().strip()
        return ContainerHandle(container_id=container_id, metadata={"runtime": "podman"})
    
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        working_dir: Optional[str] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> ExecResult:
        """Execute a command in a running container.
        
        Args:
            container_id: Container ID
            command: Command to execute
            working_dir: Working directory for command
            environment: Environment variables
        
        Returns:
            ExecResult with exit code and output
        """
        cmd = ["podman", "exec"]
        
        if working_dir:
            cmd.extend(["--workdir", working_dir])
        
        if environment:
            for key, value in environment.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        cmd.append(container_id)
        cmd.extend(command)
        
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        return ExecResult(
            exit_code=returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )
    
    async def copy_from_container(
        self,
        container_id: str,
        container_path: str,
        host_path: str,
    ) -> None:
        """Copy files from container to host.
        
        Args:
            container_id: Container ID
            container_path: Path inside container
            host_path: Destination path on host
        """
        cmd = ["podman", "cp", f"{container_id}:{container_path}", host_path]
        stdout, stderr, returncode = await self._run_podman(cmd)
        
        if returncode != 0:
            raise AdapterOperationError(
                f"Failed to copy from container: {stderr.decode()}"
            )
    
    async def copy_to_container(
        self,
        container_id: str,
        host_path: str,
        container_path: str,
    ) -> None:
        """Copy files from host to container.
        
        Args:
            container_id: Container ID
            host_path: Source path on host
            container_path: Destination path inside container
        """
        cmd = ["podman", "cp", host_path, f"{container_id}:{container_path}"]
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
        
        import json
        stats_data = json.loads(stdout.decode())[0]
        
        return ContainerStats(
            cpu_percent=float(stats_data.get("CPUPerc", "0").rstrip("%")),
            memory_mb=self._parse_memory(stats_data.get("MemUsage", "0B")),
            memory_limit_mb=self._parse_memory(stats_data.get("MemLimit", "0B")),
            network_rx_bytes=0,  # Not available in basic stats
            network_tx_bytes=0,
        )
    
    async def destroy_container(self, container_id: str, force: bool = True) -> None:
        """Destroy a container.
        
        Args:
            container_id: Container ID
            force: Force removal even if running
        """
        cmd = ["podman", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_id)
        
        await self._run_podman(cmd)
    
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
            uid = getattr(os, "getuid", lambda: 1000)()
            gid = getattr(os, "getgid", lambda: 1000)()
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
            cmd.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
            cmd.extend(["--tmpfs", "/run:rw,noexec,nosuid,size=32m"])
        
        # Network
        if network_config.disabled:
            cmd.append("--network=none")
        else:
            if network_config.allowed_endpoints:
                cmd.append("--network=slirp4netns:allow_host_loopback=false")
                for endpoint in network_config.allowed_endpoints:
                    host = endpoint.split(":")[0]
                    cmd.extend(["--add-host", f"{host}:{host}"])
            else:
                cmd.append("--network=slirp4netns")
        
        # Resources
        cmd.append(f"--cpus={resource_limits.cpu_cores}")
        cmd.append(f"--memory={resource_limits.memory_mb}m")
        cmd.append(f"--memory-swap={resource_limits.memory_mb}m")
        
        shm_size = int(resource_limits.memory_mb * 0.5)
        cmd.append(f"--shm-size={shm_size}m")
        
        # Mounts
        for mount in mounts:
            mode = "ro" if mount.read_only else "rw"
            cmd.extend(["-v", f"{mount.host_path}:{mount.container_path}:{mode}"])
        
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
                proc.kill()
                await proc.wait()
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
```

**Test:** `tests/unit/test_podman_adapter.py`

```python
"""Tests for Podman adapter."""

import pytest
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.container.types import (
    Mount,
    ResourceLimits,
    NetworkConfig,
    SecurityConfig,
)


@pytest.mark.asyncio
async def test_podman_adapter_initialization():
    """Test Podman adapter initializes correctly."""
    adapter = PodmanAdapter()
    await adapter.initialize()
    assert adapter._initialized is True
    await adapter.cleanup()


@pytest.mark.asyncio
async def test_podman_adapter_health_check():
    """Test Podman adapter health check."""
    adapter = PodmanAdapter()
    await adapter.initialize()
    is_healthy = await adapter.health_check()
    assert is_healthy is True
    await adapter.cleanup()


def test_build_run_command():
    """Test building podman run command."""
    adapter = PodmanAdapter()
    
    mounts = [Mount(host_path="/workspace", container_path="/workspace", read_only=False)]
    resource_limits = ResourceLimits(cpu_cores=2.0, memory_mb=1024)
    network_config = NetworkConfig(disabled=True)
    security_config = SecurityConfig(
        user="1000:1000",
        cap_drop=["ALL"],
        cap_add=[],
        read_only_rootfs=True,
    )
    
    cmd = adapter._build_run_command(
        image="python:3.11-slim",
        mounts=mounts,
        resource_limits=resource_limits,
        network_config=network_config,
        security_config=security_config,
        environment={"TEST": "value"},
        working_dir="/workspace",
        command=None,
    )
    
    assert "podman" in cmd
    assert "run" in cmd
    assert "--detach" in cmd
    assert "--network=none" in cmd
    assert "--cpus=2.0" in cmd
    assert "--memory=1024m" in cmd
```

---

### **Step 1.2: Create Adapter Factory**

**File:** `isolated_agents_sdk/adapters/factory.py`

```python
"""Adapter factory for creating adapter instances."""

from __future__ import annotations

from typing import Optional, Type

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.exceptions import AdapterNotFoundError


class AdapterFactory:
    """Factory for creating adapter instances."""
    
    _container_adapters: dict[str, Type[ContainerRuntimeAdapter]] = {
        "podman": PodmanAdapter,
    }
    
    @classmethod
    def create_container_adapter(
        cls,
        adapter_type: str = "podman",
        **kwargs,
    ) -> ContainerRuntimeAdapter:
        """Create a container runtime adapter.
        
        Args:
            adapter_type: Type of adapter ("podman", "docker", "kubernetes")
            **kwargs: Additional arguments for adapter initialization
        
        Returns:
            ContainerRuntimeAdapter instance
        
        Raises:
            AdapterNotFoundError: If adapter type is not registered
        """
        adapter_class = cls._container_adapters.get(adapter_type)
        if adapter_class is None:
            raise AdapterNotFoundError(
                f"Container adapter '{adapter_type}' not found. "
                f"Available adapters: {list(cls._container_adapters.keys())}"
            )
        
        return adapter_class(**kwargs)
    
    @classmethod
    def register_container_adapter(
        cls,
        name: str,
        adapter_class: Type[ContainerRuntimeAdapter],
    ) -> None:
        """Register a custom container adapter.
        
        Args:
            name: Adapter name
            adapter_class: Adapter class
        """
        cls._container_adapters[name] = adapter_class
    
    @classmethod
    def list_container_adapters(cls) -> list[str]:
        """List available container adapters."""
        return list(cls._container_adapters.keys())
```

---

### **Step 1.3: Update ContainerProvisioner to Use Adapter**

**File:** `isolated_agents_sdk/container_provisioner.py` (modified)

Add adapter support while maintaining backward compatibility:

```python
class ContainerProvisioner:
    """Provisions containers using pluggable adapters."""
    
    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        base_image: str = DEFAULT_IMAGE,
        adapter: Optional[ContainerRuntimeAdapter] = None,
    ) -> None:
        self._audit_logger = audit_logger or AuditLogger()
        self._base_image = base_image
        
        # Use provided adapter or create default Podman adapter
        if adapter is None:
            from isolated_agents_sdk.adapters.factory import AdapterFactory
            adapter = AdapterFactory.create_container_adapter("podman", base_image=base_image)
        
        self._adapter = adapter
    
    async def provision(
        self,
        working_dir: str | Path,
        policy: Policy,
        session_id: str,
        agent_id: str,
    ) -> ContainerHandle:
        """Provision a container using the configured adapter."""
        # Initialize adapter if needed
        await self._adapter.initialize()
        
        # Convert policy to adapter parameters
        mounts, resource_limits, network_config, security_config = self._policy_to_adapter_params(policy, working_dir)
        
        # Provision container
        handle = await self._adapter.provision_container(
            image=policy.base_image or self._base_image,
            mounts=mounts,
            resource_limits=resource_limits,
            network_config=network_config,
            security_config=security_config,
            environment=self._build_environment(policy),
            working_dir="/workspace",
            command=None,
        )
        
        # Log event
        self._audit_logger.log_event(
            event_type="container_created",
            session_id=session_id,
            agent_id=agent_id,
            payload={
                "container_id": handle.container_id,
                "image": policy.base_image or self._base_image,
                "working_dir": str(working_dir),
            },
        )
        
        return handle
```

---

## 📝 Summary

This refactoring guide provides:

1. **Complete Podman adapter implementation** - Wraps existing Podman logic
2. **Adapter factory** - Centralized adapter creation
3. **Backward-compatible changes** - Existing code continues to work
4. **Test examples** - Ensure quality

**Next Steps:**
1. Implement the Podman adapter
2. Add tests
3. Update ContainerProvisioner
4. Repeat for other adapter types

---

**See Also:**
- [ADAPTER_ARCHITECTURE.md](ADAPTER_ARCHITECTURE.md) - Architecture design
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Full roadmap
- [IMPLEMENTATION_GAP_ANALYSIS.md](IMPLEMENTATION_GAP_ANALYSIS.md) - What's missing