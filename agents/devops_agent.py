"""
DevOps Agent

Manages Kubernetes resources, deployments, scaling, and configuration.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from kubernetes import client, config
from kubernetes.client import (
    CoreV1Api,
    AppsV1Api,
    AutoscalingV1Api,
    V1ConfigMap,
    V1Secret,
)
from kubernetes.dynamic import DynamicClient
from kubernetes.client.api import CoreV1Api

from core.agent_base import AgentBase, AgentConfig, AgentMessage, AgentProfile
from core.communication import MessageBus, SharedState
from core.snapshot import Snapshot, SnapshotStore, SnapshotType

logger = logging.getLogger(__name__)


class KubernetesManager:
    """Manages Kubernetes resources."""

    def __init__(self, namespace: str = "spot-render"):
        self.namespace = namespace
        self._v1: CoreV1Api | None = None
        self._apps_v1: AppsV1Api | None = None
        self._autoscaling_v1: AutoscalingV1Api | None = None

    async def initialize(self) -> None:
        """Initialize Kubernetes clients."""
        try:
            config.load_incluster_config()
            self._v1 = CoreV1Api()
            self._apps_v1 = AppsV1Api()
            self._autoscaling_v1 = AutoscalingV1Api()
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes client: {e}")

    async def scale_deployment(
        self,
        name: str,
        replicas: int,
    ) -> dict[str, Any]:
        """Scale a deployment."""
        if not self._apps_v1:
            return {"success": False, "error": "Client not initialized"}

        try:
            # Get current deployment
            deploy = self._apps_v1.read_namespaced_deployment(name, self.namespace)

            # Update replicas
            deploy.spec.replicas = replicas
            self._apps_v1.patch_namespaced_deployment_scale(
                name,
                self.namespace,
                {"spec": {"replicas": replicas}},
            )

            return {
                "success": True,
                "deployment": name,
                "replicas": replicas,
                "previous_replicas": deploy.spec.replicas,
            }

        except Exception as e:
            logger.error(f"Failed to scale deployment {name}: {e}")
            return {"success": False, "error": str(e)}

    async def restart_deployment(self, name: str) -> dict[str, Any]:
        """Restart a deployment by patching the annotation."""
        if not self._apps_v1:
            return {"success": False, "error": "Client not initialized"}

        try:
            # Add/Update restart annotation
            annotation_patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat()
                            }
                        }
                    }
                }
            }

            self._apps_v1.patch_namespaced_deployment(
                name, self.namespace, annotation_patch
            )

            return {"success": True, "deployment": name}

        except Exception as e:
            logger.error(f"Failed to restart deployment {name}: {e}")
            return {"success": False, "error": str(e)}

    async def rollout_status(self, name: str) -> dict[str, Any]:
        """Get rollout status of a deployment."""
        if not self._apps_v1:
            return {"available": False}

        try:
            deploy = self._apps_v1.read_namespaced_deployment_status(name, self.namespace)

            conditions = deploy.status.conditions or []
            ready = deploy.status.ready_replicas or 0
            available = deploy.status.available_replicas or 0
            desired = deploy.spec.replicas or 0

            # Check for available condition
            available_condition = next(
                (c for c in conditions if c.type == "Available"), None
            )

            return {
                "available": available_condition is not None,
                "ready_replicas": ready,
                "available_replicas": available,
                "desired_replicas": desired,
                "up_to_date_replicas": deploy.status.updated_replicas or 0,
                "conditions": [
                    {"type": c.type, "status": c.status, "message": c.message}
                    for c in conditions
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get rollout status for {name}: {e}")
            return {"available": False, "error": str(e)}

    async def get_resource_usage(
        self, resource_type: str = "deployment", name: str = ""
    ) -> dict[str, Any]:
        """Get resource usage for a deployment or pod."""
        if not self._v1 or not self._apps_v1:
            return {}

        try:
            if resource_type == "deployment" and name:
                # Get pod metrics via HPA
                hpas = self._autoscaling_v1.list_namespaced_hpa(self.namespace)
                hpa = next(
                    (h for h in hpas.items if h.spec.scale_target_ref.name == name),
                    None,
                )

                deploy = self._apps_v1.read_namespaced_deployment(name, self.namespace)
                current_replicas = deploy.status.ready_replicas or 0

                return {
                    "type": "deployment",
                    "name": name,
                    "current_replicas": current_replicas,
                    "desired_replicas": deploy.spec.replicas,
                    "hpa": {
                        "min_replicas": hpa.spec.min_replicas,
                        "max_replicas": hpa.spec.max_replicas,
                        "current_replicas": hpa.status.current_replicas,
                    }
                    if hpa
                    else None,
                }

            return {}

        except Exception as e:
            logger.error(f"Failed to get resource usage: {e}")
            return {}

    async def create_configmap(
        self,
        name: str,
        data: dict[str, str],
    ) -> dict[str, Any]:
        """Create a ConfigMap."""
        if not self._v1:
            return {"success": False, "error": "Client not initialized"}

        try:
            cm = V1ConfigMap(
                metadata=client.V1ObjectMeta(name=name, namespace=self.namespace),
                data=data,
            )

            self._v1.create_namespaced_config_map(self.namespace, cm)

            return {"success": True, "name": name}

        except Exception as e:
            logger.error(f"Failed to create ConfigMap {name}: {e}")
            return {"success": False, "error": str(e)}

    async def update_configmap(
        self, name: str, data: dict[str, str]
    ) -> dict[str, Any]:
        """Update a ConfigMap."""
        if not self._v1:
            return {"success": False, "error": "Client not initialized"}

        try:
            cm = self._v1.read_namespaced_config_map(name, self.namespace)
            cm.data = data
            self._v1.replace_namespaced_config_map(name, self.namespace, cm)

            return {"success": True, "name": name}

        except Exception as e:
            logger.error(f"Failed to update ConfigMap {name}: {e}")
            return {"success": False, "error": str(e)}


class DevOpsAgent(AgentBase):
    """
    DevOps Agent.

    Handles infrastructure operations:
    - Deployment scaling
    - Configuration management
    - Resource management
    - Rollout operations
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.k8s_manager = KubernetesManager(config.namespace)
        self.snapshot_store = SnapshotStore(config.namespace)
        self._message_bus: MessageBus | None = None
        self._shared_state: SharedState | None = None

    async def initialize(self) -> None:
        """Initialize agent resources."""
        self.logger.info(f"Initializing DevOps Agent: {self.config.name}")

        await self.k8s_manager.initialize()
        await self.snapshot_store.initialize()

        self._message_bus = await MessageBus.get_instance(self.config.namespace)
        self._shared_state = SharedState(self.config.namespace)
        await self._shared_state.initialize()

        await self._message_bus.subscribe(self.config.name)

        self.logger.info("DevOps Agent initialized successfully")

    async def execute_cycle(self) -> None:
        """Execute one DevOps cycle."""
        self.logger.debug("DevOps Agent executing cycle")

        try:
            # Check for pending operations in shared state
            pending_ops = await self._shared_state.get("pending_operations")

            if pending_ops:
                for op in pending_ops:
                    await self._execute_operation(op)

            # Monitor deployment health
            await self._monitor_deployments()

        except Exception as e:
            self.logger.error(f"Error in DevOps cycle: {e}", exc_info=True)

    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages."""
        self.logger.debug(f"DevOps received: {message.message_type}")

        handlers = {
            "scale_request": self._handle_scale_request,
            "restart_request": self._handle_restart_request,
            "config_update": self._handle_config_update,
            "status_request": self._handle_status_request,
            "resource_check": self._handle_resource_check,
        }

        handler = handlers.get(message.message_type)
        if handler:
            await handler(message)

    async def _execute_operation(self, operation: dict) -> None:
        """Execute a pending operation."""
        op_type = operation.get("type")
        target = operation.get("target")

        self.logger.info(f"Executing operation: {op_type} on {target}")

        try:
            if op_type == "scale":
                result = await self.k8s_manager.scale_deployment(
                    target, operation.get("replicas", 1)
                )
            elif op_type == "restart":
                result = await self.k8s_manager.restart_deployment(target)
            else:
                result = {"success": False, "error": f"Unknown operation: {op_type}"}

            # Store result snapshot
            if result.get("success"):
                snapshot = Snapshot.log_snapshot(
                    messages=[f"Operation {op_type} succeeded on {target}"],
                    log_count=1,
                    source=self.config.name,
                    component=target,
                    severity="info",
                )
            else:
                snapshot = Snapshot.error_snapshot(
                    error_type="OperationFailed",
                    error_message=f"{op_type} failed on {target}: {result.get('error')}",
                    source=self.config.name,
                    component=target,
                    severity="error",
                )

            await self.snapshot_store.store(snapshot)

            # Notify completion
            await self.broadcast(
                "operation_completed",
                {
                    "operation": op_type,
                    "target": target,
                    "result": result,
                },
            )

        except Exception as e:
            self.logger.error(f"Operation failed: {e}")

    async def _monitor_deployments(self) -> None:
        """Monitor deployment health."""
        deployments = ["spot-render-web", "spot-render-backend", "spot-render-worker"]

        for deploy_name in deployments:
            status = await self.k8s_manager.rollout_status(deploy_name)

            if not status.get("available"):
                # Store warning snapshot
                snapshot = Snapshot.error_snapshot(
                    error_type="DeploymentUnhealthy",
                    error_message=f"{deploy_name} is not available: {status.get('error', 'Unknown')}",
                    source=self.config.name,
                    component="deployment",
                    severity="warning",
                )
                await self.snapshot_store.store(snapshot)

    async def _handle_scale_request(self, message: AgentMessage) -> None:
        """Handle a scale request."""
        target = message.payload.get("target")
        replicas = message.payload.get("replicas", 1)

        self.logger.info(f"Scale request: {target} to {replicas} replicas")

        result = await self.k8s_manager.scale_deployment(target, replicas)

        response = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=message.sender,
            message_type="scale_response",
            payload={
                "correlation_id": message.id,
                "target": target,
                "replicas": replicas,
                "result": result,
            },
            correlation_id=message.id,
            reply_to=message.id,
        )
        await self.send_message(response)

    async def _handle_restart_request(self, message: AgentMessage) -> None:
        """Handle a restart request."""
        target = message.payload.get("target")

        self.logger.info(f"Restart request: {target}")

        result = await self.k8s_manager.restart_deployment(target)

        response = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=message.sender,
            message_type="restart_response",
            payload={
                "correlation_id": message.id,
                "target": target,
                "result": result,
            },
            correlation_id=message.id,
            reply_to=message.id,
        )
        await self.send_message(response)

    async def _handle_config_update(self, message: AgentMessage) -> None:
        """Handle a configuration update request."""
        configmap = message.payload.get("configmap")
        data = message.payload.get("data", {})

        self.logger.info(f"Config update for ConfigMap: {configmap}")

        # Check if ConfigMap exists
        result = await self.k8s_manager.update_configmap(configmap, data)

        response = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=message.sender,
            message_type="config_update_response",
            payload={
                "correlation_id": message.id,
                "configmap": configmap,
                "result": result,
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

    async def _handle_resource_check(self, message: AgentMessage) -> None:
        """Handle a resource check request."""
        resource_type = message.payload.get("type", "deployment")
        name = message.payload.get("name", "")

        usage = await self.k8s_manager.get_resource_usage(resource_type, name)

        response = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=message.sender,
            message_type="resource_check_response",
            payload={
                "correlation_id": message.id,
                "usage": usage,
            },
            correlation_id=message.id,
            reply_to=message.id,
        )
        await self.send_message(response)


def main() -> None:
    """Main entry point for DevOps Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="DevOps Agent")
    parser.add_argument("--name", default="devops-agent", help="Agent name")
    parser.add_argument(
        "--namespace", default="spot-render", help="Kubernetes namespace"
    )
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    config = AgentConfig(
        name=args.name,
        profile=AgentProfile.DEVOPS,
        namespace=args.namespace,
        log_level=args.log_level,
    )

    agent = DevOpsAgent(config)

    asyncio.run(agent.start())


if __name__ == "__main__":
    main()
