"""
Snapshot Module

Takes snapshots of metrics, logs, and errors for analysis.
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from kubernetes import client, config
from kubernetes.client import CoreV1Api, CustomObjectsApi

logger = logging.getLogger(__name__)


class SnapshotType(str, Enum):
    """Types of snapshots."""

    METRIC = "metric"
    LOG = "log"
    ERROR = "error"
    EVENT = "event"
    STATE = "state"
    TRACE = "trace"


@dataclass
class Snapshot:
    """
    A snapshot of system state at a point in time.

    Used for:
    - Error tracking
    - Performance analysis
    - Root cause analysis
    - Trend detection
    """

    id: str
    snapshot_type: SnapshotType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""  # Which agent took the snapshot
    component: str = ""  # Which component this is about

    # Content
    metric_name: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    metric_labels: dict[str, str] | None = None

    error_type: str | None = None
    error_message: str | None = None
    error_stack: str | None = None

    log_messages: list[str] | None = None
    log_count: int | None = None

    event_type: str | None = None
    event_data: dict[str, Any] | None = None

    state_snapshot: dict[str, Any] | None = None

    # Metadata
    severity: str = "info"  # critical, error, warning, info
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert snapshot to dictionary."""
        data = asdict(self)
        data["snapshot_type"] = self.snapshot_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Snapshot":
        """Create snapshot from dictionary."""
        data["snapshot_type"] = SnapshotType(data["snapshot_type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)

    @classmethod
    def metric_snapshot(
        cls,
        metric_name: str,
        value: float,
        unit: str = "",
        labels: dict | None = None,
        source: str = "",
        component: str = "",
    ) -> "Snapshot":
        """Create a metric snapshot."""
        import hashlib

        snapshot_id = hashlib.md5(
            f"{metric_name}{value}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        return cls(
            id=f"ms-{snapshot_id}",
            snapshot_type=SnapshotType.METRIC,
            source=source,
            component=component,
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            metric_labels=labels,
        )

    @classmethod
    def error_snapshot(
        cls,
        error_type: str,
        error_message: str,
        error_stack: str | None = None,
        source: str = "",
        component: str = "",
        severity: str = "error",
    ) -> "Snapshot":
        """Create an error snapshot."""
        import hashlib

        snapshot_id = hashlib.md5(
            f"{error_type}{error_message}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        return cls(
            id=f"es-{snapshot_id}",
            snapshot_type=SnapshotType.ERROR,
            source=source,
            component=component,
            error_type=error_type,
            error_message=error_message,
            error_stack=error_stack,
            severity=severity,
        )

    @classmethod
    def log_snapshot(
        cls,
        messages: list[str],
        log_count: int | None = None,
        source: str = "",
        component: str = "",
        severity: str = "info",
    ) -> "Snapshot":
        """Create a log snapshot."""
        import hashlib

        snapshot_id = hashlib.md5(
            f"{len(messages)}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:12]

        return cls(
            id=f"ls-{snapshot_id}",
            snapshot_type=SnapshotType.LOG,
            source=source,
            component=component,
            log_messages=messages[-100:],  # Keep last 100 messages
            log_count=log_count or len(messages),
            severity=severity,
        )


class SnapshotStore:
    """
    Persistent storage for snapshots.

    Uses Kubernetes ConfigMaps for storage.
    """

    def __init__(
        self,
        namespace: str = "spot-render-ai-agents",
        retention_count: int = 1000,
        retention_hours: int = 72,
    ):
        self.namespace = namespace
        self.retention_count = retention_count
        self.retention_hours = retention_hours
        self._v1: CoreV1Api | None = None
        self._custom: CustomObjectsApi | None = None
        self._snapshots: list[Snapshot] = []
        self._configmap_name = "agent-snapshots"

    async def initialize(self) -> None:
        """Initialize Kubernetes connections."""
        try:
            config.load_incluster_config()
            self._v1 = CoreV1Api()
            self._custom = CustomObjectsApi()
            await self._ensure_configmap()
            await self._load_snapshots()
            self.logger.info("SnapshotStore initialized")
        except Exception as e:
            self.logger.warning(f"Kubernetes not available: {e}")
            self._v1 = None

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("snapshot_store")

    async def _ensure_configmap(self) -> None:
        """Ensure ConfigMap exists."""
        if not self._v1:
            return

        try:
            self._v1.read_namespaced_config_map(self._configmap_name, self.namespace)
        except client.ApiException as e:
            if e.status == 404:
                cm = client.V1ConfigMap(
                    metadata=client.V1ObjectMeta(
                        name=self._configmap_name,
                        namespace=self.namespace,
                    ),
                    data={"snapshots": "[]"},
                )
                self._v1.create_namespaced_config_map(self.namespace, cm)

    async def _load_snapshots(self) -> None:
        """Load snapshots from ConfigMap."""
        if not self._v1:
            return

        try:
            cm = self._v1.read_namespaced_config_map(self._configmap_name, self.namespace)
            snapshots_data = json.loads(cm.data.get("snapshots", "[]"))
            self._snapshots = [Snapshot.from_dict(s) for s in snapshots_data]
            self.logger.info(f"Loaded {len(self._snapshots)} snapshots")
        except Exception as e:
            self.logger.error(f"Failed to load snapshots: {e}")

    async def _save_snapshots(self) -> None:
        """Save snapshots to ConfigMap."""
        if not self._v1:
            return

        try:
            cm = self._v1.read_namespaced_config_map(self._configmap_name, self.namespace)
            snapshots_data = [s.to_dict() for s in self._snapshots]
            cm.data = {"snapshots": json.dumps(snapshots_data)}
            self._v1.replace_namespaced_config_map(self._configmap_name, self.namespace, cm)
        except Exception as e:
            self.logger.error(f"Failed to save snapshots: {e}")

    async def store(self, snapshot: Snapshot) -> None:
        """Store a snapshot."""
        self._snapshots.append(snapshot)
        await self._apply_retention()
        await self._save_snapshots()

    async def store_batch(self, snapshots: list[Snapshot]) -> None:
        """Store multiple snapshots."""
        self._snapshots.extend(snapshots)
        await self._apply_retention()
        await self._save_snapshots()

    async def _apply_retention(self) -> None:
        """Apply retention policies."""
        now = datetime.utcnow()

        # Filter by count
        if len(self._snapshots) > self.retention_count:
            self._snapshots = self._snapshots[-self.retention_count :]

        # Filter by age
        cutoff = now - timedelta(hours=self.retention_hours)
        self._snapshots = [s for s in self._snapshots if s.timestamp > cutoff]

    async def query(
        self,
        snapshot_type: SnapshotType | None = None,
        component: str | None = None,
        severity: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Snapshot]:
        """Query snapshots with filters."""
        results = self._snapshots

        if snapshot_type:
            results = [s for s in results if s.snapshot_type == snapshot_type]

        if component:
            results = [s for s in results if s.component == component]

        if severity:
            results = [s for s in results if s.severity == severity]

        if since:
            results = [s for s in results if s.timestamp > since]

        # Sort by timestamp descending
        results.sort(key=lambda s: s.timestamp, reverse=True)

        return results[:limit]

    async def get_error_snapshots(
        self,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[Snapshot]:
        """Get recent error snapshots."""
        return await self.query(
            snapshot_type=SnapshotType.ERROR,
            since=since,
            limit=limit,
        )

    async def get_metric_snapshots(
        self,
        metric_name: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Snapshot]:
        """Get snapshots for a specific metric."""
        results = await self.query(
            snapshot_type=SnapshotType.METRIC,
            since=since,
            limit=limit * 2,  # Get more, then filter
        )

        return [s for s in results if s.metric_name == metric_name][:limit]

    async def get_recent_errors(self, hours: int = 24) -> list[Snapshot]:
        """Get recent errors from the last N hours."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return await self.get_error_snapshots(since=since)

    def get_stats(self) -> dict:
        """Get snapshot statistics."""
        by_type = {}
        by_severity = {}
        by_component = {}

        for s in self._snapshots:
            by_type[s.snapshot_type.value] = by_type.get(s.snapshot_type.value, 0) + 1
            by_severity[s.severity] = by_severity.get(s.severity, 0) + 1
            if s.component:
                by_component[s.component] = by_component.get(s.component, 0) + 1

        return {
            "total": len(self._snapshots),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_component": by_component,
        }


class MetricSnapshotter:
    """
    Takes periodic snapshots of cluster metrics.

    Designed to capture baseline and anomaly snapshots.
    """

    def __init__(
        self,
        store: SnapshotStore,
        agent_name: str,
        interval: int = 60,  # seconds
    ):
        self.store = store
        self.agent_name = agent_name
        self.interval = interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start periodic snapshots."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._snapshot_loop())
        self.logger.info(f"MetricSnapshotter started with {self.interval}s interval")

    async def stop(self) -> None:
        """Stop periodic snapshots."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _snapshot_loop(self) -> None:
        """Main snapshot loop."""
        while self._running:
            try:
                await self.take_metric_snapshots()
                await asyncio.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"Error in snapshot loop: {e}")

    async def take_metric_snapshots(self) -> None:
        """Take snapshots of current metrics."""
        if not self._v1:
            try:
                config.load_incluster_config()
                self._v1 = CoreV1Api()
            except Exception:
                self.logger.warning("Cannot load Kubernetes config")
                return

        try:
            # Get node metrics
            metrics = await self._get_node_metrics()

            for metric_name, value in metrics.items():
                snapshot = Snapshot.metric_snapshot(
                    metric_name=metric_name,
                    value=value,
                    source=self.agent_name,
                    component="node",
                )
                await self.store.store(snapshot)

        except Exception as e:
            self.logger.error(f"Failed to take metric snapshots: {e}")

    async def _get_node_metrics(self) -> dict[str, float]:
        """Get current node metrics."""
        if not self._v1:
            return {}

        metrics = {}

        try:
            # Get CPU and memory usage from nodes
            nodes = self._v1.list_node()

            for node in nodes.items:
                # Extract CPU
                cpu = node.status.allocatable.get("cpu", "0")
                metrics["node_cpu_allocatable"] = int(cpu)

                # Extract memory (convert to GB)
                mem = node.status.allocatable.get("memory", "0")
                if isinstance(mem, str) and mem.endswith("Gi"):
                    mem_gb = float(mem.replace("Gi", ""))
                elif isinstance(mem, str) and mem.endswith("G"):
                    mem_gb = float(mem.replace("G", ""))
                else:
                    mem_gb = 0
                metrics["node_memory_allocatable_gb"] = mem_gb

        except Exception as e:
            self.logger.error(f"Failed to get node metrics: {e}")

        return metrics
