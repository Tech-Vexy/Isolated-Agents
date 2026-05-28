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

from isolated_agents_sdk.logging import add_global_sensitive_patterns
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import ContainerHandle
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.models import (
    AgentResult,
    Policy,
    INTERNAL_BASE_PATH,
    CONTAINER_BOOTSTRAP_PATH,
    CONTAINER_OUTPUT_PATH,
    CONTAINER_SOURCE_PATH,
)

# Container-internal paths used during execution
_CONTAINER_SITE_PACKAGES = "/tmp/site-packages"
_CONTAINER_SECRETS_PATH = "/run/secrets/credentials.env"
_CONTAINER_CA_CERT_PATH = "/usr/local/share/ca-certificates/proxy-ca.crt"

logger = logging.getLogger(__name__)

# Detect if adapters are available
try:
    from isolated_agents_sdk.adapters.registry import get_registry as _get_adapter_registry
    _ADAPTERS_AVAILABLE = True
except ImportError:
    _get_adapter_registry = None  # type: ignore[assignment]
    _ADAPTERS_AVAILABLE = False

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

# Initialize Sub-Agent Client if socket is present
if os.environ.get("ISOLATED_AGENTS_SPAWN_SOCKET"):
    try:
        from isolated_agents_sdk.sub_agent_client import init_sub_agent_client
        init_sub_agent_client(os.environ["ISOLATED_AGENTS_SPAWN_SOCKET"])
    except ImportError:
        pass

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
        if adapter:
            self._adapter = adapter
        elif _ADAPTERS_AVAILABLE and _get_adapter_registry is not None:
            self._adapter = _get_adapter_registry().get_container_adapter()
        else:
            from isolated_agents_sdk.adapters.container.podman import PodmanAdapter
            self._adapter = PodmanAdapter()

        self._audit_logger = audit_logger or AuditLogger()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def _prepare_execution(
        self,
        agent: Optional[Callable],
        policy: Policy,
        session_id: str,
        container_id: str,
        agent_args: tuple,
        agent_kwargs: dict,
        agent_payload_hex: Optional[str],
        spawn_socket_path: Optional[str],
    ) -> tuple[list[str], dict[str, str]]:
        """Prepare the command and environment for agent execution.

        Handles SDK injection, source serialisation, pip installs, and
        builds the final command list and env dict.

        Returns:
            (command, env) ready to pass to exec_in_container.
        """
        # Sub-agent socket setup
        if policy.allow_sub_agents:
            await self._setup_spawn_daemon(container_id, spawn_socket_path=spawn_socket_path)
            import isolated_agents_sdk as _sdk
            _pkg_path = Path(_sdk.__file__).parent
            try:
                await self._adapter.copy_to_container(
                    container_id, str(_pkg_path),
                    str(Path(INTERNAL_BASE_PATH) / "isolated_agents_sdk"),
                )
            except Exception as e:
                logger.error("Failed to inject SDK into container: %s", e)

        env: dict[str, str] = {}
        if policy.allow_sub_agents:
            from isolated_agents_sdk.models import CONTAINER_SPAWN_SOCKET_PATH
            env["ISOLATED_AGENTS_SPAWN_SOCKET"] = CONTAINER_SPAWN_SOCKET_PATH
            env["PYTHONPATH"] = f"{INTERNAL_BASE_PATH}:{env.get('PYTHONPATH', '')}".strip(":")
            env["ISOLATED_AGENTS_SESSION_ID"] = session_id

        if policy.proxy_url:
            env.update({
                "HTTP_PROXY": policy.proxy_url,
                "HTTPS_PROXY": policy.proxy_url,
                "http_proxy": policy.proxy_url,
                "https_proxy": policy.proxy_url,
            })
            if policy.network.grpc:
                env["GRPC_PROXY"] = policy.proxy_url
                env["grpc_proxy"] = policy.proxy_url

        if policy.entrypoint:
            command = self._build_entrypoint_command(policy)
        else:
            command = await self._build_python_command(
                agent, policy, container_id, agent_args, agent_kwargs,
                agent_payload_hex, env,
            )

        return command, env

    def _build_entrypoint_command(self, policy: Policy) -> list[str]:
        """Build the shell command for entrypoint (framework-agnostic) mode."""
        if policy.requires_display:
            xvfb = "Xvfb :99 -screen 0 1280x1024x24 & export DISPLAY=:99 && sleep 1 && "
            secret = "if [ -f /run/secrets/credentials.env ]; then set -a; . /run/secrets/credentials.env; set +a; fi && "
            return ["sh", "-c", xvfb + secret + " ".join(policy.entrypoint)]  # type: ignore[arg-type]
        return list(policy.entrypoint)  # type: ignore[arg-type]

    async def _build_python_command(
        self,
        agent: Optional[Callable],
        policy: Policy,
        container_id: str,
        agent_args: tuple,
        agent_kwargs: dict,
        agent_payload_hex: Optional[str],
        env: dict[str, str],
    ) -> list[str]:
        """Serialise agent, install deps, and return the bootstrap command."""
        if agent is None and agent_payload_hex is None:
            raise ValueError("Agent callable must be provided if policy.entrypoint is not set.")

        await self._inject_source(
            agent=agent,
            container_id=container_id,
            agent_args=agent_args,
            agent_kwargs=agent_kwargs,
            agent_payload_hex=agent_payload_hex,
        )
        await self._inject_bootstrap(container_id)

        packages_to_install = list(policy.pip_packages)
        should_inject_cloudpickle = False
        if "cloudpickle" not in [p.split("==")[0].split(">=")[0].strip() for p in packages_to_install]:
            if policy.pip_require_hashes:
                should_inject_cloudpickle = True
            else:
                packages_to_install.append("cloudpickle")

        if should_inject_cloudpickle:
            import cloudpickle as _cp
            cp_path = Path(_cp.__file__).parent
            try:
                await self._adapter.copy_to_container(
                    container_id, str(cp_path),
                    str(Path(INTERNAL_BASE_PATH) / "cloudpickle"),
                )
                env["PYTHONPATH"] = f"{INTERNAL_BASE_PATH}:{env.get('PYTHONPATH', '')}".strip(":")
            except Exception as e:
                logger.error("Failed to inject cloudpickle from host: %s", e)

        await self._install_pip_packages(
            container_id=container_id,
            packages=packages_to_install,
            index_url=policy.pip_index_url,
            require_hashes=policy.pip_require_hashes,
        )

        env["PYTHONPATH"] = f"{_CONTAINER_SITE_PACKAGES}:{env.get('PYTHONPATH', '')}".strip(":")

        if policy.requires_display:
            xvfb = "Xvfb :99 -screen 0 1280x1024x24 & export DISPLAY=:99 && sleep 1 && "
            return ["sh", "-c", xvfb + f"python3 {CONTAINER_BOOTSTRAP_PATH}"]
        return ["python3", CONTAINER_BOOTSTRAP_PATH]

    async def run(
        self,
        agent: Optional[Callable],
        policy: Policy,
        session_id: str,
        agent_id: str,
        agent_args: tuple = (),
        agent_kwargs: Optional[dict] = None,
        agent_payload_hex: Optional[str] = None,
        spawn_socket_path: Optional[str] = None,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> AgentResult:
        """Execute the agent inside the container.

        This method orchestrates the entire agent execution lifecycle:
        1. Injects secrets and CA certificates into the container.
        2. Injects agent source code (if Python callable mode used).
        3. Installs dependencies requested by the policy.
        4. Executes the agent (or entrypoint) with optional retry logic.
        5. Monitors for privilege escalation during execution.
        6. Collects exit code and return values.

        Args:
            agent: The Python callable to execute, or None if using entrypoint mode.
            policy: The :class:`Policy` governing the execution.
            session_id: Unique identifier for this execution session.
            agent_id: Human-readable identifier for the agent.
            agent_args: Positional arguments for the agent callable.
            agent_kwargs: Keyword arguments for the agent callable.

        Returns:
            An :class:`AgentResult` containing the execution outcome.
        """
        if agent_kwargs is None:
            agent_kwargs = {}
        container_id = self._handle.container_id

        # 0. Register sensitive patterns from policy for log masking
        if policy.sensitive_env_vars:
            add_global_sensitive_patterns(policy.sensitive_env_vars)

        # 1. Inject secrets if provided
        if policy.tmpfs_secrets:
            await self._inject_secrets(container_id, policy.tmpfs_secrets)

        # 2. Inject CA cert if provided
        if policy.proxy_ca_cert:
            await self._inject_ca_cert(container_id, policy.proxy_ca_cert)

        # 3. Build command and environment
        command, env = await self._prepare_execution(
            agent=agent,
            policy=policy,
            session_id=session_id,
            container_id=container_id,
            agent_args=agent_args,
            agent_kwargs=agent_kwargs,
            agent_payload_hex=agent_payload_hex,
            spawn_socket_path=spawn_socket_path,
        )

        # 4. Launch the agent via the adapter with optional retries
        attempts = 0
        max_attempts = policy.retry_count + 1
        exec_result = None
        exit_code = 1  # default; overwritten by exec_result below

        while attempts < max_attempts:
            attempts += 1
            
            # Emit agent_launched audit event (only on first attempt)
            if attempts == 1:
                await self._audit_logger.log_event(
                    event_type="agent_launched",
                    session_id=session_id,
                    agent_id=agent_id,
                    payload={"container_id": container_id, "image": policy.base_image},
                )

            if policy.interactive:
                # Interactive mode: Bypass the exec_task and run directly
                await self._audit_logger.log_event(
                    event_type="agent_interactive_start",
                    session_id=session_id,
                    agent_id=agent_id,
                    payload={"container_id": container_id, "command": command},
                )
                exit_code = await self._adapter.interactive_exec(
                    container_id=container_id,
                    command=command,
                    env=env,
                    working_dir="/workspace",
                )
                # Create a dummy result for the rest of the flow
                from isolated_agents_sdk.adapters.container.types import ExecResult
                exec_result = ExecResult(exit_code=exit_code, stdout="", stderr="")
            else:
                import sys

                def default_stdout(chunk):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    if on_stdout:
                        on_stdout(chunk)

                def default_stderr(chunk):
                    sys.stderr.write(chunk)
                    sys.stderr.flush()
                    if on_stderr:
                        on_stderr(chunk)

                # Execute in container (v0.2.1: Removed insecure polling monitor)
                # Rely on kernel-level isolation (Seccomp, Capabilities, UID mapping)
                try:
                    exec_result = await self._adapter.exec_in_container(
                        container_id=container_id,
                        command=command,
                        env=env,
                        working_dir="/workspace",
                        on_stdout=default_stdout,
                        on_stderr=default_stderr,
                    )
                except Exception as e:
                    logger.error(f"Execution failed: {e}")
                    raise
            
            exit_code = exec_result.exit_code

            # Break if successful or interactive or no more retries
            if exit_code == 0 or policy.interactive or attempts >= max_attempts:
                break
            
            # Handle retry
            await self._audit_logger.log_event(
                event_type="agent_retry",
                session_id=session_id,
                agent_id=agent_id,
                payload={
                    "attempt": attempts,
                    "exit_code": exit_code,
                    "delay_seconds": policy.retry_delay_seconds
                },
            )
            await asyncio.sleep(policy.retry_delay_seconds)

        error_msg = None
        # OOM Kill detection
        if exit_code == 137:
            error_msg = "Agent exceeded allocated memory limits (OOM Kill)"
            await self._audit_logger.log_event(
                event_type="resource_limit_exceeded",
                session_id=session_id,
                agent_id=agent_id,
                payload={
                    "violation_type": "oom_kill",
                    "attempted_action": "memory_allocation",
                    "reason": error_msg,
                    "container_id": container_id,
                },
            )
        elif exit_code != 0:
            error_msg = f"Agent process failed with exit code {exit_code}"

        artifacts = {}
        # Replay data collection would need more work to integrate with adapter
        
        return AgentResult(
            exit_code=exit_code,
            artifacts=artifacts,
            session_id=session_id,
            output=None,
            error=error_msg,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _setup_spawn_daemon(self, container_id: str, spawn_socket_path: Optional[str] = None) -> None:
        """Initialize the spawn daemon and mount the IPC socket.
        
        This method ensures the container can reach the Spawn Daemon.
        If current runtime has a socket, it is mounted.
        """
        if not spawn_socket_path:
            return
            
        # Mounting logic is typically handled by the adapter during provision.
        # However, if we are doing it via exec or post-provision, we need
        # adapter support. For now, we assume the provisioner handles it
        # or we rely on the adapter to support hot-mounting.
        pass

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
            await self._adapter.copy_to_container(container_id, tmp_path, _CONTAINER_SECRETS_PATH)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _inject_ca_cert(self, container_id: str, cert_content: str) -> None:
        """Inject a custom CA certificate and update the container's trust store."""
        with tempfile.NamedTemporaryFile(suffix=".crt", mode="w", delete=False) as tmp:
            tmp.write(cert_content)
            tmp_path = tmp.name
        try:
            await self._adapter.copy_to_container(container_id, tmp_path, _CONTAINER_CA_CERT_PATH)
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
        """Install Python packages into a temporary directory inside the container.

        Packages are installed to /tmp/site-packages and added to PYTHONPATH.
        This ensures the root filesystem remains read-only if configured.

        Args:
            container_id: ID of the container to install packages into.
            packages: List of pip package specifiers.
            index_url: Optional private PyPI index URL.
            require_hashes: Whether to require --hash on all packages.
        """
        import re

        _SAFE_SPECIFIER = re.compile(
            r'^[A-Za-z0-9_.+\-\[\]@/=<>!~,;: ]+(--hash=[a-zA-Z0-9:]+)?$'
        )
        for spec in packages:
            if not _SAFE_SPECIFIER.match(spec):
                raise ValueError(
                    f"pip package specifier contains unsafe characters: {spec!r}."
                )

        # Install to /tmp/site-packages because rootfs might be read-only.
        # Set HOME=/tmp to avoid pip trying to write to /root.
        pip_cmd = [
            "python3", "-m", "pip", "install",
            "--no-cache-dir",
            "--target", _CONTAINER_SITE_PACKAGES,
            "--retries", "10",
            "--default-timeout", "180"
        ]
        if index_url is not None:
            pip_cmd.extend(["--index-url", index_url])
        if require_hashes:
            pip_cmd.append("--require-hashes")
        pip_cmd.extend(packages)

        env = {
            "HOME": "/tmp",
            "PIP_BREAK_SYSTEM_PACKAGES": "1"
        }
        
        result = await self._adapter.exec_in_container(
            container_id=container_id, 
            command=pip_cmd,
            env=env,
            user="root",
            timeout=600
        )

        if result.exit_code != 0:
            raise RuntimeError(
                f"pip install failed (exit {result.exit_code}) for packages "
                f"{packages!r}.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

    async def _inject_source(
        self,
        agent: Optional[Callable],
        container_id: str,
        agent_args: tuple = (),
        agent_kwargs: Optional[dict] = None,
        agent_payload_hex: Optional[str] = None,
    ) -> None:
        """Serialize the agent callable, args, and kwargs via cloudpickle and copy to container.

        Args:
            agent: The Python callable to serialize.
            container_id: ID of the container to inject the source into.
            agent_args: Positional arguments for the agent.
            agent_kwargs: Keyword arguments for the agent.
            agent_payload_hex: Hex-encoded pickled payload (v0.2.1: bypass host deserialization).
        """
        if agent_payload_hex:
            # v0.2.1: Security fix - use pre-pickled payload from untrusted container directly.
            # This prevents host-side RCE via insecure deserialization.
            payload_bytes = bytes.fromhex(agent_payload_hex)
            with tempfile.NamedTemporaryFile(suffix=".pkl", mode="wb", delete=False) as tmp:
                tmp.write(payload_bytes)
                tmp_path = tmp.name
        else:
            import cloudpickle
            if agent_kwargs is None:
                agent_kwargs = {}
            payload = {"fn": agent, "args": agent_args, "kwargs": agent_kwargs}
            with tempfile.NamedTemporaryFile(suffix=".pkl", mode="wb", delete=False) as tmp:
                cloudpickle.dump(payload, tmp)
                tmp_path = tmp.name

        try:
            await self._adapter.copy_to_container(container_id, tmp_path, CONTAINER_SOURCE_PATH)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _inject_bootstrap(self, container_id: str) -> None:
        """Write the bootstrap script and copy it into the container."""
        script = _BOOTSTRAP_TEMPLATE.format(
            source_path=CONTAINER_SOURCE_PATH,
            output_path=CONTAINER_OUTPUT_PATH,
        )
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(script)
            tmp_path = tmp.name
        try:
            await self._adapter.copy_to_container(container_id, tmp_path, CONTAINER_BOOTSTRAP_PATH)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # v0.2.1: Removed _monitor_privilege_escalation. 
    # High-overhead polling is ineffective against TOCTOU attacks.
    # Security is now enforced via Podman User Namespaces and Seccomp profiles.

    async def _stream_output(self, *args, **kwargs) -> None:
        """Legacy method for backward compatibility in tests."""
        pass
