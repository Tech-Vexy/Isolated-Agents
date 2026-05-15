"""Unit tests for ContainerProvisioner."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from isolated_agents_sdk.container_provisioner import ContainerHandle, ContainerProvisioner
from isolated_agents_sdk.exceptions import PodmanNotFoundError, WorkingDirectoryError
from isolated_agents_sdk.models import NetworkPolicy, Policy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_mock_proc(exit_code: int = 0, stdout: bytes = b"", stderr: bytes = b""):
    """Return a mock asyncio subprocess that finishes immediately."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.wait = AsyncMock(return_value=exit_code)
    proc.returncode = exit_code
    return proc


def _provisioner() -> ContainerProvisioner:
    return ContainerProvisioner()


def _default_policy() -> Policy:
    return Policy()


# ---------------------------------------------------------------------------
# _check_podman
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCheckPodman:
    async def test_raises_when_podman_missing(self, tmp_path):
        p = _provisioner()
        with patch("shutil.which", return_value=None):
            with pytest.raises(PodmanNotFoundError):
                await p.provision(tmp_path, _default_policy(), "s1", "a1")

    async def test_no_error_when_podman_present(self, tmp_path):
        p = _provisioner()
        with patch("shutil.which", return_value="/usr/bin/podman"):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = await _make_mock_proc(stdout=b"abc123\n")
                handle = await p.provision(tmp_path, _default_policy(), "s1", "a1")
        assert handle.container_id == "abc123"


# ---------------------------------------------------------------------------
# Working directory validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestWorkingDirectory:
    async def test_raises_for_nonexistent_directory(self, tmp_path):
        p = _provisioner()
        missing = tmp_path / "does_not_exist"
        with patch("shutil.which", return_value="/usr/bin/podman"):
            with pytest.raises(WorkingDirectoryError):
                await p.provision(missing, _default_policy(), "s1", "a1")

    async def test_accepts_existing_directory(self, tmp_path):
        p = _provisioner()
        with patch("shutil.which", return_value="/usr/bin/podman"):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = await _make_mock_proc(stdout=b"cid\n")
                handle = await p.provision(tmp_path, _default_policy(), "s1", "a1")
        assert isinstance(handle, ContainerHandle)


# ---------------------------------------------------------------------------
# build_command — isolation flags
# ---------------------------------------------------------------------------

class TestBuildCommandIsolationFlags:
    def test_always_includes_userns_keep_id(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "--userns=keep-id" in cmd

    def test_always_includes_pid_private(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "--pid=private" in cmd

    def test_always_includes_no_new_privileges(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "--security-opt=no-new-privileges" in cmd

    def test_never_includes_privileged(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "--privileged" not in cmd

    def test_includes_shm_size(self, tmp_path):
        policy = Policy(memory_mb=1000)
        cmd = _provisioner().build_command(tmp_path, policy)
        # 50% of 1000mb is 500mb
        assert "--shm-size=500m" in cmd

    def test_starts_with_podman_run_detach(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert cmd[:3] == ["podman", "run", "--detach"]

    def test_does_not_include_rm_flag(self, tmp_path):
        # --rm is intentionally absent: the container must stay alive after the
        # agent exits so OutputCollector can run `podman cp` against it.
        # SessionManager.complete_session() calls `podman rm -f` explicitly.
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "--rm" not in cmd

    def test_includes_memory_swap_limit(self, tmp_path):
        policy = Policy(memory_mb=256)
        cmd = _provisioner().build_command(tmp_path, policy)
        assert "--memory=256m" in cmd
        assert "--memory-swap=256m" in cmd

    def test_uses_tail_f_dev_null_as_keepalive(self, tmp_path):
        # tail -f /dev/null is the correct POSIX idiom for keeping a container
        # alive indefinitely without a time ceiling.  sleep 3600 was replaced
        # because it imposed an arbitrary 1-hour limit.
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "tail" in cmd
        assert "-f" in cmd
        assert "/dev/null" in cmd
        assert "sleep" not in cmd


# ---------------------------------------------------------------------------
# build_command — network
# ---------------------------------------------------------------------------

class TestBuildCommandNetwork:
    def test_network_none_when_disabled(self, tmp_path):
        policy = Policy(network=NetworkPolicy(disabled=True))
        cmd = _provisioner().build_command(tmp_path, policy)
        assert "--network=none" in cmd

    def test_no_network_none_when_enabled(self, tmp_path):
        policy = Policy(network=NetworkPolicy(disabled=False, allowed_endpoints=["8.8.8.8:53"]))
        cmd = _provisioner().build_command(tmp_path, policy)
        assert "--network=none" not in cmd

    def test_allowed_endpoints_use_add_host(self, tmp_path):
        # Endpoints must appear as --add-host entries, not raw --network args.
        # Passing raw "host:port" strings as --network values is invalid Podman
        # syntax; slirp4netns is used for the network mode instead.
        policy = Policy(network=NetworkPolicy(disabled=False, allowed_endpoints=["host1:80", "host2:443"]))
        cmd = _provisioner().build_command(tmp_path, policy)
        # The network mode should be slirp4netns, not the raw endpoint string
        assert "--network=slirp4netns:allow_host_loopback=false" in cmd
        # Each host should appear as an --add-host entry
        assert "--add-host" in cmd
        cmd_str = " ".join(cmd)
        assert "host1" in cmd_str
        assert "host2" in cmd_str
        # Raw endpoint strings must NOT appear as --network values
        assert "--network=host1:80" not in cmd
        assert "--network=host2:443" not in cmd


# ---------------------------------------------------------------------------
# build_command — resource limits
# ---------------------------------------------------------------------------

class TestBuildCommandResourceLimits:
    def test_default_cpu_and_memory(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert "--cpus=1.0" in cmd
        assert "--memory=512m" in cmd

    def test_custom_cpu_and_memory(self, tmp_path):
        policy = Policy(cpu_cores=2.5, memory_mb=1024)
        cmd = _provisioner().build_command(tmp_path, policy)
        assert "--cpus=2.5" in cmd
        assert "--memory=1024m" in cmd


# ---------------------------------------------------------------------------
# build_command — mounts
# ---------------------------------------------------------------------------

class TestBuildCommandMounts:
    def test_working_dir_mounted_rw(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        assert f"{tmp_path}:/workspace:rw" in cmd

    def test_readonly_mounts_included(self, tmp_path):
        policy = Policy(readonly_mounts=["/etc/ssl", "/usr/share/ca-certificates"])
        cmd = _provisioner().build_command(tmp_path, policy)
        assert "/etc/ssl:/etc/ssl:ro" in cmd
        assert "/usr/share/ca-certificates:/usr/share/ca-certificates:ro" in cmd

    def test_no_extra_mounts_by_default(self, tmp_path):
        cmd = _provisioner().build_command(tmp_path, _default_policy())
        # Only the workspace mount should be present
        mounts = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-v"]
        assert len(mounts) == 1
        assert mounts[0] == f"{tmp_path}:/workspace:rw"


# ---------------------------------------------------------------------------
# build_command — environment variables
# ---------------------------------------------------------------------------

class TestBuildCommandEnvVars:
    def test_allowed_env_var_forwarded_when_present(self, tmp_path):
        policy = Policy(allowed_env_vars=["MY_VAR"])
        with patch.dict(os.environ, {"MY_VAR": "hello"}):
            cmd = _provisioner().build_command(tmp_path, policy)
        assert "-e" in cmd
        assert "MY_VAR=hello" in cmd

    def test_env_var_not_forwarded_when_absent_from_host(self, tmp_path):
        policy = Policy(allowed_env_vars=["ABSENT_VAR_XYZ"])
        env = {k: v for k, v in os.environ.items() if k != "ABSENT_VAR_XYZ"}
        with patch.dict(os.environ, env, clear=True):
            cmd = _provisioner().build_command(tmp_path, policy)
        assert "ABSENT_VAR_XYZ" not in " ".join(cmd)

    def test_only_allowed_vars_forwarded(self, tmp_path):
        policy = Policy(allowed_env_vars=["ALLOWED_VAR"])
        with patch.dict(os.environ, {"ALLOWED_VAR": "yes", "SECRET": "no"}, clear=True):
            cmd = _provisioner().build_command(tmp_path, policy)
        assert "ALLOWED_VAR=yes" in cmd
        assert "SECRET" not in " ".join(cmd)


# ---------------------------------------------------------------------------
# ContainerHandle
# ---------------------------------------------------------------------------

class TestContainerHandle:
    def test_has_container_id(self):
        handle = ContainerHandle(container_id="abc123")
        assert handle.container_id == "abc123"


# ---------------------------------------------------------------------------
# Audit event on provision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAuditEvent:
    async def test_container_created_event_emitted(self, tmp_path):
        from isolated_agents_sdk.audit_logger import AuditLogger

        emitted = []

        class CapturingLogger(AuditLogger):
            def log_event(self, event_type, session_id, agent_id, payload):
                emitted.append((event_type, session_id, agent_id, payload))

        p = ContainerProvisioner(audit_logger=CapturingLogger())
        with patch("shutil.which", return_value="/usr/bin/podman"):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.return_value = await _make_mock_proc(stdout=b"cid42\n")
                await p.provision(tmp_path, _default_policy(), "sess1", "agent1")

        assert len(emitted) == 1
        event_type, session_id, agent_id, payload = emitted[0]
        assert event_type == "container_created"
        assert session_id == "sess1"
        assert agent_id == "agent1"
        assert payload["container_id"] == "cid42"
