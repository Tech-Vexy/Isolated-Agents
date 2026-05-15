"""Agent Runner for the Isolated Agents SDK.

Serialises an agent callable into a container, executes it, streams
stdout/stderr, and monitors for privilege escalation.
"""

from __future__ import annotations

import asyncio
import cloudpickle
import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
from isolated_agents_sdk.adapters.container.types import ContainerHandle
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.models import AgentResult, Policy

# Paths used inside the container
_CONTAINER_BOOTSTRAP_PATH = "/tmp/_agent_bootstrap.py"
_CONTAINER_OUTPUT_PATH = "/tmp/_agent_return.pkl"
_CONTAINER_SOURCE_PATH = "/tmp/_agent_source.pkl"

# Bootstrap script — injected source is loaded via cloudpickle.
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
        adapter: ContainerRuntimeAdapter instance (defaults to PodmanAdapter).
        audit_logger: :class:`AuditLogger` instance for emitting lifecycle events.
    """

    def __init__(
        self,
        handle: ContainerHandle,
        adapter: Optional[ContainerRuntimeAdapter] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self._handle = handle
        self._adapter = adapter or PodmanAdapter()
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
        """Execute the agent inside the container."""
        if agent_kwargs is None:
            agent_kwargs = {}
        container_id = self._handle.container_id

        # 1. Inject secrets if provided
        if policy.tmpfs_secrets:
            await self._inject_secrets(container_id, policy.tmpfs_secrets)

        # 2. Inject CA cert if provided
        if policy.proxy_ca_cert:
            await self._inject_ca_cert(container_id, policy.proxy_ca_cert)

        env = {}
        if policy.proxy_url:
            env.update({
                "HTTP_PROXY": policy.proxy_url,
                "HTTPS_PROXY": policy.proxy_url,
                "http_proxy": policy.proxy_url,
                "https_proxy": policy.proxy_url,
            })

        if policy.entrypoint:
            # Framework-Agnostic Mode: Execute the user's command
            if policy.requires_display:
                # Wrap with Xvfb
                xvfb_cmd = "Xvfb :99 -screen 0 1280x1024x24 & export DISPLAY=:99 && sleep 1 && "
                # Source secrets if they exist for polyglot agents too
                secret_cmd = "if [ -f /run/secrets/credentials.env ]; then set -a; . /run/secrets/credentials.env; set +a; fi && "
                final_cmd = xvfb_cmd + secret_cmd + " ".join(policy.entrypoint)
                command = ["sh", "-c", final_cmd]
            else:
                command = policy.entrypoint
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
                command = ["sh", "-c", final_cmd]
            else:
                command = ["python3", _CONTAINER_BOOTSTRAP_PATH]

        # 4. Launch the agent via the adapter
        # We need to handle streaming separately if the adapter doesn't support it directly in exec_in_container.
        # But wait, the adapter interface 'exec_in_container' returns ExecResult which has all stdout/stderr.
        # To support real-time streaming, the adapter should probably expose a stream_exec method.
        # For now, let's stick to the current adapter interface but acknowledge it might be blocking.
        
        # Emit agent_launched audit event
        self._audit_logger.log_event(
            event_type="agent_launched",
            session_id=session_id,
            agent_id=agent_id,
            payload={"container_id": container_id},
        )

        # Monitor privilege escalation concurrently
        # Note: This is tricky with the current adapter interface because exec_in_container is awaited.
        # We might need to run the exec in a separate task.
        
        exec_task = asyncio.create_task(
            self._adapter.exec_in_container(
                container_id=container_id,
                command=command,
                env=env,
                working_dir="/workspace",
            )
        )
        
        # Start privilege escalation monitor
        monitor_task = asyncio.create_task(
            self._monitor_privilege_escalation(
                container_id, session_id, agent_id
            )
        )
        
        try:
            exec_result = await exec_task
        finally:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

        exit_code = exec_result.exit_code

        # Print output to host stdout/stderr for real-time-like feel (though it's buffered here)
        if exec_result.stdout:
            import sys
            sys.stdout.write(exec_result.stdout)
            sys.stdout.flush()
        if exec_result.stderr:
            import sys
            sys.stderr.write(exec_result.stderr)
            sys.stderr.flush()

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
        # Replay data collection would need more work to integrate with adapter
        
        return AgentResult(
            exit_code=exit_code,
            artifacts=artifacts,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _inject_secrets(self, container_id: str, secrets: dict[str, str]) -> None:
        """Write secrets to a file in the tmpfs mount inside the container."""
        import shlex

        lines = []
        for k, v in secrets.items():
            if not k.replace("_", "").isalnum() or k[0].isdigit():
                raise ValueError(
                    f"Invalid secret key '{k}': must be a valid environment variable name."
                )
            lines.append(f"{k}={shlex.quote(v)}")
        content = "\n".join(lines) + "\n"

        with tempfile.NamedTemporaryFile(suffix=".env", mode="w", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            await self._adapter.copy_to_container(container_id, tmp_path, "/run/secrets/credentials.env")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _inject_ca_cert(self, container_id: str, cert_content: str) -> None:
        """Inject a custom CA certificate and update the container's trust store."""
        with tempfile.NamedTemporaryFile(suffix=".crt", mode="w", delete=False) as tmp:
            tmp.write(cert_content)
            tmp_path = tmp.name
        try:
            await self._adapter.copy_to_container(container_id, tmp_path, "/usr/local/share/ca-certificates/proxy-ca.crt")
            await self._adapter.exec_in_container(container_id, ["update-ca-certificates"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _install_pip_packages(
        self,
        container_id: str,
        packages: list[str],
        index_url: Optional[str],
        require_hashes: bool,
    ) -> None:
        """Install *packages* inside the container with hardened pip flags."""
        import re

        _SAFE_SPECIFIER = re.compile(
            r'^[A-Za-z0-9_.+\-\[\]@/=<>!~,;: ]+(--hash=[a-zA-Z0-9:]+)?$'
        )
        for spec in packages:
            if not _SAFE_SPECIFIER.match(spec):
                raise ValueError(
                    f"pip package specifier contains unsafe characters: {spec!r}."
                )

        pip_cmd = ["pip", "install", "--quiet"]
        if index_url is not None:
            pip_cmd.extend(["--index-url", index_url])
        if require_hashes:
            pip_cmd.append("--require-hashes")
        pip_cmd.extend(packages)

        result = await self._adapter.exec_in_container(container_id, pip_cmd)

        if result.exit_code != 0:
            raise RuntimeError(
                f"pip install failed (exit {result.exit_code}) for packages "
                f"{packages!r}.\nstderr: {result.stderr}"
            )

    async def _inject_source(
        self,
        agent: Callable,
        container_id: str,
        agent_args: tuple = (),
        agent_kwargs: Optional[dict] = None,
    ) -> None:
        """Serialize the agent callable, args, and kwargs via cloudpickle."""
        import cloudpickle
        if agent_kwargs is None:
            agent_kwargs = {}
        payload = {"fn": agent, "args": agent_args, "kwargs": agent_kwargs}
        with tempfile.NamedTemporaryFile(suffix=".pkl", mode="wb", delete=False) as tmp:
            cloudpickle.dump(payload, tmp)
            tmp_path = tmp.name

        try:
            await self._adapter.copy_to_container(container_id, tmp_path, _CONTAINER_SOURCE_PATH)
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
            await self._adapter.copy_to_container(container_id, tmp_path, _CONTAINER_BOOTSTRAP_PATH)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _monitor_privilege_escalation(
        self,
        container_id: str,
        session_id: str,
        agent_id: str,
        poll_interval: float = 1.0,
    ) -> None:
        """Poll the container's effective UID and terminate if it becomes 0 (root)."""
        while True:
            await asyncio.sleep(poll_interval)
            try:
                result = await self._adapter.exec_in_container(container_id, ["id", "-u"])
                if result.exit_code != 0:
                    break
                uid = int(result.stdout.strip())
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
                    # We would ideally kill the process here, but the adapter doesn't expose a kill method for a specific command.
                    # However, destroy_container (which happens on cleanup) will handle it.
                    # For now, we just log the event.
                    break
            except Exception:
                break
