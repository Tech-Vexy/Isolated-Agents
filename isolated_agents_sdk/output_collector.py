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
import cloudpickle
from pathlib import Path
from typing import Optional, Any

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.storage.base import StorageAdapter
from isolated_agents_sdk.adapters.storage.local import LocalStorageAdapter
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.exceptions import ContainerError, OutputSizeLimitError
from isolated_agents_sdk.models import AgentResult, Policy, CONTAINER_OUTPUT_PATH

# Detect if adapters are available
try:
    from isolated_agents_sdk.adapters.factory import AdapterFactory
    from isolated_agents_sdk.adapters.registry import get_adapter_registry
    _ADAPTERS_AVAILABLE = True
except ImportError:
    _ADAPTERS_AVAILABLE = False

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
        if container_adapter:
            self._container_adapter = container_adapter
        elif _ADAPTERS_AVAILABLE:
            self._container_adapter = get_adapter_registry().get_container_adapter()
        else:
            from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
            self._container_adapter = PodmanAdapter()

        self._storage_adapter = storage_adapter
        if self._storage_adapter is None and _ADAPTERS_AVAILABLE:
            # We don't initialize it here because output_path is needed
            pass

        self._audit_logger = audit_logger or AuditLogger()

    async def collect(
        self,
        container_id: str,
        policy: Policy,
        host_output_path: str | Path,
        exit_code: int,
        session_id: str,
        agent_id: str,
        error: Optional[str] = None,
    ) -> AgentResult:
        """Copy output files and the return value from the container to the host.

        This method performs the following:
        1. Validates the existence of the output directory in the container.
        2. Retrieves the list of files in that directory.
        3. Copies files to the storage provider while enforcing size limits.
        4. Extracts and validates the agent's return value (if any).
        5. Validates the return value against a JSON schema if specified in the policy.

        Args:
            container_id: ID of the container to collect output from.
            policy: The :class:`Policy` that governed the execution.
            host_output_path: Path on the host where files should be stored.
            exit_code: The process exit code of the agent.
            session_id: The session identifier.
            agent_id: The agent identifier.
            error: Optional error message from the runner.

        Returns:
            An :class:`AgentResult` containing the collected artifacts and return value.
        """
        host_output_path = Path(host_output_path)
        output_path_in_container = policy.output_path_in_container
        max_output_bytes = policy.max_output_bytes
        
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
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id, error=error)

        # 2. List regular files only (no symlinks, no directories).
        # We use 'find' via exec.
        find_result = await self._container_adapter.exec_in_container(
            container_id, ["find", output_path_in_container, "-type", "f"]
        )
        if find_result.exit_code != 0:
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id, error=error)

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
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id, error=error)

        # 2b. v0.2.1: Check total size inside container BEFORE copying to host.
        # This prevents host-side resource exhaustion (Disk Spike) from malicious agents.
        size_check_result = await self._container_adapter.exec_in_container(
            container_id, ["du", "-sb", output_path_in_container]
        )
        if size_check_result.exit_code == 0:
            try:
                total_container_size = int(size_check_result.stdout.split()[0])
                if max_output_bytes is not None and total_container_size > max_output_bytes:
                    await self._audit_logger.log_event(
                        event_type="output_size_exceeded",
                        session_id=session_id,
                        agent_id=agent_id,
                        payload={
                            "violation_type": "output_size_exceeded",
                            "attempted_action": "precheck_output_size",
                            "total_bytes": total_container_size,
                            "max_output_bytes": max_output_bytes,
                            "container_id": container_id,
                        },
                    )
                    raise OutputSizeLimitError(
                        f"Projected output size {total_container_size} bytes exceeds limit of {max_output_bytes} bytes.",
                        total_bytes=total_container_size,
                        limit_bytes=max_output_bytes,
                    )
            except (ValueError, IndexError):
                logger.debug("Failed to parse du output, falling back to incremental check")

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
                    await self._audit_logger.log_event(
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

        # 4. Fetch the agent return value (cloudpickle'd)
        agent_output = None
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            
            await self._container_adapter.copy_from_container(
                container_id, CONTAINER_OUTPUT_PATH, str(tmp_path)
            )
            if tmp_path.exists() and tmp_path.stat().st_size > 0:
                with open(tmp_path, "rb") as f:
                    agent_output = cloudpickle.load(f)
        except Exception as e:
            logger.debug("No return value found or Error unpickling result: %s", e)
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass

        # 5. Validate structured output if requested
        if policy.structured_output and agent_output is not None:
            self._validate_structured_output(agent_output, policy.structured_output)

        return AgentResult(
            exit_code=exit_code,
            artifacts=artifacts,
            session_id=session_id,
            output=agent_output,
            error=error,
        )

    def _validate_structured_output(self, output: Any, schema: dict[str, Any]) -> None:
        """Validate the agent's output against a JSON Schema."""
        try:
            from jsonschema import validate
            validate(instance=output, schema=schema)
        except ImportError:
            logger.warning("jsonschema not installed; skipping structured output validation.")
        except Exception as e:
            raise ValueError(f"Agent output failed structured validation: {e}")
