"""Kubernetes Container Runtime Adapter."""

from __future__ import annotations

import asyncio
import json
import uuid
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

class KubernetesAdapter(ContainerRuntimeAdapter):
    """Kubernetes container runtime adapter.
    
    Uses `kubectl` to manage agent execution inside a Kubernetes cluster.
    Each agent session corresponds to a single Pod.
    """
    
    def __init__(
        self, 
        namespace: str = "default",
        context: Optional[str] = None,
        timeout: float = 300,
        **kwargs
    ):
        """Initialize Kubernetes adapter.
        
        Args:
            namespace: Kubernetes namespace to run Pods in
            context: kubectl context to use
            timeout: Default timeout for operations
        """
        super().__init__()
        self._namespace = namespace
        self._context = context
        self._timeout = timeout
        self._initialized = False

    async def initialize(self) -> None:
        """Verify kubectl is available and connected."""
        if self._initialized:
            return
        
        try:
            cmd = ["kubectl"]
            if self._context:
                cmd.extend(["--context", self._context])
            cmd.extend(["version", "--client"])
            
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            
            if proc.returncode != 0:
                raise AdapterInitializationError("kubectl not found or not configured")
                
            self._initialized = True
        except Exception as e:
            raise AdapterInitializationError(f"Failed to initialize Kubernetes adapter: {e}")

    async def check_availability(self) -> bool:
        return await super().check_availability()

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
        """Provision a Pod in Kubernetes."""
        await self.initialize()
        
        pod_name = f"agent-{uuid.uuid4().hex[:8]}"
        
        # Build kubectl run command
        # Note: Kubernetes doesn't support 'tail -f /dev/null' exactly like Podman run
        # We'll use --overrides to specify the Pod spec including resources.
        
        overrides = {
            "spec": {
                "containers": [{
                    "name": "agent",
                    "image": image,
                    "command": ["sleep", "infinity"],  # Keep alive
                    "resources": {
                        "limits": {
                            "cpu": f"{resources.cpu_cores}",
                            "memory": f"{resources.memory_mb}Mi"
                        }
                    },
                    "securityContext": {
                        "readOnlyRootFilesystem": security.read_only_rootfs,
                        "allowPrivilegeEscalation": False,
                    }
                }]
            }
        }
        
        if security.user:
            # Assuming UID:GID format
            if ":" in security.user:
                uid, gid = security.user.split(":")
                overrides["spec"]["containers"][0]["securityContext"]["runAsUser"] = int(uid)
                overrides["spec"]["containers"][0]["securityContext"]["runAsGroup"] = int(gid)
        
        cmd = ["kubectl"]
        if self._context:
            cmd.extend(["--context", self._context])
        cmd.extend([
            "run", pod_name,
            f"--image={image}",
            f"--namespace={self._namespace}",
            "--restart=Never",
            f"--overrides={json.dumps(overrides)}"
        ])
        
        stdout, stderr, returncode = await self._run_kubectl(cmd)
        if returncode != 0:
            raise AdapterOperationError(f"Failed to create Pod: {stderr.decode()}")
            
        # Wait for Pod to be running
        wait_cmd = ["kubectl", "wait", "--for=condition=Ready", f"pod/{pod_name}", f"--namespace={self._namespace}", "--timeout=60s"]
        if self._context: wait_cmd.insert(1, "--context"); wait_cmd.insert(2, self._context)
        
        await self._run_kubectl(wait_cmd)
        
        return ContainerHandle(container_id=pod_name, image=image)

    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[float] = None,
        user: Optional[str] = None,
    ) -> ExecResult:
        """Execute command in Pod."""
        cmd = ["kubectl"]
        if self._context: cmd.extend(["--context", self._context])
        cmd.extend(["exec", "-n", self._namespace, container_id, "--"])
        cmd.extend(command)
        
        stdout, stderr, returncode = await self._run_kubectl(cmd, timeout=timeout)
        return ExecResult(exit_code=returncode, stdout=stdout.decode(), stderr=stderr.decode())

    async def interactive_exec(
        self,
        container_id: str,
        command: list[str],
        env: Optional[dict[str, str]] = None,
        working_dir: Optional[str] = None,
        user: Optional[str] = None,
    ) -> int:
        """Interactive exec in Pod."""
        import subprocess
        cmd = ["kubectl"]
        if self._context: cmd.extend(["--context", self._context])
        cmd.extend(["exec", "-it", "-n", self._namespace, container_id, "--"])
        cmd.extend(command)
        
        return subprocess.call(cmd)

    async def copy_from_container(self, container_id: str, src_path: str, dest_path: str) -> None:
        """Copy from Pod."""
        cmd = ["kubectl"]
        if self._context: cmd.extend(["--context", self._context])
        cmd.extend(["cp", f"{self._namespace}/{container_id}:{src_path}", dest_path])
        
        await self._run_kubectl(cmd)

    async def destroy_container(self, container_id: str, force: bool = True, timeout: Optional[float] = None) -> None:
        """Delete the Pod."""
        cmd = ["kubectl"]
        if self._context: cmd.extend(["--context", self._context])
        cmd.extend(["delete", "pod", container_id, "-n", self._namespace, "--now"])
        
        await self._run_kubectl(cmd)

    async def get_container_stats(self, container_id: str) -> ContainerStats:
        """Get K8s stats (requires metrics-server)."""
        cmd = ["kubectl", "top", "pod", container_id, "-n", self._namespace, "--no-headers"]
        if self._context: cmd.insert(1, "--context"); cmd.insert(2, self._context)
        
        stdout, _, returncode = await self._run_kubectl(cmd)
        if returncode != 0:
            return ContainerStats(0.0, 0.0, 0.0, 0, 0)
            
        try:
            line = stdout.decode().split()
            # Format: NAME CPU(cores) MEMORY(bytes)
            cpu_str = line[1].replace("m", "")
            mem_str = line[2].replace("Mi", "")
            
            return ContainerStats(
                cpu_percent=float(cpu_str) / 10, # rough estimate
                memory_mb=float(mem_str),
                memory_limit_mb=0,
                network_rx_bytes=0,
                network_tx_bytes=0
            )
        except Exception:
            return ContainerStats(0.0, 0.0, 0.0, 0, 0)

    async def _run_kubectl(self, cmd: list[str], timeout: Optional[float] = None) -> tuple[bytes, bytes, int]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout or self._timeout)
            return stdout, stderr, proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError("kubectl component timed out")

    def get_adapter_name(self) -> str:
        return "Kubernetes"
