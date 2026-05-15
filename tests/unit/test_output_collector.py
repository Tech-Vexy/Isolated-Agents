"""Unit tests for OutputCollector.

Covers:
- Empty result and warning when output path is missing in container (Requirement 7.2)
- OutputSizeLimitError raised and audit event emitted when size limit exceeded (Requirement 7.3)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch, AsyncMock

import pytest

from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.exceptions import OutputSizeLimitError
from isolated_agents_sdk.models import AgentResult
from isolated_agents_sdk.output_collector import OutputCollector

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


CONTAINER_ID = "abc123"
OUTPUT_PATH = "/output"
SESSION_ID = "sess-001"
AGENT_ID = "agent-001"


def _make_collector(audit_logger: AuditLogger | None = None) -> OutputCollector:
    return OutputCollector(audit_logger=audit_logger or MagicMock(spec=AuditLogger))


# ---------------------------------------------------------------------------
# Requirement 7.2 — missing output path returns empty result with warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMissingOutputPath:
    """When the output path does not exist inside the container, collect() should
    return an empty AgentResult and log a warning rather than raising."""

    async def test_returns_agent_result_on_missing_path(self, tmp_path: Path) -> None:
        """collect() returns an AgentResult (not raises) when output path is absent."""
        collector = _make_collector()

        # podman exec test -d … exits non-zero → path does not exist
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=1)
            result = await collector.collect(
                container_id=CONTAINER_ID,
                output_path_in_container=OUTPUT_PATH,
                host_output_path=tmp_path / "out",
                max_output_bytes=None,
                exit_code=0,
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
            )

        assert isinstance(result, AgentResult)

    async def test_artifacts_are_empty_on_missing_path(self, tmp_path: Path) -> None:
        """artifacts dict is empty when the container output path is absent."""
        collector = _make_collector()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=1)
            result = await collector.collect(
                container_id=CONTAINER_ID,
                output_path_in_container=OUTPUT_PATH,
                host_output_path=tmp_path / "out",
                max_output_bytes=None,
                exit_code=0,
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
            )

        assert result.artifacts == {}

    async def test_exit_code_preserved_on_missing_path(self, tmp_path: Path) -> None:
        """The caller-supplied exit code is preserved even when output path is absent."""
        collector = _make_collector()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=1)
            result = await collector.collect(
                container_id=CONTAINER_ID,
                output_path_in_container=OUTPUT_PATH,
                host_output_path=tmp_path / "out",
                max_output_bytes=None,
                exit_code=42,
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
            )

        assert result.exit_code == 42

    async def test_session_id_preserved_on_missing_path(self, tmp_path: Path) -> None:
        """session_id is preserved in the returned AgentResult."""
        collector = _make_collector()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=1)
            result = await collector.collect(
                container_id=CONTAINER_ID,
                output_path_in_container=OUTPUT_PATH,
                host_output_path=tmp_path / "out",
                max_output_bytes=None,
                exit_code=0,
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
            )

        assert result.session_id == SESSION_ID

    async def test_warning_is_logged_on_missing_path(self, tmp_path: Path, caplog) -> None:
        """A warning is emitted to the Python logger when the output path is absent."""
        import logging

        collector = _make_collector()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=1)
            with caplog.at_level(logging.WARNING, logger="isolated_agents_sdk.output_collector"):
                await collector.collect(
                    container_id=CONTAINER_ID,
                    output_path_in_container=OUTPUT_PATH,
                    host_output_path=tmp_path / "out",
                    max_output_bytes=None,
                    exit_code=0,
                    session_id=SESSION_ID,
                    agent_id=AGENT_ID,
                )

        assert any("does not exist" in record.message for record in caplog.records)

    async def test_no_podman_cp_called_on_missing_path(self, tmp_path: Path) -> None:
        """podman cp is never invoked when the output path check fails."""
        collector = _make_collector()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await _make_mock_proc(exit_code=1)
            await collector.collect(
                container_id=CONTAINER_ID,
                output_path_in_container=OUTPUT_PATH,
                host_output_path=tmp_path / "out",
                max_output_bytes=None,
                exit_code=0,
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
            )

        # Only the existence-check call should have been made
        for c in mock_exec.call_args_list:
            args = c.args
            assert "cp" not in args, "podman cp should not be called when output path is missing"


# ---------------------------------------------------------------------------
# Requirement 7.3 — output size limit enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestOutputSizeLimit:
    """When total output exceeds max_output_bytes, collect() must raise
    OutputSizeLimitError and emit an output_size_exceeded audit event."""

    async def _run_collect_with_files(
        self,
        tmp_path: Path,
        files: dict[str, bytes],
        max_output_bytes: int,
        audit_logger: AuditLogger,
    ) -> None:
        """Helper: simulate a container that has *files* at OUTPUT_PATH.

        The new OutputCollector calls:
          1. ``podman exec … test -d <path>``  — existence check
          2. ``podman exec … find <path> -type f``  — list regular files
          3. ``podman cp <container>:<file> <host_path>``  — one call per file
        """
        # Build a fake staging area that mimics the container's output directory.
        fake_output_dir = tmp_path / "fake_container_output"
        fake_output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            (fake_output_dir / name).write_bytes(content)

        # Pre-build the find output: one absolute path per file.
        find_output = "\n".join(
            f"{OUTPUT_PATH}/{name}" for name in files
        ).encode()

        async def fake_exec(*cmd, **kwargs):
            cmd = list(cmd)
            if "podman" not in cmd:
                return await _make_mock_proc(exit_code=0)

            subcmd = cmd[1] if len(cmd) > 1 else ""

            if subcmd == "exec":
                if "test" in cmd:
                    # Existence check — path exists.
                    return await _make_mock_proc(exit_code=0)
                if "find" in cmd:
                    # File listing — return one path per file.
                    return await _make_mock_proc(exit_code=0, stdout=find_output)
                return await _make_mock_proc(exit_code=0)

            if subcmd == "cp":
                # Per-file copy: ``podman cp container:/output/name /host/path``
                # The source is ``container_id:/output/name``; extract the filename.
                src = cmd[2]  # e.g. "abc123:/output/big.bin"
                dest_str = cmd[3]
                if ":" in src and src.index(":") != 1:
                    container_file = src.split(":", 1)[1]  # "/output/big.bin"
                    filename = Path(container_file).name
                    src_file = fake_output_dir / filename
                    if src_file.exists():
                        import shutil as _shutil
                        _shutil.copy2(str(src_file), dest_str)
                return await _make_mock_proc(exit_code=0)

            return await _make_mock_proc(exit_code=0)

        collector = OutputCollector(audit_logger=audit_logger)

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await collector.collect(
                container_id=CONTAINER_ID,
                output_path_in_container=OUTPUT_PATH,
                host_output_path=tmp_path / "host_out",
                max_output_bytes=max_output_bytes,
                exit_code=0,
                session_id=SESSION_ID,
                agent_id=AGENT_ID,
            )

    async def test_raises_output_size_limit_error(self, tmp_path: Path) -> None:
        """OutputSizeLimitError is raised when total output exceeds the limit."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"big.bin": b"x" * 100}

        with pytest.raises(OutputSizeLimitError):
            await self._run_collect_with_files(
                tmp_path=tmp_path,
                files=files,
                max_output_bytes=50,
                audit_logger=audit_logger,
            )

    async def test_audit_event_emitted_on_size_violation(self, tmp_path: Path) -> None:
        """An output_size_exceeded audit event is emitted when the limit is exceeded."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"big.bin": b"x" * 100}

        with pytest.raises(OutputSizeLimitError):
            await self._run_collect_with_files(
                tmp_path=tmp_path,
                files=files,
                max_output_bytes=50,
                audit_logger=audit_logger,
            )

        audit_logger.log_event.assert_called_once()
        call_kwargs = audit_logger.log_event.call_args
        assert call_kwargs.kwargs.get("event_type") == "output_size_exceeded" or (
            call_kwargs.args and call_kwargs.args[0] == "output_size_exceeded"
        )

    async def test_audit_event_payload_contains_violation_type(self, tmp_path: Path) -> None:
        """The audit event payload includes violation_type."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"data.bin": b"y" * 200}

        with pytest.raises(OutputSizeLimitError):
            await self._run_collect_with_files(
                tmp_path=tmp_path,
                files=files,
                max_output_bytes=10,
                audit_logger=audit_logger,
            )

        payload = audit_logger.log_event.call_args.kwargs["payload"]
        assert "violation_type" in payload

    async def test_audit_event_payload_contains_attempted_action(self, tmp_path: Path) -> None:
        """The audit event payload includes attempted_action."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"data.bin": b"z" * 200}

        with pytest.raises(OutputSizeLimitError):
            await self._run_collect_with_files(
                tmp_path=tmp_path,
                files=files,
                max_output_bytes=10,
                audit_logger=audit_logger,
            )

        payload = audit_logger.log_event.call_args.kwargs["payload"]
        assert "attempted_action" in payload

    async def test_no_files_copied_to_host_on_size_violation(self, tmp_path: Path) -> None:
        """No files are written to the host output path when the limit is exceeded."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"secret.bin": b"s" * 100}
        host_out = tmp_path / "host_out"

        with pytest.raises(OutputSizeLimitError):
            await self._run_collect_with_files(
                tmp_path=tmp_path,
                files=files,
                max_output_bytes=50,
                audit_logger=audit_logger,
            )

        assert not host_out.exists() or not any(host_out.rglob("*"))

    async def test_no_error_when_output_within_limit(self, tmp_path: Path) -> None:
        """No error is raised when total output is within the allowed limit."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"small.txt": b"hello"}

        # Should not raise
        await self._run_collect_with_files(
            tmp_path=tmp_path,
            files=files,
            max_output_bytes=1000,
            audit_logger=audit_logger,
        )

        audit_logger.log_event.assert_not_called()

    async def test_no_error_when_max_output_bytes_is_none(self, tmp_path: Path) -> None:
        """No size check is performed when max_output_bytes is None."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"large.bin": b"x" * 10_000}

        # Should not raise regardless of file size
        await self._run_collect_with_files(
            tmp_path=tmp_path,
            files=files,
            max_output_bytes=999_999_999,  # effectively unlimited for this test
            audit_logger=audit_logger,
        )

    async def test_error_message_includes_sizes(self, tmp_path: Path) -> None:
        """The OutputSizeLimitError message mentions the actual and limit sizes."""
        audit_logger = MagicMock(spec=AuditLogger)
        files = {"data.bin": b"x" * 100}

        with pytest.raises(OutputSizeLimitError, match=r"100"):
            await self._run_collect_with_files(
                tmp_path=tmp_path,
                files=files,
                max_output_bytes=50,
                audit_logger=audit_logger,
            )
