"""Property-based tests for OutputCollector.

Feature: isolated-agents-sdk
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from isolated_agents_sdk.models import AgentResult


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for valid filenames.
# - Lowercase only: avoids Windows case-insensitive filesystem collisions
#   (e.g. 'foo' and 'FOO' would map to the same file on Windows).
# - No trailing dot: invalid on Windows.
# - Excludes Windows reserved device names (NUL, CON, etc.).
_WINDOWS_RESERVED_NAMES = frozenset({
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
})

filename_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=30,
).filter(lambda s: s not in _WINDOWS_RESERVED_NAMES)

# Strategy for arbitrary file contents
file_content_strategy = st.binary(min_size=0, max_size=1024)

# Strategy for a non-empty dict of filename → bytes
output_files_strategy = st.dictionaries(
    keys=filename_strategy,
    values=file_content_strategy,
    min_size=1,
    max_size=10,
)

# Strategy for valid exit codes
exit_code_strategy = st.integers(min_value=0, max_value=255)

# Strategy for session/agent IDs
id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=36,
)


# ---------------------------------------------------------------------------
# Property 8: Agent result contains exit code and artifacts
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 8: Agent result contains exit code and artifacts
@given(
    output_files=output_files_strategy,
    exit_code=exit_code_strategy,
    session_id=id_strategy,
    agent_id=id_strategy,
)
@settings(max_examples=100, deadline=None)
def test_agent_result_contains_exit_code_and_artifacts(
    output_files: dict[str, bytes],
    exit_code: int,
    session_id: str,
    agent_id: str,
) -> None:
    """For any successful agent execution that produces output files, the returned
    AgentResult SHALL contain the agent's exit code and a mapping of all files
    present at the container's output_path_in_container to their byte contents.

    Validates: Requirements 6.5, 7.1
    """
    from isolated_agents_sdk.output_collector import OutputCollector

    with tempfile.TemporaryDirectory() as container_output_dir, \
         tempfile.TemporaryDirectory() as host_output_dir:

        container_output_path = Path(container_output_dir)

        # Write the generated files into the simulated container output directory
        for filename, content in output_files.items():
            (container_output_path / filename).write_bytes(content)

        collector = OutputCollector(audit_logger=MagicMock())

        # Patch subprocess calls so no real Podman is needed:
        # - `podman exec ... test -d <path>` → returncode 0 (path exists)
        # - `podman cp <container>:<path> <tmp>` → copy from our temp dir instead
        def fake_run(cmd, **kwargs):
            result = MagicMock()
            if "test" in cmd:
                # Simulate output path exists in container
                result.returncode = 0
            elif "cp" in cmd:
                # cmd: ["podman", "cp", "container_id:/output", "/tmp/xyz/output"]
                dest = Path(cmd[-1])
                dest.mkdir(parents=True, exist_ok=True)
                for filename, content in output_files.items():
                    (dest / filename).write_bytes(content)
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        with patch("isolated_agents_sdk.output_collector.subprocess.run", side_effect=fake_run):
            result = collector.collect(
                container_id="test-container-id",
                output_path_in_container="/output",
                host_output_path=host_output_dir,
                max_output_bytes=None,
                exit_code=exit_code,
                session_id=session_id,
                agent_id=agent_id,
            )

        # The result must be an AgentResult
        assert isinstance(result, AgentResult)

        # Exit code must be preserved exactly
        assert result.exit_code == exit_code

        # session_id must be preserved
        assert result.session_id == session_id

        # Every generated file must appear in artifacts with its exact content
        for filename, expected_content in output_files.items():
            assert filename in result.artifacts, (
                f"Expected '{filename}' in artifacts but got keys: {list(result.artifacts.keys())}"
            )
            assert result.artifacts[filename] == expected_content, (
                f"Content mismatch for '{filename}'"
            )

        # No extra files should appear beyond what was generated
        assert set(result.artifacts.keys()) == set(output_files.keys())


# ---------------------------------------------------------------------------
# Property 9: Output size limit is enforced
# ---------------------------------------------------------------------------

# Feature: isolated-agents-sdk, Property 9: Output size limit is enforced
@given(
    output_files=output_files_strategy,
    exit_code=exit_code_strategy,
    session_id=id_strategy,
    agent_id=id_strategy,
)
@settings(max_examples=100, deadline=None)
def test_output_size_limit_is_enforced(
    output_files: dict[str, bytes],
    exit_code: int,
    session_id: str,
    agent_id: str,
) -> None:
    """For any policy with a max_output_bytes limit, if the total size of files at
    the container's output path exceeds that limit, the SDK SHALL reject the transfer
    and emit an output_size_exceeded audit event rather than copying the files.

    Validates: Requirements 7.3
    """
    from isolated_agents_sdk.exceptions import OutputSizeLimitError
    from isolated_agents_sdk.output_collector import OutputCollector

    total_size = sum(len(v) for v in output_files.values())
    # Set the limit to one byte less than the total so it is always exceeded
    max_output_bytes = max(0, total_size - 1)

    mock_audit_logger = MagicMock()

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        if "test" in cmd:
            result.returncode = 0
        elif "cp" in cmd:
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            for filename, content in output_files.items():
                (dest / filename).write_bytes(content)
            result.returncode = 0
        else:
            result.returncode = 0
        return result

    collector = OutputCollector(audit_logger=mock_audit_logger)

    with tempfile.TemporaryDirectory() as host_output_dir:
        with patch("isolated_agents_sdk.output_collector.subprocess.run", side_effect=fake_run):
            try:
                collector.collect(
                    container_id="test-container-id",
                    output_path_in_container="/output",
                    host_output_path=host_output_dir,
                    max_output_bytes=max_output_bytes,
                    exit_code=exit_code,
                    session_id=session_id,
                    agent_id=agent_id,
                )
                # If total_size == 0 and limit is 0, no files to copy — no error expected
                assert total_size == 0, (
                    "Expected OutputSizeLimitError to be raised when output exceeds limit"
                )
            except OutputSizeLimitError:
                # Transfer was correctly rejected — verify the audit event was emitted
                mock_audit_logger.log_event.assert_called_once()
                call_kwargs = mock_audit_logger.log_event.call_args
                args = call_kwargs[1] if call_kwargs[1] else {}
                # Support both positional and keyword call styles
                if call_kwargs[0]:
                    event_type = call_kwargs[0][0]
                else:
                    event_type = args.get("event_type", "")
                assert event_type == "output_size_exceeded", (
                    f"Expected audit event 'output_size_exceeded', got '{event_type}'"
                )

                # No files should have been written to the host output directory
                host_files = list(Path(host_output_dir).rglob("*"))
                assert not host_files, (
                    f"Expected no files copied to host after size limit rejection, "
                    f"but found: {host_files}"
                )
