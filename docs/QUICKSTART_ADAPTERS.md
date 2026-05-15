# Quick Start Guide: Implementing Adapters

## Overview

This guide provides a step-by-step walkthrough for implementing the adapter pattern in the Isolated Agents SDK. Follow these steps to get started quickly.

## Prerequisites

- Python 3.11+
- Understanding of abstract base classes (ABC)
- Familiarity with async/await patterns
- Access to the SDK codebase

## Step 1: Create Your First Adapter Interface (15 minutes)

### 1.1 Create the Base Adapter Module

```bash
mkdir -p isolated_agents_sdk/adapters
touch isolated_agents_sdk/adapters/__init__.py
touch isolated_agents_sdk/adapters/base.py
touch isolated_agents_sdk/adapters/exceptions.py
touch isolated_agents_sdk/adapters/types.py
```

### 1.2 Define Base Adapter Class

**File**: `isolated_agents_sdk/adapters/base.py`

```python
"""Base adapter interface for all SDK adapters."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAdapter(ABC):
    """Base class for all adapters in the SDK.
    
    Provides common lifecycle methods and configuration management.
    """
    
    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the adapter with optional configuration.
        
        Args:
            config: Adapter-specific configuration dictionary
        """
        self._config = config or {}
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter (connect to services, validate config, etc.)."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up adapter resources (close connections, flush buffers, etc.)."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the adapter is healthy and ready to use.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)
```

### 1.3 Define Adapter Exceptions

**File**: `isolated_agents_sdk/adapters/exceptions.py`

```python
"""Exceptions for adapter operations."""


class AdapterError(Exception):
    """Base exception for all adapter errors."""
    pass


class AdapterNotFoundError(AdapterError):
    """Raised when a requested adapter is not registered."""
    pass


class AdapterConfigurationError(AdapterError):
    """Raised when adapter configuration is invalid."""
    pass


class AdapterInitializationError(AdapterError):
    """Raised when adapter initialization fails."""
    pass


class AdapterOperationError(AdapterError):
    """Raised when an adapter operation fails."""
    pass
```

## Step 2: Implement Container Runtime Adapter (30 minutes)

### 2.1 Create Container Adapter Module

```bash
mkdir -p isolated_agents_sdk/adapters/container
touch isolated_agents_sdk/adapters/container/__init__.py
touch isolated_agents_sdk/adapters/container/base.py
touch isolated_agents_sdk/adapters/container/types.py
```

### 2.2 Define Container Types

**File**: `isolated_agents_sdk/adapters/container/types.py`

```python
"""Type definitions for container runtime adapters."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContainerHandle:
    """Handle to a running container."""
    container_id: str
    image: str
    created_at: str


@dataclass
class ExecResult:
    """Result of executing a command in a container."""
    exit_code: int
    stdout: str
    stderr: str


@dataclass
class ContainerStats:
    """Container resource usage statistics."""
    cpu_percent: float
    memory_mb: float
    memory_limit_mb: float
    network_rx_bytes: int
    network_tx_bytes: int


@dataclass
class Mount:
    """Container mount specification."""
    source: str  # Host path
    target: str  # Container path
    readonly: bool = False


@dataclass
class ResourceLimits:
    """Container resource limits."""
    cpu_cores: float
    memory_mb: int
    memory_swap_mb: Optional[int] = None


@dataclass
class NetworkConfig:
    """Container network configuration."""
    disabled: bool = True
    allowed_endpoints: list[str] = None
    
    def __post_init__(self):
        if self.allowed_endpoints is None:
            self.allowed_endpoints = []


@dataclass
class SecurityConfig:
    """Container security configuration."""
    cap_drop: list[str] = None
    cap_add: list[str] = None
    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    
    def __post_init__(self):
        if self.cap_drop is None:
            self.cap_drop = ["ALL"]
        if self.cap_add is None:
            self.cap_add = []
```

### 2.3 Define Container Adapter Interface

**File**: `isolated_agents_sdk/adapters/container/base.py`

```python
"""Base interface for container runtime adapters."""

from abc import abstractmethod
from typing import Optional

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.container.types import (
    ContainerHandle,
    ContainerStats,
    ExecResult,
    Mount,
    NetworkConfig,
    ResourceLimits,
    SecurityConfig,
)


class ContainerRuntimeAdapter(BaseAdapter):
    """Abstract base class for container runtime adapters.
    
    Implementations must provide methods for container lifecycle management,
    command execution, file operations, and resource monitoring.
    """
    
    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the container runtime is available.
        
        Returns:
            True if runtime is installed and accessible
        """
        pass
    
    @abstractmethod
    async def provision_container(
        self,
        image: str,
        command: list[str],
        mounts: list[Mount],
        resources: ResourceLimits,
        network: NetworkConfig,
        security: SecurityConfig,
        env: Optional[dict[str, str]] = None,
    ) -> ContainerHandle:
        """Create and start a container.
        
        Args:
            image: Container image name
            command: Command to run in container
            mounts: List of volume mounts
            resources: Resource limits
            network: Network configuration
            security: Security settings
            env: Environment variables
            
        Returns:
            Handle to the created container
        """
        pass
    
    @abstractmethod
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
    ) -> ExecResult:
        """Execute a command inside a running container.
        
        Args:
            container_id: Container identifier
            command: Command to execute
            env: Additional environment variables
            working_dir: Working directory for command
            
        Returns:
            Execution result with exit code and output
        """
        pass
    
    @abstractmethod
    async def copy_from_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy a file or directory from container to host.
        
        Args:
            container_id: Container identifier
            src_path: Source path in container
            dest_path: Destination path on host
        """
        pass
    
    @abstractmethod
    async def copy_to_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy a file or directory from host to container.
        
        Args:
            container_id: Container identifier
            src_path: Source path on host
            dest_path: Destination path in container
        """
        pass
    
    @abstractmethod
    async def get_container_stats(
        self,
        container_id: str,
    ) -> ContainerStats:
        """Get resource usage statistics for a container.
        
        Args:
            container_id: Container identifier
            
        Returns:
            Current resource usage statistics
        """
        pass
    
    @abstractmethod
    async def destroy_container(
        self,
        container_id: str,
        force: bool = True,
    ) -> None:
        """Stop and remove a container.
        
        Args:
            container_id: Container identifier
            force: Force removal even if container is running
        """
        pass
```

## Step 3: Implement Podman Adapter (45 minutes)

### 3.1 Create Podman Adapter

**File**: `isolated_agents_sdk/adapters/container/podman.py`

```python
"""Podman container runtime adapter."""

import asyncio
import shutil
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


class PodmanAdapter(ContainerRuntimeAdapter):
    """Podman container runtime adapter.
    
    Implements container operations using Podman CLI.
    """
    
    async def initialize(self) -> None:
        """Initialize the Podman adapter."""
        if not await self.check_availability():
            raise AdapterInitializationError(
                "Podman is not installed or not accessible on PATH"
            )
        self._initialized = True
    
    async def cleanup(self) -> None:
        """Clean up Podman adapter resources."""
        # No persistent resources to clean up
        self._initialized = False
    
    async def health_check(self) -> bool:
        """Check if Podman is healthy."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False
    
    async def check_availability(self) -> bool:
        """Check if Podman is available."""
        return shutil.which("podman") is not None
    
    async def provision_container(
        self,
        image: str,
        command: list[str],
        mounts: list[Mount],
        resources: ResourceLimits,
        network: NetworkConfig,
        security: SecurityConfig,
        env: Optional[dict[str, str]] = None,
    ) -> ContainerHandle:
        """Create and start a Podman container."""
        cmd = self._build_run_command(
            image, command, mounts, resources, network, security, env
        )
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise AdapterOperationError(
                f"Failed to create container: {stderr.decode()}"
            )
        
        container_id = stdout.decode().strip()
        
        return ContainerHandle(
            container_id=container_id,
            image=image,
            created_at="",  # TODO: Get actual creation time
        )
    
    def _build_run_command(
        self,
        image: str,
        command: list[str],
        mounts: list[Mount],
        resources: ResourceLimits,
        network: NetworkConfig,
        security: SecurityConfig,
        env: Optional[dict[str, str]],
    ) -> list[str]:
        """Build the podman run command."""
        cmd = ["podman", "run", "--detach"]
        
        # Resource limits
        cmd.extend([f"--cpus={resources.cpu_cores}"])
        cmd.extend([f"--memory={resources.memory_mb}m"])
        
        # Network
        if network.disabled:
            cmd.append("--network=none")
        else:
            cmd.append("--network=slirp4netns")
        
        # Security
        for cap in security.cap_drop:
            cmd.append(f"--cap-drop={cap}")
        for cap in security.cap_add:
            cmd.append(f"--cap-add={cap}")
        
        if security.read_only_rootfs:
            cmd.append("--read-only")
        
        if security.no_new_privileges:
            cmd.append("--security-opt=no-new-privileges")
        
        # Mounts
        for mount in mounts:
            mode = "ro" if mount.readonly else "rw"
            cmd.extend(["-v", f"{mount.source}:{mount.target}:{mode}"])
        
        # Environment
        if env:
            for key, value in env.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        # Image and command
        cmd.append(image)
        cmd.extend(command)
        
        return cmd
    
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
    ) -> ExecResult:
        """Execute command in Podman container."""
        cmd = ["podman", "exec"]
        
        if env:
            for key, value in env.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        if working_dir:
            cmd.extend(["-w", working_dir])
        
        cmd.append(container_id)
        cmd.extend(command)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        
        return ExecResult(
            exit_code=proc.returncode,
            stdout=stdout.decode(),
            stderr=stderr.decode(),
        )
    
    async def copy_from_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy from Podman container."""
        proc = await asyncio.create_subprocess_exec(
            "podman", "cp",
            f"{container_id}:{src_path}",
            dest_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise AdapterOperationError(
                f"Failed to copy from container: {stderr.decode()}"
            )
    
    async def copy_to_container(
        self,
        container_id: str,
        src_path: str,
        dest_path: str,
    ) -> None:
        """Copy to Podman container."""
        proc = await asyncio.create_subprocess_exec(
            "podman", "cp",
            src_path,
            f"{container_id}:{dest_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise AdapterOperationError(
                f"Failed to copy to container: {stderr.decode()}"
            )
    
    async def get_container_stats(
        self,
        container_id: str,
    ) -> ContainerStats:
        """Get Podman container stats."""
        proc = await asyncio.create_subprocess_exec(
            "podman", "stats", "--no-stream",
            "--format", "{{.CPUPerc}},{{.MemUsage}}",
            container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        
        if proc.returncode != 0:
            raise AdapterOperationError("Failed to get container stats")
        
        # Parse output (simplified)
        line = stdout.decode().strip()
        parts = line.split(",")
        
        cpu_percent = 0.0
        memory_mb = 0.0
        
        if len(parts) >= 2:
            try:
                cpu_percent = float(parts[0].strip().rstrip("%"))
                mem_str = parts[1].strip().split()[0]
                if mem_str.endswith("MiB"):
                    memory_mb = float(mem_str[:-3])
            except ValueError:
                pass
        
        return ContainerStats(
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_limit_mb=0.0,  # TODO: Get from container config
            network_rx_bytes=0,
            network_tx_bytes=0,
        )
    
    async def destroy_container(
        self,
        container_id: str,
        force: bool = True,
    ) -> None:
        """Destroy Podman container."""
        cmd = ["podman", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_id)
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        
        # Don't raise on error - container might already be gone
```

## Step 4: Create Adapter Factory (20 minutes)

**File**: `isolated_agents_sdk/factory.py`

```python
"""Adapter factory for creating and managing adapter instances."""

from typing import Any, Optional, Type

from isolated_agents_sdk.adapters.base import BaseAdapter
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.exceptions import (
    AdapterNotFoundError,
    AdapterConfigurationError,
)


class AdapterFactory:
    """Factory for creating adapter instances."""
    
    _container_adapters: dict[str, Type[ContainerRuntimeAdapter]] = {}
    _instances: dict[str, BaseAdapter] = {}
    
    @classmethod
    def register_container_adapter(
        cls,
        name: str,
        adapter_class: Type[ContainerRuntimeAdapter],
    ) -> None:
        """Register a container runtime adapter.
        
        Args:
            name: Adapter name (e.g., "podman", "docker")
            adapter_class: Adapter class to register
        """
        cls._container_adapters[name] = adapter_class
    
    @classmethod
    async def create_container_adapter(
        cls,
        name: str,
        config: Optional[dict[str, Any]] = None,
        singleton: bool = True,
    ) -> ContainerRuntimeAdapter:
        """Create a container runtime adapter instance.
        
        Args:
            name: Adapter name
            config: Adapter configuration
            singleton: If True, return cached instance
            
        Returns:
            Initialized adapter instance
        """
        cache_key = f"container:{name}"
        
        if singleton and cache_key in cls._instances:
            return cls._instances[cache_key]  # type: ignore
        
        if name not in cls._container_adapters:
            raise AdapterNotFoundError(
                f"Container adapter '{name}' not found. "
                f"Available: {list(cls._container_adapters.keys())}"
            )
        
        adapter_class = cls._container_adapters[name]
        adapter = adapter_class(config=config)
        
        try:
            await adapter.initialize()
        except Exception as e:
            raise AdapterConfigurationError(
                f"Failed to initialize adapter '{name}': {e}"
            ) from e
        
        if singleton:
            cls._instances[cache_key] = adapter
        
        return adapter
    
    @classmethod
    def list_container_adapters(cls) -> list[str]:
        """List registered container adapters."""
        return list(cls._container_adapters.keys())


# Register built-in adapters
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter

AdapterFactory.register_container_adapter("podman", PodmanAdapter)
```

## Step 5: Test Your Adapter (15 minutes)

**File**: `tests/unit/adapters/test_podman_adapter.py`

```python
"""Tests for Podman adapter."""

import pytest
from unittest.mock import AsyncMock, patch

from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.container.types import (
    Mount,
    NetworkConfig,
    ResourceLimits,
    SecurityConfig,
)


@pytest.mark.asyncio
async def test_podman_adapter_initialization():
    """Test Podman adapter initialization."""
    with patch("shutil.which", return_value="/usr/bin/podman"):
        adapter = PodmanAdapter()
        await adapter.initialize()
        assert adapter._initialized is True


@pytest.mark.asyncio
async def test_podman_adapter_health_check():
    """Test Podman adapter health check."""
    adapter = PodmanAdapter()
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        
        result = await adapter.health_check()
        assert result is True


@pytest.mark.asyncio
async def test_podman_adapter_provision_container():
    """Test container provisioning."""
    adapter = PodmanAdapter()
    
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"abc123\n", b"")
        )
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        
        handle = await adapter.provision_container(
            image="python:3.11-slim",
            command=["tail", "-f", "/dev/null"],
            mounts=[Mount(source="/tmp", target="/workspace")],
            resources=ResourceLimits(cpu_cores=1.0, memory_mb=512),
            network=NetworkConfig(disabled=True),
            security=SecurityConfig(),
        )
        
        assert handle.container_id == "abc123"
        assert handle.image == "python:3.11-slim"
```

## Step 6: Integrate with Existing Code (30 minutes)

### 6.1 Update ContainerProvisioner

**File**: `isolated_agents_sdk/container_provisioner.py` (modifications)

```python
# Add at the top
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.factory import AdapterFactory

class ContainerProvisioner:
    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        base_image: str = DEFAULT_IMAGE,
        container_adapter: Optional[ContainerRuntimeAdapter] = None,
    ) -> None:
        self._audit_logger = audit_logger or AuditLogger()
        self._base_image = base_image
        self._container_adapter = container_adapter
    
    async def provision(
        self,
        working_dir: str | Path,
        policy: Policy,
        session_id: str,
        agent_id: str,
    ) -> ContainerHandle:
        # Get or create adapter
        if self._container_adapter is None:
            self._container_adapter = await AdapterFactory.create_container_adapter("podman")
        
        # Use adapter instead of direct Podman calls
        # ... rest of implementation
```

## Next Steps

1. **Implement remaining adapters**: Storage, Audit, Policy
2. **Add configuration system**: YAML + environment variables
3. **Write integration tests**: Test adapter switching
4. **Update documentation**: API docs and examples
5. **Create migration guide**: Help users transition

## Common Pitfalls

1. **Forgetting async/await**: All adapter methods are async
2. **Not handling errors**: Wrap operations in try/except
3. **Skipping initialization**: Always call `initialize()` before use
4. **Ignoring cleanup**: Call `cleanup()` to prevent resource leaks
5. **Hard-coding values**: Use configuration for flexibility

## Getting Help

- Review `docs/ADAPTER_ARCHITECTURE.md` for design details
- Check `docs/IMPLEMENTATION_PLAN.md` for full roadmap
- See `examples/` directory for working examples
- Open an issue on GitHub for questions

---

**Happy Coding!** 🚀