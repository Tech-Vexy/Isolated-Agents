"""Shared fixtures for integration tests."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from isolated_agents_sdk.adapters import AdapterRegistry


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests.

    Yields:
        Path to temporary directory

    Cleanup:
        Removes the temporary directory after the test
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def reset_registry():
    """Reset the adapter registry before and after each test.

    This ensures test isolation by clearing the singleton registry
    instance between tests.
    """
    AdapterRegistry.reset_instance()
    yield
    AdapterRegistry.reset_instance()


@pytest.fixture
def sample_session_id() -> str:
    """Provide a sample session ID for tests."""
    return "test-session-123"


@pytest.fixture
def sample_agent_id() -> str:
    """Provide a sample agent ID for tests."""
    return "test-agent-456"


# Made with Bob
