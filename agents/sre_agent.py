"""
SRE Agent

Monitors metrics, logs, and alerts for the Kubernetes cluster.
Detects anomalies and generates diagnostic snapshots.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from kubernetes import client, config
from kubernetes.client import CoreV1Api, AppsV1Api

from core.agent_base import AgentBase, AgentConfig, AgentMessage, AgentProfile
from core.communication import MessageBus, SharedState
from core.llm import LLMClient
from core.rag import RAGKnowledgeBase
from core.snapshot import Snapshot, SnapshotStore, SnapshotType

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects metrics from various sources."""

    def __init__(self, namespace: str = "spot-render"):
        self.namespace = namespace
        self._v1: CoreV1Api | None = None
        self._apps_v1: AppsV1Api | None = None

    async def initialize(self) -> None:
        """Initialize Kubernetes clients."""
        try:
            config.load_incluster_config()
            self._v1 = CoreV1Api()
            self._apps_v1 = AppsV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")

    async def collect_node_metrics(self) -> dict[str, Any]:
        """Collect node-level metrics."""
        if not self._v1:
            return {}

        metrics = {"nodes": [], "timestamp": datetime.utcnow().isoformat()}

        try:
            nodes = self._v1.list_node()

            for node in nodes.items:
                node_metrics = {
                    "name": node.metadata.name,
                    "conditions": [
                        {"type": c.type, "status": c.status}
                        for c in (node.status.conditions or [])
                    ],
                    "allocatable_cpu": node.status.allocatable.get("cpu", "0"),
                    "allocatable_memory": node.status.allocatable.get("memory", "0"),
                }

                # Get usage from metrics-server if available
                # For now, use allocatable as approximation
                metrics["nodes"].append(node_metrics)

        except Exception as e:
            logger.error(f"Failed to collect node metrics: {e}")

        return metrics

    async def collect_pod_metrics(self) -> dict[str, Any]:
        """Collect pod-level metrics."""
        if not self._v1:
            return {}

        metrics = {
            "pods": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            pods = self._v1.list_namespaced_pod(self.namespace)

            for pod in pods.items:
                pod_metrics = {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "ready": f"{sum(1 for c in (pod.status.container_statuses or []) if c.ready)}/{len(pod.status.container_statuses or [])}",
                    "restarts": sum(
                        c.restart_count for c in (pod.status.container_statuses or [])
                    ),
                    "age": str(pod.metadata.creation_timestamp),
                }

                # Get container resource requests/limits
                containers = []
                for container in (pod.spec.containers or []):
                    containers.append(
                        {
                            "name": container.name,
                            "resources": {
                                "requests": container.resources.requests,
                                "limits": container.resources.limits,
                            }
                            if container.resources
                            else {},
                        }
                    )
                pod_metrics["containers"] = containers

                metrics["pods"].append(pod_metrics)

        except Exception as e:
            logger.error(f"Failed to collect pod metrics: {e}")

        return metrics

    async def collect_deployment_metrics(self) -> dict[str, Any]:
        """Collect deployment metrics."""
        if not self._apps_v1:
            return {}

        metrics = {"deployments": [], "timestamp": datetime.utcnow().isoformat()}

        try:
            deployments = self._apps_v1.list_namespaced_deployment(self.namespace)

            for deploy in deployments.items:
                deploy_metrics = {
                    "name": deploy.metadata.name,
                    "replicas": deploy.spec.replicas or 0,
                    "ready_replicas": deploy.status.ready_replicas or 0,
                    "available_replicas": deploy.status.available_replicas or 0,
                    "updated_replicas": deploy.status.updated_replicas or 0,
                    "conditions": [
                        {"type": c.type, "status": c.status}
                        for c in (deploy.status.conditions or [])
                    ],
                }
                metrics["deployments"].append(deploy_metrics)

        except Exception as e:
            logger.error(f"Failed to collect deployment metrics: {e}")

        return metrics


class LogAnalyzer:
    """Analyzes logs for patterns and anomalies."""

    def __init__(self, namespace: str = "spot-render"):
        self.namespace = namespace
        self._v1: CoreV1Api | None = None

    async def initialize(self) -> None:
        """Initialize Kubernetes client."""
        try:
            config.load_incluster_config()
            self._v1 = CoreV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")

    async def get_recent_logs(
        self,
        pod_name: str,
        container_name: str | None = None,
        tail_lines: int = 100,
    ) -> list[str]:
        """Get recent logs from a pod."""
        if not self._v1:
            return []

        try:
            logs = self._v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
                container=container_name,
                tail_lines=tail_lines,
                timestamps=True,
            )

            return logs.split("\n")

        except Exception as e:
            logger.error(f"Failed to get logs for {pod_name}: {e}")
            return []

    async def detect_error_patterns(self, logs: list[str]) -> list[dict[str, Any]]:
        """Detect common error patterns in logs."""
        error_patterns = [
            ("OOMKilled", "error"),
            ("CrashLoopBackOff", "error"),
            ("Error", "error"),
            ("Exception", "error"),
            ("Failed", "error"),
            ("Timeout", "warning"),
            ("Connection refused", "warning"),
            ("NotFound", "warning"),
        ]

        detected = []

        for i, log in enumerate(logs):
            for pattern, severity in error_patterns:
                if pattern in log:
                    detected.append(
                        {
                            "line_number": i,
                            "pattern": pattern,
                            "severity": severity,
                            "message": log[:200],  # Truncate
                        }
                    )

        return detected[:20]  # Limit results


class SREAgent(AgentBase):
    """
    SRE (Site Reliability Engineering) Agent.

    Monitors:
    - CPU, Memory, Network, Disk metrics
    - Pod status and health
    - Log patterns and errors
    - Deployment health

    Generates snapshots and alerts for anomalies.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.metrics_collector = MetricsCollector(config.namespace)
        self.log_analyzer = LogAnalyzer(config.namespace)
        self.snapshot_store = SnapshotStore(config.namespace)
        self.llm_client = LLMClient(config)
        self.rag_kb = RAGKnowledgeBase(config)
        self._message_bus: MessageBus | None = None
        self._shared_state: SharedState | None = None
        self._anomaly_threshold = 3.0  # Standard deviations

    async def initialize(self) -> None:
        """Initialize agent resources."""
        self.logger.info(f"Initializing SRE Agent: {self.config.name}")

        await self.metrics_collector.initialize()
        await self.snapshot_store.initialize()
        await self.llm_client.initialize()
        await self.rag_kb.initialize()

        self._message_bus = await MessageBus.get_instance(self.config.namespace)
        self._shared_state = SharedState(self.config.namespace)
        await self._shared_state.initialize()

        # Subscribe to message bus
        await self._message_bus.subscribe(self.config.name)

        self.logger.info("SRE Agent initialized successfully")

    async def execute_cycle(self) -> None:
        """Execute one monitoring cycle."""
        self.logger.debug("SRE Agent executing monitoring cycle")

        try:
            # Collect metrics
            node_metrics = await self.metrics_collector.collect_node_metrics()
            pod_metrics = await self.metrics_collector.collect_pod_metrics()
            deploy_metrics = await self.metrics_collector.collect_deployment_metrics()

            # Take metric snapshots
            await self._take_metric_snapshots(node_metrics, pod_metrics, deploy_metrics)

            # Check for pod issues
            await self._check_pod_health(pod_metrics)

            # Check deployment health
            await self._check_deployment_health(deploy_metrics)

            # Analyze logs for errors
            await self._analyze_error_logs()

            # Update shared state
            await self._update_shared_state(pod_metrics, deploy_metrics)

        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
            error_snapshot = Snapshot.error_snapshot(
                error_type="MonitoringCycleError",
                error_message=str(e),
                error_stack=None,
                source=self.config.name,
                severity="error",
            )
            await self.snapshot_store.store(error_snapshot)

    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages."""
        self.logger.debug(f"Received message: {message.message_type}")

        if message.message_type == "diagnose_request":
            await self._handle_diagnose_request(message)
        elif message.message_type == "status_request":
            await self._handle_status_request(message)
        elif message.message_type == "metrics_request":
            await self._handle_metrics_request(message)

    async def _take_metric_snapshots(
        self,
        node_metrics: dict,
        pod_metrics: dict,
        deploy_metrics: dict,
    ) -> None:
        """Take snapshots of collected metrics."""
        snapshots = []

        # Snapshot pod count
        if "pods" in pod_metrics:
            snapshots.append(
                Snapshot.metric_snapshot(
                    metric_name="pod_count",
                    value=len(pod_metrics["pods"]),
                    labels={"namespace": self.config.namespace},
                    source=self.config.name,
                    component="namespace",
                )
            )

        # Snapshot running pods
        running_pods = [
            p for p in pod_metrics.get("pods", []) if p.get("status") == "Running"
        ]
        snapshots.append(
            Snapshot.metric_snapshot(
                metric_name="running_pods",
                value=len(running_pods),
                labels={"namespace": self.config.namespace},
                source=self.config.name,
                component="namespace",
            )
        )

        # Snapshot deployment replicas
        for deploy in deploy_metrics.get("deployments", []):
            snapshots.append(
                Snapshot.metric_snapshot(
                    metric_name="deployment_replicas",
                    value=deploy.get("replicas", 0),
                    labels={
                        "deployment": deploy.get("name", ""),
                        "ready": str(deploy.get("ready_replicas", 0)),
                    },
                    source=self.config.name,
                    component="deployment",
                )
            )

            # Check for replicas mismatch
            replicas = deploy.get("replicas", 0)
            ready = deploy.get("ready_replicas", 0)
            if replicas != ready:
                snapshots.append(
                    Snapshot.error_snapshot(
                        error_type="ReplicaMismatch",
                        error_message=f"Deployment {deploy['name']}: {ready}/{replicas} ready",
                        source=self.config.name,
                        component="deployment",
                        severity="warning",
                    )
                )

        # Snapshot node count
        if "nodes" in node_metrics:
            snapshots.append(
                Snapshot.metric_snapshot(
                    metric_name="node_count",
                    value=len(node_metrics["nodes"]),
                    source=self.config.name,
                    component="cluster",
                )
            )

        if snapshots:
            await self.snapshot_store.store_batch(snapshots)

    async def _check_pod_health(self, pod_metrics: dict) -> None:
        """Check for unhealthy pods."""
        issues = []

        for pod in pod_metrics.get("pods", []):
            status = pod.get("status")
            restarts = pod.get("restarts", 0)

            # Check for issues
            if status != "Running" and status != "Succeeded":
                issues.append(
                    {
                        "pod": pod.get("name"),
                        "issue": f"Status: {status}",
                        "severity": "warning"
                        if status == "Pending"
                        else "error",
                    }
                )

            if restarts > 5:
                issues.append(
                    {
                        "pod": pod.get("name"),
                        "issue": f"High restarts: {restarts}",
                        "severity": "warning",
                    }
                )

        # Store issue snapshots and broadcast if critical
        for issue in issues:
            if issue["severity"] == "error":
                snapshot = Snapshot.error_snapshot(
                    error_type="PodIssue",
                    error_message=f"{issue['pod']}: {issue['issue']}",
                    source=self.config.name,
                    component="pod",
                    severity="error",
                )
                await self.snapshot_store.store(snapshot)

                # Notify other agents
                await self.broadcast(
                    "alert",
                    {
                        "type": "pod_issue",
                        "pod": issue["pod"],
                        "issue": issue["issue"],
                        "severity": issue["severity"],
                    },
                )

    async def _check_deployment_health(self, deploy_metrics: dict) -> None:
        """Check deployment health."""
        for deploy in deploy_metrics.get("deployments", []):
            ready = deploy.get("ready_replicas", 0)
            desired = deploy.get("replicas", 0)

            if ready < desired:
                snapshot = Snapshot.error_snapshot(
                    error_type="DeploymentUnhealthy",
                    error_message=f"{deploy['name']}: {ready}/{desired} replicas ready",
                    source=self.config.name,
                    component="deployment",
                    severity="warning",
                )
                await self.snapshot_store.store(snapshot)

    async def _analyze_error_logs(self) -> None:
        """Analyze logs for error patterns."""
        # Get pods with issues
        pod_metrics = await self.metrics_collector.collect_pod_metrics()

        for pod in pod_metrics.get("pods", [])[:5]:  # Check first 5 pods
            if pod.get("restarts", 0) > 0:
                logs = await self.log_analyzer.get_recent_logs(
                    pod.get("name"), tail_lines=50
                )

                if logs:
                    patterns = await self.log_analyzer.detect_error_patterns(logs)

                    if patterns:
                        # Store log snapshot
                        snapshot = Snapshot.log_snapshot(
                            messages=[p["message"] for p in patterns],
                            log_count=len(patterns),
                            source=self.config.name,
                            component="pod",
                            severity="warning",
                        )
                        await self.snapshot_store.store(snapshot)

    async def _update_shared_state(
        self,
        pod_metrics: dict,
        deploy_metrics: dict,
    ) -> None:
        """Update shared state for other agents."""
        if not self._shared_state:
            return

        # Update overall health
        running_pods = sum(
            1 for p in pod_metrics.get("pods", []) if p.get("status") == "Running"
        )
        total_pods = len(pod_metrics.get("pods", []))

        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "running_pods": running_pods,
            "total_pods": total_pods,
            "healthy": running_pods == total_pods,
            "deployments": {
                d["name"]: {
                    "ready": d.get("ready_replicas", 0),
                    "desired": d.get("replicas", 0),
                    "healthy": d.get("ready_replicas", 0) == d.get("replicas", 0),
                }
                for d in deploy_metrics.get("deployments", [])
            },
        }

        await self._shared_state.set("cluster_health", health)

    async def _handle_diagnose_request(self, message: AgentMessage) -> None:
        """Handle a diagnose request from another agent."""
        target = message.payload.get("target")
        target_type = message.payload.get("type", "pod")

        self.logger.info(f"Diagnosing {target_type}: {target}")

        # Gather diagnostic data
        if target_type == "pod":
            pod_metrics = await self.metrics_collector.collect_pod_metrics()
            pod = next(
                (p for p in pod_metrics.get("pods", []) if p.get("name") == target),
                None,
            )
            logs = await self.log_analyzer.get_recent_logs(target)
            patterns = await self.log_analyzer.detect_error_patterns(logs)

            # Use LLM to analyze
            diagnostic = await self.llm_client.analyze_diagnostic(
                symptoms=[f"Pod status: {pod.get('status') if pod else 'Unknown'}"],
                metrics=pod or {},
                logs=patterns,
            )

            # Send response
            response = AgentMessage(
                id=f"msg-{datetime.utcnow().timestamp()}",
                sender=self.config.name,
                receiver=message.sender,
                message_type="diagnose_response",
                payload={
                    "correlation_id": message.id,
                    "diagnostic": {
                        "issue": diagnostic.issue,
                        "root_cause": diagnostic.root_cause,
                        "confidence": diagnostic.confidence,
                        "recommendations": diagnostic.recommendations,
                        "severity": diagnostic.severity,
                    },
                },
                correlation_id=message.id,
                reply_to=message.id,
            )
            await self.send_message(response)

    async def _handle_status_request(self, message: AgentMessage) -> None:
        """Handle a status request."""
        response = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=message.sender,
            message_type="status_response",
            payload=self.get_status(),
            correlation_id=message.id,
            reply_to=message.id,
        )
        await self.send_message(response)

    async def _handle_metrics_request(self, message: AgentMessage) -> None:
        """Handle a metrics request."""
        pod_metrics = await self.metrics_collector.collect_pod_metrics()
        deploy_metrics = await self.metrics_collector.collect_deployment_metrics()

        response = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=message.sender,
            message_type="metrics_response",
            payload={
                "correlation_id": message.id,
                "pod_metrics": pod_metrics,
                "deployment_metrics": deploy_metrics,
            },
            correlation_id=message.id,
            reply_to=message.id,
        )
        await self.send_message(response)


def main() -> None:
    """Main entry point for SRE Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="SRE Agent")
    parser.add_argument("--name", default="sre-agent", help="Agent name")
    parser.add_argument(
        "--namespace", default="spot-render", help="Kubernetes namespace"
    )
    parser.add_argument(
        "--ollama-url", default="http://ollama:11434", help="Ollama URL"
    )
    parser.add_argument(
        "--ollama-model", default="llama3.2:latest", help="Ollama model"
    )
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    config = AgentConfig(
        name=args.name,
        profile=AgentProfile.SRE,
        namespace=args.namespace,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        log_level=args.log_level,
    )

    agent = SREAgent(config)

    asyncio.run(agent.start())


if __name__ == "__main__":
    main()
