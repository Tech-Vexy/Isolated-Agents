"""Output Collector for the Isolated Agents SDK.

Copies output files from a container to the host after agent execution,
enforcing the Policy's max_output_bytes limit.

Design notes
------------
- Files are copied one at a time via ``podman cp`` into a temporary staging
  directory, with the running total checked against ``max_output_bytes`` after
  each file.  This avoids doubling peak disk usage by staging the entire output
  tree before checking the limit.
- Symlinks inside the container output directory are **not** followed.  Only
  regular files are transferred.  This prevents a malicious agent from using
  symlinks to exfiltrate host files that happen to be accessible inside the
  container.
- The file listing is obtained via ``podman exec find`` rather than
  ``podman cp`` + ``rglob``, so we know the exact set of regular files before
  any data is transferred.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.local import LocalStorageAdapter
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.exceptions import ContainerError, OutputSizeLimitError
from isolated_agents_sdk.models import AgentResult

logger = logging.getLogger(__name__)

class OutputCollector:
    """Collects output artifacts from a container after agent execution.

    Args:
        container_adapter: ContainerRuntimeAdapter instance.
        storage_adapter: StorageAdapter instance.
        audit_logger: AuditLogger instance for emitting lifecycle events.
    """

    def __init__(
        self,
        container_adapter: Optional[ContainerRuntimeAdapter] = None,
        storage_adapter: Optional[StorageAdapter] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._container_adapter = container_adapter or PodmanAdapter()
        self._storage_adapter = storage_adapter  # Late initialization in collect() if None
        self._audit_logger = audit_logger or AuditLogger()

    async def collect(
        self,
        container_id: str,
        output_path_in_container: str,
        host_output_path: str | Path,
        max_output_bytes: Optional[int],
        exit_code: int,
        session_id: str,
        agent_id: str,
    ) -> AgentResult:
        """Copy output files from the container to the host."""
        host_output_path = Path(host_output_path)
        
        # Initialize storage adapter if not provided
        if self._storage_adapter is None:
            self._storage_adapter = LocalStorageAdapter(base_path=host_output_path)
        
        await self._storage_adapter.initialize()

        # 1. Check whether the output directory exists inside the container.
        # We use 'ls -d' or 'test -d' via exec.
        result = await self._container_adapter.exec_in_container(
            container_id, ["test", "-d", output_path_in_container]
        )
        if result.exit_code != 0:
            logger.warning(
                "Output path '%s' does not exist in container '%s'; "
                "returning empty artifacts.",
                output_path_in_container,
                container_id,
            )
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id)

        # 2. List regular files only (no symlinks, no directories).
        # We use 'find' via exec.
        find_result = await self._container_adapter.exec_in_container(
            container_id, ["find", output_path_in_container, "-type", "f"]
        )
        if find_result.exit_code != 0:
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id)

        relative_paths = []
        prefix = output_path_in_container.rstrip("/") + "/"
        for line in find_result.stdout.splitlines():
            full = line.strip()
            if not full:
                continue
            if full.startswith(prefix):
                rel = full[len(prefix):]
            else:
                rel = full
            if rel:
                relative_paths.append(rel)

        if not relative_paths:
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id)

        # 3. Copy files one at a time, checking the size limit on the fly.
        host_output_path.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, str] = {}
        total_bytes = 0

        with tempfile.TemporaryDirectory(prefix="agent_output_stage_") as stage_dir:
            for rel in relative_paths:
                container_src = f"{output_path_in_container}/{rel}"
                stage_file = Path(stage_dir) / rel.replace("/", "_")

                await self._container_adapter.copy_from_container(
                    container_id, container_src, str(stage_file)
                )

                if not stage_file.exists():
                    continue

                file_size = stage_file.stat().st_size
                total_bytes += file_size

                if max_output_bytes is not None and total_bytes > max_output_bytes:
                    self._audit_logger.log_event(
                        event_type="output_size_exceeded",
                        session_id=session_id,
                        agent_id=agent_id,
                        payload={
                            "violation_type": "output_size_exceeded",
                            "attempted_action": f"copy {total_bytes} bytes from container",
                            "total_bytes": total_bytes,
                            "max_output_bytes": max_output_bytes,
                            "container_id": container_id,
                        },
                    )
                    raise OutputSizeLimitError(
                        f"Output size {total_bytes} bytes exceeds limit of {max_output_bytes} bytes.",
                        total_bytes=total_bytes,
                        limit_bytes=max_output_bytes,
                    )

                # Store via StorageAdapter
                data = stage_file.read_bytes()
                location = await self._storage_adapter.store_artifact(
                    session_id=session_id,
                    artifact_name=rel,
                    data=data,
                )
                
                # Maintain backward compatibility: return local path if possible
                artifacts[rel] = location.path or str(location.url)

        return AgentResult(exit_code=exit_code, artifacts=artifacts, session_id=session_id)
