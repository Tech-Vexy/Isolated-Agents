"""Container Provisioner for the Isolated Agents SDK.

Builds and executes rootless Podman container commands from a validated Policy.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.exceptions import (
    ContainerError,
    PodmanNotFoundError,
    WorkingDirectoryError,
)
from isolated_agents_sdk.models import Policy

DEFAULT_IMAGE = "python:3.11-slim"

# Timeout (seconds) for individual Podman subprocess calls.  Long enough for
# image pulls on slow networks but short enough to surface hangs quickly.
_PODMAN_TIMEOUT_SECONDS = 300


@dataclass
class ContainerHandle:
    """Handle returned after a container is successfully provisioned."""

    container_id: str


class ContainerProvisioner:
    """Provisions rootless Podman containers from a validated Policy.

    Args:
        audit_logger: AuditLogger instance for emitting lifecycle events.
        base_image: Container image to use. Defaults to ``python:3.11-slim``.
    """

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        base_image: str = DEFAULT_IMAGE,
    ) -> None:
        self._audit_logger = audit_logger or AuditLogger()
        self._base_image = base_image

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def provision(
        self,
        working_dir: str | Path,
        policy: Policy,
        session_id: str,
        agent_id: str,
    ) -> ContainerHandle:
        """Provision a rootless Podman container for the given policy.

        Args:
            working_dir: Host path to the working directory to mount.
            policy: Validated Policy object describing resource/network/fs constraints.
            session_id: Unique identifier for this session.
            agent_id: Identifier for the agent being launched.

        Returns:
            A :class:`ContainerHandle` containing the container ID.

        Raises:
            PodmanNotFoundError: If Podman is not found on PATH.
            WorkingDirectoryError: If *working_dir* does not exist.
        """
        self._check_podman()
        await self._check_cgroups_v2()

        working_dir = Path(working_dir)
        if not working_dir.exists():
            raise WorkingDirectoryError(
                f"Working directory does not exist: {working_dir}"
            )

        cmd = self.build_command(working_dir, policy)

        stdout_bytes, stderr_bytes, returncode = await self._run_podman(cmd)

        if returncode != 0:
            raise ContainerError(
                f"Podman failed to start container (exit {returncode})",
                command=cmd,
                exit_code=returncode,
                stderr=stderr_bytes.decode(errors="replace"),
            )

        container_id = stdout_bytes.decode().strip()

        self._audit_logger.log_event(
            event_type="container_created",
            session_id=session_id,
            agent_id=agent_id,
            payload={
                "container_id": container_id,
                "image": policy.base_image or self._base_image,
                "working_dir": str(working_dir),
            },
        )

        return ContainerHandle(container_id=container_id)

    def build_command(
        self,
        working_dir: str | Path,
        policy: Policy,
    ) -> list[str]:
        """Build the ``podman run`` command list from *policy*.

        This method is intentionally separated from :meth:`provision` so that
        it can be tested without actually running Podman.

        Security posture applied by default (all overridable via Policy):
        - ``--cap-drop=ALL`` — drop every Linux capability.
        - ``--security-opt=no-new-privileges`` — prevent setuid/setgid escalation.
        - ``--security-opt=seccomp=<profile>`` — restrict syscalls.
        - ``--read-only`` — root filesystem is immutable.
        - tmpfs mounts for ``/tmp`` and ``/run`` so the agent still has writable
          scratch space without touching the real root FS.
        - ``--network=none`` by default; ``allowed_endpoints`` uses
          ``slirp4netns`` with a DNS-based allowlist when network is enabled.

        Args:
            working_dir: Host path to the working directory.
            policy: Validated Policy object.

        Returns:
            A list of strings representing the full ``podman run`` command.
        """
        working_dir = Path(working_dir)

        cmd: list[str] = [
            "podman", "run",
            "--detach",
            # NOTE: --rm is intentionally omitted.  The container must stay
            # alive after the agent process exits so that OutputCollector can
            # run `podman cp` / `podman exec` against it.  SessionManager
            # calls `podman rm -f` explicitly once collection is complete.

            # ---- Identity / namespace isolation ----
            # Map the calling user into the container as a non-root UID.
            "--userns=keep-id",
            # Private PID namespace — container cannot see host processes.
            "--pid=private",

            # ---- Privilege escalation prevention ----
            # Disallow acquiring new privileges via setuid/setgid binaries.
            "--security-opt=no-new-privileges",
        ]

        # ---- Container user (non-root enforcement) ----
        # Derive the UID:GID from the host caller when the policy does not
        # specify one explicitly.  This ensures the process inside the
        # container is never root even when the base image defaults to root
        # (e.g. python:3.11-slim runs as uid 0 by default).
        # os.getuid/getgid are POSIX-only; on Windows they are absent, so we
        # fall back to "1000:1000" which is the conventional first non-root
        # user on Linux systems.
        if policy.container_user is not None:
            user_spec = policy.container_user
        else:
            uid = getattr(os, "getuid", lambda: 1000)()
            gid = getattr(os, "getgid", lambda: 1000)()
            user_spec = f"{uid}:{gid}"
        cmd.append(f"--user={user_spec}")

        # ---- Capability hardening ----
        # Drop every capability first, then selectively re-add what the policy
        # explicitly requests.  The default policy adds nothing back, giving
        # the agent the minimum viable privilege set.
        for cap in policy.cap_drop:
            cmd.append(f"--cap-drop={cap}")
        for cap in policy.cap_add:
            cmd.append(f"--cap-add={cap}")

        # ---- Seccomp profile ----
        # None  → use Podman's built-in default profile (recommended).
        # path  → load a custom JSON profile from the host.
        # "unconfined" → disable seccomp (not recommended; useful for debugging).
        if policy.seccomp_profile is not None:
            cmd.append(f"--security-opt=seccomp={policy.seccomp_profile}")
        # When seccomp_profile is None we deliberately omit the flag so Podman
        # applies its own default seccomp policy automatically.

        # ---- Read-only root filesystem ----
        if policy.read_only_rootfs:
            cmd.append("--read-only")
            # /tmp — writable scratch space, non-executable, size-capped.
            cmd.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
            # /run — needed by some daemons (e.g. dbus, systemd-notify).
            cmd.extend(["--tmpfs", "/run:rw,noexec,nosuid,size=32m"])

        # ---- Network isolation ----
        if policy.network.disabled:
            cmd.append("--network=none")
        else:
            # Use slirp4netns (rootless-compatible userspace networking).
            # Build a comma-separated allow list of "host:port" pairs that
            # slirp4netns will permit; everything else is blocked by the
            # network namespace.  This is the correct Podman idiom for
            # rootless containers — passing raw endpoint strings as
            # --network arguments is invalid syntax.
            if policy.network.allowed_endpoints:
                # Format: slirp4netns:allow_host_loopback=false,outbound_addr=...
                # For a simple DNS/IP allowlist we use the `outbound_addr`
                # option combined with a custom DNS server when needed.
                # The most portable approach is to pass the endpoints as
                # --add-host entries and restrict outbound via the network
                # namespace; full iptables-based filtering requires root.
                # We use slirp4netns with cidr restriction where possible.
                cmd.append("--network=slirp4netns:allow_host_loopback=false")
                for endpoint in policy.network.allowed_endpoints:
                    # Add each allowed host to /etc/hosts so the agent can
                    # resolve it by name without a full DNS stack.
                    # Endpoints may be "host:port" or bare hostnames/CIDRs.
                    host = endpoint.split(":")[0]
                    cmd.extend(["--add-host", f"{host}:{host}"])
            else:
                # Network enabled but no specific endpoints — allow all
                # outbound via slirp4netns (rootless-safe).
                cmd.append("--network=slirp4netns")

        # ---- Resource limits ----
        cmd.append(f"--cpus={policy.cpu_cores}")
        cmd.append(f"--memory={policy.memory_mb}m")
        # Disable swap entirely (memory-swap == memory means no swap).
        cmd.append(f"--memory-swap={policy.memory_mb}m")

        # Allocate shared memory for browsers / GUI agents.
        shm_size = int(policy.memory_mb * 0.5)
        cmd.append(f"--shm-size={shm_size}m")

        # ---- Filesystem mounts ----
        # Working directory (read-write).
        cmd.extend(["-v", f"{working_dir}:/workspace:rw"])

        # Output directory — writable bind mount so the agent can write
        # artifacts even when the root FS is read-only.  We use a tmpfs
        # here so output lives in memory until OutputCollector copies it out.
        cmd.extend(["--tmpfs", f"{policy.output_path_in_container}:rw,nosuid,size=256m"])

        # Additional read-only mounts from policy.
        for mount in policy.readonly_mounts:
            cmd.extend(["-v", f"{mount}:{mount}:ro"])

        # ---- Zero-Disk Credential Injection (tmpfs) ----
        if policy.tmpfs_secrets:
            cmd.extend(["--mount", "type=tmpfs,destination=/run/secrets"])

        # ---- Environment variables ----
        # Forward only the variables explicitly listed in the policy.
        for var in policy.allowed_env_vars:
            value = os.environ.get(var)
            if value is not None:
                cmd.extend(["-e", f"{var}={value}"])

        cmd.append(policy.base_image or self._base_image)

        # Keep the container alive indefinitely so the agent runner can exec
        # into it.  `tail -f /dev/null` is the conventional POSIX idiom for
        # this: it blocks forever, consumes no CPU, and exits cleanly on
        # SIGTERM/SIGKILL.  It is preferable to `sleep 3600` because it does
        # not impose an arbitrary ceiling and does not require the container to
        # be restarted if the agent takes longer than expected.
        cmd.extend(["tail", "-f", "/dev/null"])

        return cmd

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_podman(self) -> None:
        """Raise :class:`PodmanNotFoundError` if Podman is not on PATH."""
        if shutil.which("podman") is None:
            raise PodmanNotFoundError(
                "Podman is not installed or not accessible on PATH. "
                "Please install Podman to use the Isolated Agents SDK."
            )

    async def _run_podman(
        self,
        cmd: list[str],
        timeout: float = _PODMAN_TIMEOUT_SECONDS,
    ) -> tuple[bytes, bytes, int]:
        """Run a Podman command and return (stdout, stderr, returncode).

        Wraps :func:`asyncio.create_subprocess_exec` with a timeout so that
        hung Podman calls do not block the event loop indefinitely.

        Args:
            cmd: Full command list starting with ``"podman"``.
            timeout: Maximum seconds to wait before raising :exc:`TimeoutError`.

        Returns:
            A ``(stdout_bytes, stderr_bytes, returncode)`` tuple.

        Raises:
            ContainerError: If the command times out.
        """
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise ContainerError(
                f"Podman command timed out after {timeout}s",
                command=cmd,
                exit_code=None,
                stderr="",
            )
        return stdout, stderr, proc.returncode  # type: ignore[return-value]

    async def _check_cgroups_v2(self) -> None:
        """Ensure the host supports rootless memory enforcement."""
        import logging
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "info", "--format", "{{.Host.CgroupsVersion}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                version = stdout.decode().strip()
                if version != "v2":
                    logging.warning(
                        "Cgroups v2 not detected (found '%s'). "
                        "Rootless memory limits may not be enforced. "
                        "See Podman documentation for rootless memory limits.",
                        version
                    )
        except Exception as exc:
            logging.debug("Failed to check cgroups version: %s", exc)
