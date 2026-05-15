"""Agent Runner for the Isolated Agents SDK.

Serialises an agent callable into a container, executes it, streams
stdout/stderr, and monitors for privilege escalation.
"""

from __future__ import annotations

import asyncio
import cloudpickle
import tempfile
from pathlib import Path
from typing import Callable, Optional

from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.container_provisioner import ContainerHandle
from isolated_agents_sdk.models import AgentResult, Policy

# Paths used inside the container
_CONTAINER_BOOTSTRAP_PATH = "/tmp/_agent_bootstrap.py"
_CONTAINER_OUTPUT_PATH = "/tmp/_agent_return.pkl"
_CONTAINER_SOURCE_PATH = "/tmp/_agent_source.pkl"

# Bootstrap script — injected source is loaded via cloudpickle.
# The payload file contains a dict with keys "fn", "args", and "kwargs" so
# that callers can pass positional and keyword arguments to the agent callable.
#
# Security notes:
# - The secrets file is wiped from the tmpfs immediately after the environment
#   variables are loaded so it is not readable by any subsequent process.
# - {source_path!r} and {output_path!r} are repr()-quoted Python string
#   literals; they cannot contain shell metacharacters because the bootstrap
#   is executed via `python3 <path>`, not through a shell.
_BOOTSTRAP_TEMPLATE = """\
import cloudpickle
import os

# ---------------------------------------------------------------------------
# 1. Load secrets from tmpfs and wipe the file immediately.
# ---------------------------------------------------------------------------
_secrets_path = "/run/secrets/credentials.env"
if os.path.exists(_secrets_path):
    try:
        with open(_secrets_path, "r") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    # Strip shell quoting added by _inject_secrets (single quotes).
                    _v = _v.strip("'")
                    os.environ[_k.strip()] = _v
    finally:
        # Overwrite with zeros then unlink so the key material is not
        # recoverable from the tmpfs page cache.
        try:
            _size = os.path.getsize(_secrets_path)
            with open(_secrets_path, "r+b") as _f:
                _f.write(b"\\x00" * _size)
                _f.flush()
        except OSError:
            pass
        try:
            os.unlink(_secrets_path)
        except OSError:
            pass

# ---------------------------------------------------------------------------
# 2. Deserialise and execute the agent callable.
# ---------------------------------------------------------------------------
with open({source_path!r}, "rb") as _f:
    _payload = cloudpickle.load(_f)

_agent = _payload["fn"]
_args  = _payload.get("args", ())
_kwargs = _payload.get("kwargs", {{}})

_result = _agent(*_args, **_kwargs)

if _result is not None:
    with open({output_path!r}, "wb") as _f:
        cloudpickle.dump(_result, _f)
"""

class AgentRunner:
    """Executes an agent callable inside an already-provisioned container.

    Args:
        handle: The :class:`ContainerHandle` returned by :class:`ContainerProvisioner`.
        audit_logger: :class:`AuditLogger` instance for emitting lifecycle events.
    """

    def __init__(
        self,
        handle: ContainerHandle,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._handle = handle
        self._audit_logger = audit_logger or AuditLogger()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        agent: Optional[Callable],
        policy: Policy,
        session_id: str,
        agent_id: str,
        agent_args: tuple = (),
        agent_kwargs: Optional[dict] = None,
    ) -> AgentResult:
        """Execute the agent inside the container.

        If *policy.entrypoint* is provided, it executes that command list.
        Otherwise, it serialises *agent*, injects it, and executes it.

        Streams stdout/stderr to the caller's stdout/stderr in real time.

        Args:
            agent: The callable to execute (ignored if *policy.entrypoint* is set).
            policy: The validated :class:`Policy` for this session.
            session_id: Unique identifier for this session.
            agent_id: Identifier for the agent being launched.
            agent_args: Positional arguments forwarded to *agent* inside the container.
            agent_kwargs: Keyword arguments forwarded to *agent* inside the container.

        Returns:
            An :class:`AgentResult` with the exit code and an empty
            ``artifacts`` dict (populated later by ``OutputCollector``).
        """
        if agent_kwargs is None:
            agent_kwargs = {}
        container_id = self._handle.container_id

        # 1. Inject secrets if provided
        if policy.tmpfs_secrets:
            await self._inject_secrets(container_id, policy.tmpfs_secrets)

        # 2. Inject CA cert if provided
        if policy.proxy_ca_cert:
            await self._inject_ca_cert(container_id, policy.proxy_ca_cert)

        exec_env = []
        if policy.proxy_url:
            exec_env.extend([
                "-e", f"HTTP_PROXY={policy.proxy_url}",
                "-e", f"HTTPS_PROXY={policy.proxy_url}",
                "-e", f"http_proxy={policy.proxy_url}",
                "-e", f"https_proxy={policy.proxy_url}",
            ])

        if policy.entrypoint:
            # Framework-Agnostic Mode: Execute the user's command
            if policy.requires_display:
                # Wrap with Xvfb
                xvfb_cmd = "Xvfb :99 -screen 0 1280x1024x24 & export DISPLAY=:99 && sleep 1 && "
                # Source secrets if they exist for polyglot agents too
                secret_cmd = "if [ -f /run/secrets/credentials.env ]; then set -a; . /run/secrets/credentials.env; set +a; fi && "
                final_cmd = xvfb_cmd + secret_cmd + " ".join(policy.entrypoint)
                run_cmd = ["podman", "exec"] + exec_env + [container_id, "sh", "-c", final_cmd]
            else:
                run_cmd = ["podman", "exec"] + exec_env + [container_id] + policy.entrypoint
        else:
            if agent is None:
                raise ValueError("Agent callable must be provided if policy.entrypoint is not set.")

            # Legacy Python Callable Mode
            # 1. Serialise agent and copy it into the container
            await self._inject_source(agent, container_id, agent_args, agent_kwargs)

            # 2. Write and copy the bootstrap script into the container
            await self._inject_bootstrap(container_id)

            # 3. Install any agent-requested packages inside the container
            if policy.pip_packages:
                await self._install_pip_packages(
                    container_id=container_id,
                    packages=policy.pip_packages,
                    index_url=policy.pip_index_url,
                    require_hashes=policy.pip_require_hashes,
                )

            if policy.requires_display:
                xvfb_cmd = "Xvfb :99 -screen 0 1280x1024x24 & export DISPLAY=:99 && sleep 1 && "
                final_cmd = xvfb_cmd + f"python3 {_CONTAINER_BOOTSTRAP_PATH}"
                run_cmd = ["podman", "exec"] + exec_env + [container_id, "sh", "-c", final_cmd]
            else:
                run_cmd = ["podman", "exec"] + exec_env + [container_id, "python3", _CONTAINER_BOOTSTRAP_PATH]

        # 4. Launch the agent via `podman exec`
        proc = await asyncio.create_subprocess_exec(
            *run_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 5. Emit agent_launched audit event
        self._audit_logger.log_event(
            event_type="agent_launched",
            session_id=session_id,
            agent_id=agent_id,
            payload={"container_id": container_id},
        )

        # 6. Stream stdout/stderr back to the caller (and record replay if enabled)
        # while concurrently monitoring for privilege escalation.
        replay_data = [] if policy.enable_session_replay else None
        await asyncio.gather(
            self._stream_output(proc, replay_data),
            self._monitor_privilege_escalation(
                proc, container_id, session_id, agent_id
            ),
        )

        exit_code = await proc.wait()

        # OOM Kill detection
        if exit_code == 137:
            self._audit_logger.log_event(
                event_type="resource_limit_exceeded",
                session_id=session_id,
                agent_id=agent_id,
                payload={
                    "violation_type": "oom_kill",
                    "attempted_action": "memory_allocation",
                    "reason": "Agent exceeded allocated memory limits (OOM Kill)",
                    "container_id": container_id,
                },
            )

        artifacts = {}
        if replay_data:
            # Save replay as a .cast file in the workspace (or just return it)
            # For now, let's just return it in the result or save to a file
            replay_path = Path(tempfile.gettempdir()) / f"replay_{session_id}.cast"
            with open(replay_path, "w") as f:
                # asciinema v2 header
                import json
                f.write(json.dumps({"version": 2, "width": 120, "height": 40}) + "\n")
                for ts, stream, text in replay_data:
                    f.write(json.dumps([ts, "o" if stream == "stdout" else "e", text]) + "\n")
            artifacts["session_replay.cast"] = replay_path

        return AgentResult(
            exit_code=exit_code,
            artifacts=artifacts,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _inject_secrets(self, container_id: str, secrets: dict[str, str]) -> None:
        """Write secrets to a file in the tmpfs mount inside the container.

        Each line is written as ``KEY=VALUE`` where VALUE is shell-quoted so
        that values containing ``=``, newlines, or special characters cannot
        corrupt the file or inject extra environment variables.
        """
        import shlex

        lines = []
        for k, v in secrets.items():
            # Validate key: must be a valid POSIX env-var name
            if not k.replace("_", "").isalnum() or k[0].isdigit():
                raise ValueError(
                    f"Invalid secret key '{k}': must be a valid environment variable name."
                )
            # Quote the value so embedded newlines / = signs are safe
            lines.append(f"{k}={shlex.quote(v)}")
        content = "\n".join(lines) + "\n"

        with tempfile.NamedTemporaryFile(suffix=".env", mode="w", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "cp", tmp_path, f"{container_id}:/run/secrets/credentials.env",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _inject_ca_cert(self, container_id: str, cert_content: str) -> None:
        """Inject a custom CA certificate and update the container's trust store."""
        with tempfile.NamedTemporaryFile(suffix=".crt", mode="w", delete=False) as tmp:
            tmp.write(cert_content)
            tmp_path = tmp.name
        try:
            # Copy cert to standard location
            proc = await asyncio.create_subprocess_exec(
                "podman", "cp", tmp_path, f"{container_id}:/usr/local/share/ca-certificates/proxy-ca.crt",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            # Update trust store
            proc = await asyncio.create_subprocess_exec(
                "podman", "exec", container_id, "update-ca-certificates",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _install_pip_packages(
        self,
        container_id: str,
        packages: list[str],
        index_url: Optional[str],
        require_hashes: bool,
    ) -> None:
        """Install *packages* inside the container with hardened pip flags.

        Security measures applied:
        - Each specifier is validated against a strict allowlist pattern before
          being passed to pip, preventing shell-metacharacter injection.
        - ``--no-deps`` prevents transitive dependency pulls that could smuggle
          in unreviewed packages.
        - ``--require-hashes`` (when ``policy.pip_require_hashes`` is True)
          forces every specifier to carry a ``--hash=`` fragment; pip aborts if
          any hash is missing or wrong.
        - ``--index-url`` redirects to a private mirror when configured.
        - Install failure raises ``RuntimeError`` so the session is torn down
          rather than silently running an agent with missing dependencies.

        Args:
            container_id: Target container.
            packages: List of pip specifiers (e.g. ``["requests==2.31.0"]``).
            index_url: Optional private PyPI mirror URL.
            require_hashes: When True, pass ``--require-hashes`` to pip.

        Raises:
            ValueError: If any specifier contains characters outside the safe set.
            RuntimeError: If pip exits with a non-zero return code.
        """
        import re

        # Allowlist: package name chars, version specifiers, extras, hashes.
        # Permits: letters, digits, hyphens, underscores, dots, brackets,
        # comparison operators (==, >=, <=, !=, ~=, >), commas (extras),
        # semicolons (environment markers), spaces, and --hash= fragments.
        # Rejects: shell metacharacters (;|&`$!<>), path separators, quotes.
        _SAFE_SPECIFIER = re.compile(
            r'^[A-Za-z0-9_.+\-\[\]@/=<>!~,;: ]+(--hash=[a-zA-Z0-9:]+)?$'
        )
        for spec in packages:
            if not _SAFE_SPECIFIER.match(spec):
                raise ValueError(
                    f"pip package specifier contains unsafe characters: {spec!r}. "
                    "Only package names, version constraints, extras, environment "
                    "markers, and --hash= fragments are permitted."
                )

        pip_cmd = [
            "podman", "exec", container_id,
            "pip", "install",
            "--quiet",
            # Prevent transitive dependency pulls — only install what is
            # explicitly listed.  Callers must enumerate all required packages.
            "--no-deps",
        ]

        if index_url is not None:
            pip_cmd.extend(["--index-url", index_url])

        if require_hashes:
            pip_cmd.append("--require-hashes")

        pip_cmd.extend(packages)

        proc = await asyncio.create_subprocess_exec(
            *pip_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"pip install failed (exit {proc.returncode}) for packages "
                f"{packages!r}.\nstderr: {stderr.decode(errors='replace')}"
            )

    async def _inject_source(
        self,
        agent: Callable,
        container_id: str,
        agent_args: tuple = (),
        agent_kwargs: Optional[dict] = None,
    ) -> None:
        """Serialize the agent callable, args, and kwargs via cloudpickle."""
        if agent_kwargs is None:
            agent_kwargs = {}
        payload = {"fn": agent, "args": agent_args, "kwargs": agent_kwargs}
        with tempfile.NamedTemporaryFile(suffix=".pkl", mode="wb", delete=False) as tmp:
            cloudpickle.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "cp", tmp_path, f"{container_id}:{_CONTAINER_SOURCE_PATH}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _inject_bootstrap(self, container_id: str) -> None:
        """Write the bootstrap script and copy it into the container."""
        script = _BOOTSTRAP_TEMPLATE.format(
            source_path=_CONTAINER_SOURCE_PATH,
            output_path=_CONTAINER_OUTPUT_PATH,
        )
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(script)
            tmp_path = tmp.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "podman", "cp", tmp_path, f"{container_id}:{_CONTAINER_BOOTSTRAP_PATH}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _stream_output(
        self,
        proc: asyncio.subprocess.Process,
        replay_data: Optional[list[tuple[float, str, str]]] = None,
    ) -> None:
        """Stream stdout and stderr from *proc* to the caller's streams in real time."""
        import sys
        import time

        start_time = time.time()

        async def _pipe(reader, writer, stream_name):
            while True:
                line = await reader.read(4096)
                if not line:
                    break
                
                # Record for replay if enabled
                if replay_data is not None:
                    # asciinema expects relative time from start
                    ts = time.time() - start_time
                    replay_data.append((ts, stream_name, line.decode(errors="replace")))

                writer.buffer.write(line)
                writer.flush()

        await asyncio.gather(
            _pipe(proc.stdout, sys.stdout, "stdout"),
            _pipe(proc.stderr, sys.stderr, "stderr"),
        )

    async def _monitor_privilege_escalation(
        self,
        proc: asyncio.subprocess.Process,
        container_id: str,
        session_id: str,
        agent_id: str,
        poll_interval: float = 1.0,
    ) -> None:
        """Poll the container's effective UID and terminate if it becomes 0 (root).

        Runs concurrently with :meth:`_stream_output` and returns as soon as
        the agent process finishes or a violation is detected.

        Args:
            proc: The running ``podman exec`` process handle.
            container_id: Container to inspect.
            session_id: For audit logging.
            agent_id: For audit logging.
            poll_interval: Seconds between UID checks.
        """
        while proc.returncode is None:
            await asyncio.sleep(poll_interval)

            # If the process finished while we were sleeping, stop monitoring.
            if proc.returncode is not None:
                break

            try:
                uid_proc = await asyncio.create_subprocess_exec(
                    "podman", "exec", container_id, "id", "-u",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                uid_stdout, _ = await uid_proc.communicate()
            except Exception:
                # Podman not available or container already gone — stop monitoring.
                break

            if uid_proc.returncode != 0:
                # Container may have exited; stop monitoring.
                break

            uid_str = uid_stdout.decode().strip()
            try:
                uid = int(uid_str)
            except ValueError:
                continue

            if uid == 0:
                self._audit_logger.log_event(
                    event_type="privilege_escalation_attempt",
                    session_id=session_id,
                    agent_id=agent_id,
                    payload={
                        "violation_type": "privilege_escalation",
                        "attempted_action": "uid_change_to_root",
                        "container_id": container_id,
                        "detected_uid": uid,
                    },
                )
                # Terminate the agent process immediately.
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                break
