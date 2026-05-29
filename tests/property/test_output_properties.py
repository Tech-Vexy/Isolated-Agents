"""Property-based tests for OutputCollector with adapter-based architecture.

Feature: isolated-agents-sdk
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from isolated_agents_sdk.models import AgentResult, Policy
from isolated_agents_sdk.output_collector import OutputCollector

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
)

filename_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=30,
).filter(lambda s: s not in _WINDOWS_RESERVED_NAMES)

file_content_strategy = st.binary(min_size=0, max_size=1024)

output_files_strategy = st.dictionaries(
    keys=filename_strategy,
    values=file_content_strategy,
    min_size=1,
    max_size=10,
)

exit_code_strategy = st.integers(min_value=0, max_value=255)

id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=36,
)


# ---------------------------------------------------------------------------
# Property: Agent result contains exit code and artifacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@given(
    output_files=output_files_strategy,
    exit_code=exit_code_strategy,
    session_id=id_strategy,
    agent_id=id_strategy,
)
@settings(max_examples=50, deadline=None)
async def test_agent_result_contains_exit_code_and_artifacts(
    output_files: dict[str, bytes],
    exit_code: int,
    session_id: str,
    agent_id: str,
) -> None:
    """AgentResult SHALL contain the exit code and a mapping of all collected artifacts."""
    mock_audit_logger = MagicMock()
    mock_container_adapter = AsyncMock()
    from isolated_agents_sdk.adapters.container.types import ExecResult

    async def fake_exec_in_container(cid, cmd, **kwargs):
        if cmd[0] == "test":
            return ExecResult(exit_code=0, stdout="", stderr="")
        elif cmd[0] == "find":
            stdout = "\n".join([f"/output/{k}" for k in output_files]) + "\n"
            return ExecResult(exit_code=0, stdout=stdout, stderr="")
        elif cmd[0] == "du":
            total_size = sum(len(v) for v in output_files.values())
            return ExecResult(exit_code=0, stdout=f"{total_size} /output\n", stderr="")
        return ExecResult(exit_code=0, stdout="", stderr="")

    mock_container_adapter.exec_in_container = AsyncMock(side_effect=fake_exec_in_container)

    async def fake_copy_from_container(cid, src, dest, **kwargs):
        # Create a mock file at the destination path
        name = src.split("/")[-1]
        Path(dest).write_bytes(output_files.get(name, b""))

    mock_container_adapter.copy_from_container = AsyncMock(side_effect=fake_copy_from_container)

    mock_storage_adapter = AsyncMock()
    mock_storage_adapter.initialize = AsyncMock()

    # Simulate storing artifacts
    stored_artifacts = {}

    async def fake_store(session_id, artifact_name, data, content_type=None):
        stored_artifacts[artifact_name] = data
        return MagicMock(path=f"{session_id}/{artifact_name}", url=None)

    mock_storage_adapter.store_artifact = AsyncMock(side_effect=fake_store)

    collector = OutputCollector(
        audit_logger=mock_audit_logger,
        container_adapter=mock_container_adapter,
        storage_adapter=mock_storage_adapter,
    )

    with tempfile.TemporaryDirectory() as host_output_dir:
        # Patch Path.glob to simulate container files being copied to host
        # (Actually, we should patch PodmanAdapter.copy_from_container but we are using mocks)

        # We need to simulate that files are present on the host so they can be "stored"
        # Since we mocked store_artifact, we just need to ensure the loop runs.

        # We'll mock the copy operation if we were using real adapters, but here we
        # just need to make sure the collector sees the files.

        with patch("isolated_agents_sdk.output_collector.Path.glob") as mock_glob:
            # Create mock path objects
            mock_paths = []
            for name in output_files:
                p = MagicMock(spec=Path)
                p.name = name
                p.is_file.return_value = True
                p.stat.return_value.st_size = len(output_files[name])
                # Mock read_bytes to return the expected content
                p.read_bytes.return_value = output_files[name]
                mock_paths.append(p)

            mock_glob.return_value = mock_paths

            result = await collector.collect(
                container_id="test-container-id",
                policy=Policy(output_path_in_container="/output", max_output_bytes=None),
                host_output_path=Path(host_output_dir),
                exit_code=exit_code,
                session_id=session_id,
                agent_id=agent_id,
            )

        assert isinstance(result, AgentResult)
        assert result.exit_code == exit_code
        assert result.session_id == session_id

        # Check that storage adapter was called for each file
        assert len(stored_artifacts) == len(output_files)
        for name, content in output_files.items():
            assert stored_artifacts[name] == content
