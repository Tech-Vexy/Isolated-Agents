"""Base interface for container runtime adapters."""

from __future__ import annotations

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
    command execution, file operations, and resource monitoring. This interface
    abstracts the underlying container runtime (Podman, Docker, Kubernetes, etc.)
    to enable flexible deployments and easy testing.
    
    Lifecycle:
        1. Initialize adapter
        2. Provision container(s)
        3. Execute commands, copy files, monitor resources
        4. Destroy container(s)
        5. Cleanup adapter
    
    Example:
        >>> adapter = PodmanAdapter()
        >>> await adapter.initialize()
        >>> 
        >>> handle = await adapter.provision_container(
        ...     image="python:3.11-slim",
        ...     command=["tail", "-f", "/dev/null"],
        ...     mounts=[Mount(source="/tmp", target="/workspace")],
        ...     resources=ResourceLimits(cpu_cores=1.0, memory_mb=512),
        ...     network=NetworkConfig(disabled=True),
        ...     security=SecurityConfig(),
        ... )
        >>> 
        >>> result = await adapter.exec_in_container(
        ...     container_id=handle.container_id,
        ...     command=["python", "--version"],
        ... )
        >>> print(result.stdout)
        >>> 
        >>> await adapter.destroy_container(handle.container_id)
        >>> await adapter.cleanup()
    """
    
    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if the container runtime is available.
        
        This method verifies that the container runtime is installed and
        accessible. It should be called before attempting to provision containers.
        
        Returns:
            True if runtime is installed and accessible, False otherwise
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
        working_dir: Optional[str] = None,
    ) -> ContainerHandle:
        """Create and start a container.
        
        This method creates a new container with the specified configuration
        and starts it in detached mode. The container will continue running
        until explicitly destroyed.
        
        Args:
            image: Container image name (e.g., "python:3.11-slim")
            command: Command to run in container (e.g., ["tail", "-f", "/dev/null"])
            mounts: List of volume mounts
            resources: Resource limits (CPU, memory)
            network: Network configuration
            security: Security settings (capabilities, seccomp, etc.)
            env: Environment variables to set in container
            working_dir: Working directory inside container
            
        Returns:
            Handle to the created container
            
        Raises:
            AdapterOperationError: If container creation fails
        """
        pass
    
    @abstractmethod
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[float] = None,
        user: Optional[str] = None,
    ) -> ExecResult:
        """Execute a command inside a running container.
        
        This method runs a command in an existing container and waits for it
        to complete. The command runs in the same environment as the container's
        main process.
        
        Args:
            container_id: Container identifier
            command: Command to execute (e.g., ["python", "script.py"])
            env: Additional environment variables
            working_dir: Working directory for command
            timeout: Maximum seconds to wait for command completion
            user: User to run the command as (e.g. "root")
            
        Returns:
            Execution result with exit code and output
        
        Raises:
            AdapterOperationError: If command execution fails
            TimeoutError: If command exceeds timeout
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
        
        This method copies files from the container filesystem to the host.
        If src_path is a directory, the entire directory tree is copied.
        
        Args:
            container_id: Container identifier
            src_path: Source path in container (absolute path)
            dest_path: Destination path on host
            
        Raises:
            AdapterOperationError: If copy operation fails
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
        
        This method copies files from the host filesystem to the container.
        If src_path is a directory, the entire directory tree is copied.
        
        Args:
            container_id: Container identifier
            src_path: Source path on host
            dest_path: Destination path in container (absolute path)
            
        Raises:
            AdapterOperationError: If copy operation fails
        """
        pass
    
    @abstractmethod
    async def get_container_stats(
        self,
        container_id: str,
    ) -> ContainerStats:
        """Get resource usage statistics for a container.
        
        This method retrieves current CPU and memory usage for a running
        container. The statistics are a snapshot at the time of the call.
        
        Args:
            container_id: Container identifier
            
        Returns:
            Current resource usage statistics
            
        Raises:
            AdapterOperationError: If stats retrieval fails
        """
        pass
    
    @abstractmethod
    async def destroy_container(
        self,
        container_id: str,
        force: bool = True,
        timeout: Optional[float] = None,
    ) -> None:
        """Stop and remove a container.
        
        This method stops a running container and removes it from the system.
        If force=True, the container is killed immediately. Otherwise, it is
        sent a SIGTERM and given time to shut down gracefully.
        
        Args:
            container_id: Container identifier
            force: If True, kill container immediately
            timeout: Seconds to wait for graceful shutdown before killing
            
        Raises:
            AdapterOperationError: If container destruction fails
        """
        pass
    
    async def list_containers(
        self,
        all: bool = False,
    ) -> list[ContainerHandle]:
        """List containers managed by this runtime.
        
        This is an optional method that may be implemented by adapters to
        support container discovery and management.
        
        Args:
            all: If True, include stopped containers
            
        Returns:
            List of container handles
        """
        return []
    
    async def get_container_logs(
        self,
        container_id: str,
        tail: Optional[int] = None,
        follow: bool = False,
    ) -> str:
        """Get logs from a container.
        
        This is an optional method that may be implemented by adapters to
        support log retrieval.
        
        Args:
            container_id: Container identifier
            tail: Number of lines to return from end of logs
            follow: If True, stream logs continuously
            
        Returns:
            Container logs as string
        """
        return ""

# Made with Bob
