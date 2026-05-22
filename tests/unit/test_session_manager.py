"""Unit tests for SessionManager.

Covers:
- Cleanup handlers (atexit + signals) are registered on first session creation (Req 9.2)
- list_sessions() returns correct data for active sessions (Req 9.3)
- Session is removed from registry after completion (Req 9.3)
"""

from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch, AsyncMock, ANY

import pytest

from isolated_agents_sdk.models import Policy, SessionInfo, SessionMetrics
from isolated_agents_sdk.session_manager import SessionManager
from isolated_agents_sdk.adapters.container.base import ContainerRuntimeAdapter
from isolated_agents_sdk.adapters.container.types import ContainerStats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_mock_adapter():
    adapter = MagicMock(spec=ContainerRuntimeAdapter)
    adapter.get_container_stats = AsyncMock(return_value=ContainerStats(cpu_percent=5.0, memory_mb=128.0, memory_limit_mb=512.0))
    adapter.destroy_container = AsyncMock()
    adapter.get_adapter_name = MagicMock(return_value="MockAdapter")
    return adapter

def _make_manager(adapter=None) -> SessionManager:
    """Return a fresh SessionManager with a mocked AuditLogger."""
    audit = MagicMock()
    return SessionManager(audit_logger=audit, adapter=adapter)


def _register(
    manager: SessionManager,
    session_id: str = "s1",
    container_id: str = "c1",
    agent_id: str = "a1",
    policy: Policy | None = None,
) -> None:
    manager.register_session(
        session_id=session_id,
        container_id=container_id,
        agent_id=agent_id,
        process=None,
        policy=policy or Policy(),
    )


# ---------------------------------------------------------------------------
# Cleanup handler registration (Req 9.2)
# ---------------------------------------------------------------------------

class TestCleanupHandlerRegistration:
    """Handlers must be registered exactly once, on the first session creation."""

    def test_atexit_registered_on_first_session(self):
        manager = _make_manager()
        with patch("atexit.register") as mock_register:
            _register(manager)
            mock_register.assert_called_once_with(manager.destroy_all)

    def test_atexit_not_registered_again_on_second_session(self):
        manager = _make_manager()
        with patch("atexit.register") as mock_register:
            _register(manager, session_id="s1")
            _register(manager, session_id="s2")
            mock_register.assert_called_once()

    def test_sigterm_handler_registered_on_first_session(self):
        manager = _make_manager()
        with patch("signal.signal") as mock_signal:
            _register(manager)
            registered_sigs = [c.args[0] for c in mock_signal.call_args_list]
            assert signal.SIGTERM in registered_sigs

    def test_sigint_handler_registered_on_first_session(self):
        manager = _make_manager()
        with patch("signal.signal") as mock_signal:
            _register(manager)
            registered_sigs = [c.args[0] for c in mock_signal.call_args_list]
            assert signal.SIGINT in registered_sigs

    def test_signal_handlers_not_registered_again_on_second_session(self):
        manager = _make_manager()
        with patch("signal.signal") as mock_signal:
            _register(manager, session_id="s1")
            first_count = mock_signal.call_count
            _register(manager, session_id="s2")
            assert mock_signal.call_count == first_count

    def test_handlers_registered_flag_set_after_first_session(self):
        manager = _make_manager()
        assert manager._handlers_registered is False
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager)
        assert manager._handlers_registered is True


# ---------------------------------------------------------------------------
# list_sessions() (Req 9.3)
# ---------------------------------------------------------------------------

class TestListSessions:
    """list_sessions() must return accurate snapshots of active sessions."""

    def test_empty_before_any_session(self):
        manager = _make_manager()
        assert manager.list_sessions() == []

    def test_single_session_returned(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1", container_id="c1", agent_id="a1")

        sessions = manager.list_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.session_id == "s1"
        assert s.container_id == "c1"
        assert s.agent_id == "a1"
        assert s.status == "running"

    def test_multiple_sessions_all_returned(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1", container_id="c1")
            _register(manager, session_id="s2", container_id="c2")
            _register(manager, session_id="s3", container_id="c3")

        ids = {s.session_id for s in manager.list_sessions()}
        assert ids == {"s1", "s2", "s3"}

    def test_returns_session_info_instances(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager)

        for s in manager.list_sessions():
            assert isinstance(s, SessionInfo)

    def test_started_at_is_iso8601_string(self):
        import re
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager)

        s = manager.list_sessions()[0]
        # Basic ISO 8601 UTC pattern: ends with +00:00 or Z
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", s.started_at)

    def test_list_is_snapshot_not_live_reference(self):
        """Mutating the returned list must not affect the registry."""
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1")

        snapshot = manager.list_sessions()
        snapshot.clear()

        assert len(manager.list_sessions()) == 1


# ---------------------------------------------------------------------------
# Session removal after completion (Req 9.3)
# ---------------------------------------------------------------------------

class TestSessionRemovalAfterCompletion:
    """Sessions must be removed from the registry once they complete."""

    @pytest.mark.asyncio
    async def test_session_removed_on_successful_completion(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_async") as mock_destroy:
            mock_destroy.return_value = None
            _register(manager, session_id="s1")
            assert len(manager.list_sessions()) == 1

            await manager.complete_session("s1", exit_code=0)

        assert manager.list_sessions() == []

    @pytest.mark.asyncio
    async def test_session_removed_on_failed_completion(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_async") as mock_destroy:
            mock_destroy.return_value = None
            _register(manager, session_id="s1")
            await manager.complete_session("s1", exit_code=1)

        assert manager.list_sessions() == []

    @pytest.mark.asyncio
    async def test_only_completed_session_removed(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_async") as mock_destroy:
            mock_destroy.return_value = None
            _register(manager, session_id="s1")
            _register(manager, session_id="s2")

            await manager.complete_session("s1", exit_code=0)

        remaining = manager.list_sessions()
        assert len(remaining) == 1
        assert remaining[0].session_id == "s2"

    @pytest.mark.asyncio
    async def test_complete_nonexistent_session_is_noop(self):
        """Completing an unknown session ID must not raise."""
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"):
            await manager.complete_session("does-not-exist", exit_code=0)

        assert manager.list_sessions() == []

    @pytest.mark.asyncio
    async def test_destroy_container_called_on_completion(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_async") as mock_destroy:
            mock_destroy.return_value = None
            _register(manager, session_id="s1", container_id="c1", agent_id="a1")
            await manager.complete_session("s1", exit_code=0)

        mock_destroy.assert_called_once_with("c1", "s1", "a1", audit_logger=ANY)

    def test_destroy_all_clears_registry(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_sync"):
            _register(manager, session_id="s1")
            _register(manager, session_id="s2")

            manager.destroy_all()

        assert manager.list_sessions() == []

    def test_destroy_all_calls_destroy_container_for_each_session(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_sync") as mock_destroy:
            _register(manager, session_id="s1", container_id="c1")
            _register(manager, session_id="s2", container_id="c2")

            manager.destroy_all()

        destroyed = {c.args[0] for c in mock_destroy.call_args_list}
        assert destroyed == {"c1", "c2"}


# ---------------------------------------------------------------------------
# get_session_metrics() (Req 5.4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetSessionMetrics:
    """get_session_metrics() must return CPU/memory data for active sessions
    and raise KeyError for unknown session IDs."""

    async def test_metrics_returned_for_active_session(self):
        adapter = await _make_mock_adapter()
        adapter.get_container_stats.return_value = ContainerStats(cpu_percent=12.5, memory_mb=256.0, memory_limit_mb=512.0)
        manager = _make_manager(adapter=adapter)
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1", container_id="c1")

        metrics = await manager.get_session_metrics("s1")

        assert metrics.cpu_percent == pytest.approx(12.5)
        assert metrics.memory_mb == pytest.approx(256.0)

    async def test_metrics_returns_session_metrics_instance(self):
        adapter = await _make_mock_adapter()
        manager = _make_manager(adapter=adapter)
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1", container_id="c1")

        metrics = await manager.get_session_metrics("s1")
        assert isinstance(metrics, SessionMetrics)

    async def test_metrics_zero_when_adapter_fails(self):
        adapter = await _make_mock_adapter()
        adapter.get_container_stats.side_effect = Exception("Stats failed")
        manager = _make_manager(adapter=adapter)
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1", container_id="c1")

        metrics = await manager.get_session_metrics("s1")

        assert metrics.cpu_percent == 0.0
        assert metrics.memory_mb == 0.0

    async def test_adapter_stats_called_with_correct_container_id(self):
        adapter = await _make_mock_adapter()
        manager = _make_manager(adapter=adapter)
        with patch("atexit.register"), patch("signal.signal"):
            _register(manager, session_id="s1", container_id="container-abc")

        await manager.get_session_metrics("s1")

        adapter.get_container_stats.assert_called_once_with("container-abc")

    async def test_raises_key_error_for_unknown_session(self):
        manager = _make_manager()
        with pytest.raises(KeyError, match="not-a-session"):
            await manager.get_session_metrics("not-a-session")

    async def test_raises_key_error_after_session_completes(self):
        manager = _make_manager()
        with patch("atexit.register"), patch("signal.signal"), \
             patch.object(manager, "destroy_container_async") as mock_destroy:
            mock_destroy.return_value = None
            _register(manager, session_id="s1")
            await manager.complete_session("s1", exit_code=0)

        with pytest.raises(KeyError):
            await manager.get_session_metrics("s1")

