"""Tests for SRE Agent"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.agent_base import AgentConfig, AgentProfile
from core.snapshot import Snapshot, SnapshotType


class TestSREAgent:
    """Test cases for SRE Agent."""

    @pytest.fixture
    def agent_config(self):
        """Create test configuration."""
        return AgentConfig(
            name="test-sre-agent",
            profile=AgentProfile.SRE,
            namespace="test-namespace",
            log_level="DEBUG",
        )

    @pytest.fixture
    def mock_k8s(self):
        """Mock Kubernetes client."""
        with patch("agents.sre_agent.config") as mock_config:
            mock_config.load_incluster_config = MagicMock()
            yield mock_config

    def test_agent_config(self, agent_config):
        """Test agent configuration."""
        assert agent_config.name == "test-sre-agent"
        assert agent_config.profile == AgentProfile.SRE
        assert agent_config.namespace == "test-namespace"

    def test_snapshot_creation(self):
        """Test snapshot creation."""
        snapshot = Snapshot.error_snapshot(
            error_type="TestError",
            error_message="Test error message",
            source="test-agent",
            component="test-component",
            severity="error",
        )

        assert snapshot.error_type == "TestError"
        assert snapshot.error_message == "Test error message"
        assert snapshot.snapshot_type == SnapshotType.ERROR
        assert snapshot.severity == "error"

    def test_metric_snapshot(self):
        """Test metric snapshot creation."""
        snapshot = Snapshot.metric_snapshot(
            metric_name="cpu_usage",
            value=75.5,
            unit="percent",
            labels={"node": "test-node"},
            source="test-agent",
            component="node",
        )

        assert snapshot.metric_name == "cpu_usage"
        assert snapshot.metric_value == 75.5
        assert snapshot.metric_unit == "percent"
        assert snapshot.snapshot_type == SnapshotType.METRIC


class TestDevOpsAgent:
    """Test cases for DevOps Agent."""

    @pytest.fixture
    def agent_config(self):
        """Create test configuration."""
        return AgentConfig(
            name="test-devops-agent",
            profile=AgentProfile.DEVOPS,
            namespace="test-namespace",
            log_level="DEBUG",
        )

    def test_agent_config(self, agent_config):
        """Test agent configuration."""
        assert agent_config.name == "test-devops-agent"
        assert agent_config.profile == AgentProfile.DEVOPS


class TestSelfHealingAgent:
    """Test cases for Self-Healing Agent."""

    @pytest.fixture
    def agent_config(self):
        """Create test configuration."""
        return AgentConfig(
            name="test-selfhealing-agent",
            profile=AgentProfile.SELF_HEALING,
            namespace="test-namespace",
            log_level="DEBUG",
        )

    def test_agent_config(self, agent_config):
        """Test agent configuration."""
        assert agent_config.name == "test-selfhealing-agent"
        assert agent_config.profile == AgentProfile.SELF_HEALING


class TestSnapshotStore:
    """Test cases for Snapshot Store."""

    def test_snapshot_to_dict(self):
        """Test snapshot serialization."""
        snapshot = Snapshot.error_snapshot(
            error_type="TestError",
            error_message="Test message",
            source="test-agent",
            component="test",
            severity="error",
        )

        data = snapshot.to_dict()

        assert data["error_type"] == "TestError"
        assert data["snapshot_type"] == "error"
        assert "timestamp" in data

    def test_snapshot_from_dict(self):
        """Test snapshot deserialization."""
        data = {
            "id": "es-123456",
            "snapshot_type": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "test",
            "component": "test",
            "error_type": "TestError",
            "error_message": "Test message",
            "error_stack": None,
            "severity": "error",
            "tags": [],
            "metadata": {},
            "metric_name": None,
            "metric_value": None,
            "metric_unit": None,
            "metric_labels": None,
            "log_messages": None,
            "log_count": None,
            "event_type": None,
            "event_data": None,
            "state_snapshot": None,
        }

        snapshot = Snapshot.from_dict(data)

        assert snapshot.error_type == "TestError"
        assert snapshot.snapshot_type == SnapshotType.ERROR
