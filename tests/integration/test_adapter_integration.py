"""Integration tests for adapter switching and validation.

These tests verify that adapters can be switched at runtime, work correctly
together, and maintain data consistency across different implementations.
"""

import asyncio
import pytest
from pathlib import Path

from isolated_agents_sdk.adapters import (
    AdapterConfig,
    AdapterFactory,
    AdapterRegistry,
    get_registry,
    load_config,
)
from isolated_agents_sdk.adapters.storage.local import LocalStorageAdapter
from isolated_agents_sdk.adapters.audit.file import FileAuditAdapter
from isolated_agents_sdk.adapters.policy.default import DefaultPolicyValidator
from isolated_agents_sdk.adapters.audit.types import EventType, AuditQuery
from isolated_agents_sdk.models import Policy


class TestAdapterRegistryIntegration:
    """Test adapter registry functionality."""
    
    @pytest.mark.asyncio
    async def test_registry_initialization(self, reset_registry, temp_dir):
        """Test registry initialization with configuration."""
        config = AdapterConfig(
            storage_adapter="local",
            storage_config={"base_path": str(temp_dir / "storage")},
            audit_adapter="file",
            audit_config={"log_path": str(temp_dir / "audit_logs")},
            policy_adapter="default",
        )
        
        registry = get_registry()
        registry.initialize_from_config(config)
        
        # Verify adapters are registered
        adapters = registry.list_adapters()
        assert "local" in adapters["storage"]
        assert "file" in adapters["audit"]
        assert "default" in adapters["policy"]
        
        # Verify adapters can be retrieved
        storage = registry.get_storage_adapter()
        audit = registry.get_audit_adapter()
        policy = registry.get_policy_adapter()
        
        assert isinstance(storage, LocalStorageAdapter)
        assert isinstance(audit, FileAuditAdapter)
        assert isinstance(policy, DefaultPolicyValidator)
    
    @pytest.mark.asyncio
    async def test_registry_adapter_switching(self, reset_registry, temp_dir):
        """Test switching between different adapter instances."""
        registry = get_registry()
        
        # Register multiple storage adapters
        storage1 = LocalStorageAdapter(base_path=str(temp_dir / "storage1"))
        storage2 = LocalStorageAdapter(base_path=str(temp_dir / "storage2"))
        
        registry.register_storage_adapter("storage1", storage1)
        registry.register_storage_adapter("storage2", storage2)
        
        # Get first adapter
        adapter1 = registry.get_storage_adapter("storage1")
        assert adapter1 is storage1
        
        # Switch to second adapter
        registry.set_default_storage_adapter("storage2")
        adapter2 = registry.get_storage_adapter()
        assert adapter2 is storage2
        assert adapter2 is not adapter1
    
    @pytest.mark.asyncio
    async def test_registry_thread_safety(self, reset_registry):
        """Test registry thread safety with concurrent access."""
        registry = get_registry()
        
        # Register adapter
        storage = LocalStorageAdapter(base_path="/tmp/test")
        registry.register_storage_adapter("local", storage)
        registry.set_default_storage_adapter("local")
        
        # Concurrent access
        async def get_adapter():
            return registry.get_storage_adapter()
        
        tasks = [get_adapter() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        
        # All should return the same instance
        assert all(r is storage for r in results)


class TestStorageAdapterIntegration:
    """Test storage adapter integration."""
    
    @pytest.mark.asyncio
    async def test_storage_lifecycle(self, reset_registry, temp_dir):
        """Test complete storage adapter lifecycle."""
        storage = LocalStorageAdapter(base_path=str(temp_dir / "storage"))
        await storage.initialize()
        
        # Store artifact
        data = b"test data"
        location = await storage.store_artifact(
            session_id="test-session",
            artifact_name="test.txt",
            data=data,
            content_type="text/plain",
        )
        
        assert "test-session" in location.path
        assert "test.txt" in location.path
        
        # Retrieve artifact
        retrieved = await storage.retrieve_artifact(
            session_id="test-session",
            artifact_name="test.txt",
        )
        assert retrieved == data
        
        # List artifacts
        artifacts = await storage.list_artifacts("test-session")
        assert len(artifacts) == 1
        assert artifacts[0].artifact_name == "test.txt"
        
        # Get metadata
        metadata = await storage.get_artifact_metadata(
            session_id="test-session",
            artifact_name="test.txt",
        )
        assert metadata.size_bytes == len(data)
        assert metadata.content_type == "text/plain"
        
        # Delete artifact
        await storage.delete_artifact(
            session_id="test-session",
            artifact_name="test.txt",
        )
        
        # Verify deletion
        artifacts = await storage.list_artifacts("test-session")
        assert len(artifacts) == 0
        
        await storage.cleanup()
    
    @pytest.mark.asyncio
    async def test_storage_multiple_sessions(self, reset_registry, temp_dir):
        """Test storage with multiple sessions."""
        storage = LocalStorageAdapter(base_path=str(temp_dir / "storage"))
        await storage.initialize()
        
        # Store artifacts in different sessions
        sessions = ["session1", "session2", "session3"]
        for session_id in sessions:
            await storage.store_artifact(
                session_id=session_id,
                artifact_name="test.txt",
                data=f"data for {session_id}".encode(),
            )
        
        # Verify each session has its artifact
        for session_id in sessions:
            artifacts = await storage.list_artifacts(session_id)
            assert len(artifacts) == 1
            
            data = await storage.retrieve_artifact(session_id, "test.txt")
            assert data == f"data for {session_id}".encode()
        
        await storage.cleanup()
    
    @pytest.mark.asyncio
    async def test_storage_adapter_switching(self, reset_registry, temp_dir):
        """Test switching between storage adapters."""
        registry = get_registry()
        
        # Create two storage adapters
        storage1 = LocalStorageAdapter(base_path=str(temp_dir / "storage1"))
        storage2 = LocalStorageAdapter(base_path=str(temp_dir / "storage2"))
        
        await storage1.initialize()
        await storage2.initialize()
        
        registry.register_storage_adapter("storage1", storage1)
        registry.register_storage_adapter("storage2", storage2)
        
        # Store in first adapter
        registry.set_default_storage_adapter("storage1")
        adapter1 = registry.get_storage_adapter()
        await adapter1.store_artifact(
            session_id="test",
            artifact_name="file1.txt",
            data=b"data1",
        )
        
        # Store in second adapter
        registry.set_default_storage_adapter("storage2")
        adapter2 = registry.get_storage_adapter()
        await adapter2.store_artifact(
            session_id="test",
            artifact_name="file2.txt",
            data=b"data2",
        )
        
        # Verify isolation
        artifacts1 = await adapter1.list_artifacts("test")
        artifacts2 = await adapter2.list_artifacts("test")
        
        assert len(artifacts1) == 1
        assert artifacts1[0].artifact_name == "file1.txt"
        
        assert len(artifacts2) == 1
        assert artifacts2[0].artifact_name == "file2.txt"
        
        await storage1.cleanup()
        await storage2.cleanup()


class TestAuditAdapterIntegration:
    """Test audit adapter integration."""
    
    @pytest.mark.asyncio
    async def test_audit_lifecycle(self, reset_registry, temp_dir):
        """Test complete audit adapter lifecycle."""
        log_path = temp_dir / "audit_logs"
        audit = FileAuditAdapter(log_path=str(log_path))
        await audit.initialize()
        
        # Log events
        event_id1 = await audit.log_event(
            event_type=EventType.AGENT_STARTED,
            session_id="test-session",
            agent_id="test-agent",
            payload={"message": "Agent started"},
        )
        
        await asyncio.sleep(0.01)  # Ensure distinct timestamps
        
        event_id2 = await audit.log_event(
            event_type=EventType.AGENT_COMPLETED,
            session_id="test-session",
            agent_id="test-agent",
            payload={"message": "Agent completed"},
        )
        
        assert event_id1 != event_id2
        
        # Query events
        query = AuditQuery(session_id="test-session")
        events = await audit.query_events(query)
        
        assert len(events) == 2
        assert events[0].event_type == EventType.AGENT_COMPLETED  # Most recent first
        assert events[1].event_type == EventType.AGENT_STARTED
        
        # Get specific event
        event = await audit.get_event(event_id1)
        assert event.event_id == event_id1
        assert event.event_type == EventType.AGENT_STARTED
        
        # Query all events for statistics
        all_query = AuditQuery(session_id="test-session")
        all_events = await audit.query_events(all_query)
        assert len(all_events) == 2
        
        await audit.cleanup()
    
    @pytest.mark.asyncio
    async def test_audit_query_filtering(self, reset_registry, temp_dir):
        """Test audit event query filtering."""
        log_path = temp_dir / "audit_logs"
        audit = FileAuditAdapter(log_path=str(log_path))
        await audit.initialize()
        
        # Log various events
        await audit.log_event(
            event_type=EventType.AGENT_STARTED,
            session_id="session1",
            agent_id="agent1",
        )
        await audit.log_event(
            event_type=EventType.AGENT_COMPLETED,
            session_id="session1",
            agent_id="agent1",
        )
        await audit.log_event(
            event_type=EventType.AGENT_STARTED,
            session_id="session2",
            agent_id="agent2",
        )
        
        # Query by session
        query1 = AuditQuery(session_id="session1")
        events1 = await audit.query_events(query1)
        assert len(events1) == 2
        
        # Query by agent
        query2 = AuditQuery(agent_id="agent2")
        events2 = await audit.query_events(query2)
        assert len(events2) == 1
        
        # Query by event type
        query3 = AuditQuery(event_types=[EventType.AGENT_STARTED])
        events3 = await audit.query_events(query3)
        assert len(events3) == 2
        
        await audit.cleanup()


class TestPolicyAdapterIntegration:
    """Test policy adapter integration."""
    
    @pytest.mark.asyncio
    async def test_policy_validation(self, reset_registry):
        """Test policy validation."""
        validator = DefaultPolicyValidator()
        await validator.initialize()
        
        # Valid policy
        valid_policy = Policy(
            cpu_cores=2.0,
            memory_mb=1024,
        )
        
        result = await validator.validate_policy(valid_policy)
        assert result.is_valid
        assert len(result.errors) == 0
        
        # Invalid policy (negative values)
        invalid_policy = Policy(
            cpu_cores=-1.0,
            memory_mb=-512,
        )
        
        result = await validator.validate_policy(invalid_policy)
        assert not result.is_valid
        assert len(result.errors) > 0
        
        await validator.cleanup()
    
    @pytest.mark.asyncio
    async def test_policy_batch_validation(self, reset_registry):
        """Test batch policy validation."""
        validator = DefaultPolicyValidator()
        await validator.initialize()
        
        policies = [
            Policy(cpu_cores=1.0, memory_mb=512),
            Policy(cpu_cores=2.0, memory_mb=1024),
            Policy(cpu_cores=-1.0, memory_mb=2048),  # Invalid
        ]
        
        results = await validator.validate_batch(policies)
        
        assert len(results) == 3
        assert results[0].is_valid
        assert results[1].is_valid
        assert not results[2].is_valid
        
        await validator.cleanup()


class TestConfigurationIntegration:
    """Test configuration system integration."""
    
    @pytest.mark.asyncio
    async def test_config_from_dict(self, reset_registry, temp_dir):
        """Test configuration from dictionary."""
        config_dict = {
            "storage_adapter": "local",
            "storage_config": {"base_path": str(temp_dir / "storage")},
            "audit_adapter": "file",
            "audit_config": {"log_path": str(temp_dir / "audit_logs")},
            "policy_adapter": "default",
        }
        
        config = AdapterConfig.from_dict(config_dict)
        
        assert config.storage_adapter == "local"
        assert config.audit_adapter == "file"
        assert config.policy_adapter == "default"
        
        # Initialize registry
        registry = get_registry()
        registry.initialize_from_config(config)
        
        # Verify adapters work
        storage = registry.get_storage_adapter()
        await storage.initialize()
        
        await storage.store_artifact(
            session_id="test",
            artifact_name="test.txt",
            data=b"test",
        )
        
        artifacts = await storage.list_artifacts("test")
        assert len(artifacts) == 1
        
        await storage.cleanup()
    
    @pytest.mark.asyncio
    async def test_config_validation(self, reset_registry):
        """Test configuration validation."""
        # Valid configuration
        valid_config = AdapterConfig(
            container_adapter="podman",
            storage_adapter="local",
            audit_adapter="file",
            policy_adapter="default",
        )
        
        valid_config.validate()  # Should not raise
        
        # Invalid configuration
        invalid_config = AdapterConfig(
            container_adapter="invalid",
            storage_adapter="local",
            audit_adapter="file",
            policy_adapter="default",
        )
        
        with pytest.raises(ValueError, match="Invalid container adapter"):
            invalid_config.validate()
    
    @pytest.mark.asyncio
    async def test_config_merging(self, reset_registry):
        """Test configuration merging."""
        base_config = AdapterConfig(
            storage_adapter="local",
            storage_config={"base_path": "/base"},
        )
        
        override_config = AdapterConfig(
            storage_config={"base_path": "/override", "create_dirs": True},
        )
        
        merged = base_config.merge(override_config)
        
        assert merged.storage_adapter == "local"
        assert merged.storage_config["base_path"] == "/override"
        assert merged.storage_config["create_dirs"] is True


class TestEndToEndIntegration:
    """Test end-to-end adapter integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, reset_registry, temp_dir):
        """Test complete workflow with all adapters."""
        # Initialize configuration
        config = AdapterConfig(
            storage_adapter="local",
            storage_config={"base_path": str(temp_dir / "storage")},
            audit_adapter="file",
            audit_config={"log_path": str(temp_dir / "audit_logs")},
            policy_adapter="default",
        )
        
        registry = get_registry()
        registry.initialize_from_config(config)
        
        # Get adapters
        storage = registry.get_storage_adapter()
        audit = registry.get_audit_adapter()
        policy_validator = registry.get_policy_adapter()
        
        await storage.initialize()
        await audit.initialize()
        await policy_validator.initialize()
        
        # Validate policy
        test_policy = Policy(cpu_cores=2.0, memory_mb=1024)
        validation_result = await policy_validator.validate_policy(test_policy)
        assert validation_result.is_valid
        
        # Log agent start
        await audit.log_event(
            event_type=EventType.AGENT_STARTED,
            session_id="workflow-session",
            agent_id="workflow-agent",
            payload={"policy": "validated"},
        )
        
        # Store artifact
        await storage.store_artifact(
            session_id="workflow-session",
            artifact_name="output.txt",
            data=b"workflow output",
        )
        
        # Log agent completion
        await audit.log_event(
            event_type=EventType.AGENT_COMPLETED,
            session_id="workflow-session",
            agent_id="workflow-agent",
            payload={"artifacts": 1},
        )
        
        # Verify workflow
        artifacts = await storage.list_artifacts("workflow-session")
        assert len(artifacts) == 1
        
        query = AuditQuery(session_id="workflow-session")
        events = await audit.query_events(query)
        assert len(events) == 2
        
        # Cleanup
        await storage.cleanup()
        await audit.cleanup()
        await policy_validator.cleanup()
    
    @pytest.mark.asyncio
    async def test_adapter_isolation(self, reset_registry, temp_dir):
        """Test that adapters are properly isolated."""
        registry = get_registry()
        
        # Create isolated storage adapters
        storage1 = LocalStorageAdapter(base_path=str(temp_dir / "storage1"))
        storage2 = LocalStorageAdapter(base_path=str(temp_dir / "storage2"))
        
        await storage1.initialize()
        await storage2.initialize()
        
        registry.register_storage_adapter("storage1", storage1)
        registry.register_storage_adapter("storage2", storage2)
        
        # Store data in both
        await storage1.store_artifact(
            session_id="test",
            artifact_name="file.txt",
            data=b"storage1 data",
        )
        
        await storage2.store_artifact(
            session_id="test",
            artifact_name="file.txt",
            data=b"storage2 data",
        )
        
        # Verify isolation
        data1 = await storage1.retrieve_artifact("test", "file.txt")
        data2 = await storage2.retrieve_artifact("test", "file.txt")
        
        assert data1 == b"storage1 data"
        assert data2 == b"storage2 data"
        assert data1 != data2
        
        await storage1.cleanup()
        await storage2.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
