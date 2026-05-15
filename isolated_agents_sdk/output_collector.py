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

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.exceptions import ContainerError, OutputSizeLimitError
from isolated_agents_sdk.models import AgentResult

logger = logging.getLogger(__name__)

# Maximum seconds to wait for a single podman cp / podman exec call.
_COPY_TIMEOUT = 120


class OutputCollector:
    """Collects output artifacts from a container after agent execution.

    Args:
        audit_logger: AuditLogger instance for emitting lifecycle events.
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None) -> None:
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
        """Copy output files from the container to the host.

        Only regular files are transferred — symlinks are silently skipped to
        prevent container-escape via symlink chains.  The running byte total is
        checked after each file so that ``max_output_bytes`` is enforced without
        staging the entire output tree first.

        Args:
            container_id: The running or stopped container ID.
            output_path_in_container: Path inside the container where output
                files live.
            host_output_path: Destination directory on the host.
            max_output_bytes: Maximum total bytes allowed; ``None`` means
                unlimited.
            exit_code: The agent process exit code to include in the result.
            session_id: Session identifier for audit events.
            agent_id: Agent identifier for audit events.

        Returns:
            An :class:`AgentResult` with the exit code and collected artifacts.

        Raises:
            OutputSizeLimitError: If total output size exceeds
                *max_output_bytes*.
            ContainerError: If a ``podman`` subprocess call fails unexpectedly.
        """
        host_output_path = Path(host_output_path)

        # ------------------------------------------------------------------ #
        # 1. Check whether the output directory exists inside the container.  #
        # ------------------------------------------------------------------ #
        exists = await self._path_exists_in_container(
            container_id, output_path_in_container
        )
        if not exists:
            logger.warning(
                "Output path '%s' does not exist in container '%s'; "
                "returning empty artifacts.",
                output_path_in_container,
                container_id,
            )
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id)

        # ------------------------------------------------------------------ #
        # 2. List regular files only (no symlinks, no directories).           #
        # ------------------------------------------------------------------ #
        relative_paths = await self._list_regular_files(
            container_id, output_path_in_container
        )

        if not relative_paths:
            return AgentResult(exit_code=exit_code, artifacts={}, session_id=session_id)

        # ------------------------------------------------------------------ #
        # 3. Copy files one at a time, checking the size limit on the fly.   #
        # ------------------------------------------------------------------ #
        host_output_path.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, str] = {}
        total_bytes = 0

        with tempfile.TemporaryDirectory(prefix="agent_output_stage_") as stage_dir:
            for rel in relative_paths:
                container_src = f"{output_path_in_container}/{rel}"
                # Flatten into a safe local filename for staging; the final
                # destination preserves the original relative path.
                stage_file = Path(stage_dir) / rel.replace("/", "_")

                await self._copy_file_from_container(
                    container_id, container_src, str(stage_file)
                )

                if not stage_file.exists():
                    # podman cp succeeded but produced no file — skip silently.
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
                            "attempted_action": (
                                f"copy {total_bytes} bytes from container output path"
                            ),
                            "total_bytes": total_bytes,
                            "max_output_bytes": max_output_bytes,
                            "container_id": container_id,
                            "output_path_in_container": output_path_in_container,
                        },
                    )
                    raise OutputSizeLimitError(
                        f"Output size {total_bytes} bytes exceeds limit of "
                        f"{max_output_bytes} bytes.",
                        total_bytes=total_bytes,
                        limit_bytes=max_output_bytes,
                    )

                # Move staged file to its final destination.
                dest = host_output_path / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest.unlink()
                shutil.move(str(stage_file), str(dest))

                # Use forward slashes for cross-platform consistency.
                artifacts[Path(rel).as_posix()] = str(dest)

        return AgentResult(exit_code=exit_code, artifacts=artifacts, session_id=session_id)

    # ---------------------------------------------------------------------- #
    # Internal helpers                                                        #
    # ---------------------------------------------------------------------- #

    async def _path_exists_in_container(
        self, container_id: str, path: str
    ) -> bool:
        """Return ``True`` if *path* is a directory inside *container_id*."""
        proc = await asyncio.create_subprocess_exec(
            "podman", "exec", container_id, "test", "-d", path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=_COPY_TIMEOUT)
        except asyncio.TimeoutError:
            return False
        return proc.returncode == 0

    async def _list_regular_files(
        self, container_id: str, output_path: str
    ) -> list[str]:
        """Return a list of regular-file paths relative to *output_path*.

        Uses ``find -type f`` inside the container so that symlinks are
        excluded at the source.  Paths are returned with forward slashes and
        no leading ``./``.
        """
        proc = await asyncio.create_subprocess_exec(
            "podman", "exec", container_id,
            "find", output_path, "-type", "f",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=_COPY_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out listing files in container '%s' at '%s'",
                container_id, output_path,
            )
            return []

        if proc.returncode != 0:
            return []

        relative: list[str] = []
        prefix = output_path.rstrip("/") + "/"
        for line in stdout.decode(errors="replace").splitlines():
            full = line.strip()
            if not full:
                continue
            if full.startswith(prefix):
                rel = full[len(prefix):]
            else:
                rel = full
            if rel:
                relative.append(rel)
        return relative

    async def _copy_file_from_container(
        self, container_id: str, container_path: str, host_path: str
    ) -> None:
        """Copy a single file from the container to *host_path*.

        Raises:
            ContainerError: If ``podman cp`` exits non-zero.
        """
        cmd = ["podman", "cp", f"{container_id}:{container_path}", host_path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_COPY_TIMEOUT
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise ContainerError(
                f"podman cp timed out copying '{container_path}' from container "
                f"'{container_id}'",
                command=cmd,
                exit_code=None,
                stderr="",
            )

        if proc.returncode != 0:
            raise ContainerError(
                f"podman cp failed copying '{container_path}' from container "
                f"'{container_id}' (exit {proc.returncode})",
                command=cmd,
                exit_code=proc.returncode,
                stderr=stderr.decode(errors="replace"),
            )
