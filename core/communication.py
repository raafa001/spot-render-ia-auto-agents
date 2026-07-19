"""
Inter-Agent Communication Module

Handles message passing, event coordination, and state sharing
between agents.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from kubernetes import client, config
from kubernetes.client import CoreV1Api

from core.agent_base import AgentMessage, MessagePriority

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Central message bus for agent communication.

    Uses Kubernetes ConfigMaps and Events for message passing.
    """

    _instance: Optional["MessageBus"] = None
    _lock = asyncio.Lock()

    def __init__(self, namespace: str = "spot-render-ai-agents"):
        self.namespace = namespace
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._v1: CoreV1Api | None = None
        self._configmap_name = "agent-messages"
        self._event_prefix = "agent-message"

    @classmethod
    async def get_instance(cls, namespace: str = "spot-render-ai-agents") -> "MessageBus":
        """Get singleton instance of MessageBus."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls(namespace)
                    await instance._initialize()
                    cls._instance = instance
        return cls._instance

    async def _initialize(self) -> None:
        """Initialize Kubernetes connections."""
        try:
            config.load_incluster_config()
            self._v1 = CoreV1Api()
            await self._ensure_configmap()
            self.logger.info("MessageBus initialized with Kubernetes backend")
        except Exception as e:
            self.logger.warning(f"Kubernetes not available, using in-memory mode: {e}")
            self._v1 = None

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("message_bus")

    async def _ensure_configmap(self) -> None:
        """Ensure the ConfigMap exists."""
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
                    data={},
                )
                self._v1.create_namespaced_config_map(self.namespace, cm)
                self.logger.info(f"Created ConfigMap: {self._configmap_name}")
            else:
                raise

    async def publish(self, message: AgentMessage) -> None:
        """
        Publish a message to the bus.

        For Kubernetes mode: Creates an event.
        For in-memory mode: Uses asyncio queues.
        """
        if self._v1:
            await self._publish_to_k8s(message)
        else:
            await self._publish_to_memory(message)

    async def _publish_to_k8s(self, message: AgentMessage) -> None:
        """Publish message via Kubernetes Events."""
        if not self._v1:
            return

        try:
            # Create a Kubernetes event for the message
            event = client.V1Event(
                metadata=client.V1ObjectMeta(
                    name=f"{self._event_prefix}-{message.id}",
                    namespace=self.namespace,
                ),
                message=json.dumps(message.to_dict()),
                type="Normal",
                reason=message.message_type,
                involved_object=client.V1ObjectReference(
                    kind="ConfigMap",
                    name=self._configmap_name,
                    namespace=self.namespace,
                    api_version="v1",
                ),
                source=client.V1EventSource(component=message.sender),
                first_timestamp=message.timestamp,
                last_timestamp=message.timestamp,
                count=1,
            )

            self._v1.create_namespaced_event(self.namespace, event)

            # Also update ConfigMap with latest messages for persistence
            await self._update_configmap(message)

        except Exception as e:
            self.logger.error(f"Failed to publish to K8s: {e}")
            await self._publish_to_memory(message)

    async def _update_configmap(self, message: AgentMessage) -> None:
        """Update ConfigMap with message for persistence."""
        if not self._v1:
            return

        try:
            cm = self._v1.read_namespaced_config_map(self._configmap_name, self.namespace)
            messages = json.loads(cm.data.get("messages", "[]"))
            messages.append(message.to_dict())

            # Keep only last 100 messages
            messages = messages[-100:]

            cm.data = {"messages": json.dumps(messages)}
            self._v1.replace_namespaced_config_map(self._configmap_name, self.namespace, cm)
        except Exception as e:
            self.logger.warning(f"Failed to update ConfigMap: {e}")

    async def _publish_to_memory(self, message: AgentMessage) -> None:
        """Publish message via in-memory asyncio queues."""
        # Deliver to specific receiver if specified
        if message.receiver:
            if message.receiver in self._subscribers:
                await self._subscribers[message.receiver].put(message)
        else:
            # Broadcast to all subscribers
            for queue in self._subscribers.values():
                await queue.put(message)

    async def subscribe(self, agent_name: str) -> asyncio.Queue:
        """
        Subscribe an agent to the message bus.

        Returns a queue that will receive messages for this agent.
        """
        queue = asyncio.Queue()
        self._subscribers[agent_name] = queue
        self.logger.info(f"Agent {agent_name} subscribed to message bus")
        return queue

    async def unsubscribe(self, agent_name: str) -> None:
        """Unsubscribe an agent from the message bus."""
        if agent_name in self._subscribers:
            del self._subscribers[agent_name]
            self.logger.info(f"Agent {agent_name} unsubscribed from message bus")

    async def get_messages(self, agent_name: str, timeout: float = 1.0) -> list[AgentMessage]:
        """Get all pending messages for an agent."""
        messages = []
        queue = self._subscribers.get(agent_name)

        if not queue:
            return messages

        try:
            while not queue.empty():
                try:
                    msg = queue.get_nowait()
                    messages.append(msg)
                except asyncio.QueueEmpty:
                    break
        except Exception as e:
            self.logger.error(f"Error getting messages: {e}")

        return messages


class SharedState:
    """
    Shared state manager for agents.

    Provides distributed state sharing via Kubernetes ConfigMaps.
    """

    def __init__(self, namespace: str = "spot-render-ai-agents"):
        self.namespace = namespace
        self._v1: CoreV1Api | None = None
        self._state: dict[str, Any] = {}
        self._configmap_name = "agent-shared-state"
        self._lock_key = "state_lock"

    async def initialize(self) -> None:
        """Initialize Kubernetes connections."""
        try:
            config.load_incluster_config()
            self._v1 = CoreV1Api()
            await self._ensure_configmap()
            await self._load_state()
            self.logger.info("SharedState initialized")
        except Exception as e:
            self.logger.warning(f"Kubernetes not available, using in-memory mode: {e}")
            self._v1 = None

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("shared_state")

    async def _ensure_configmap(self) -> None:
        """Ensure the ConfigMap exists."""
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
                    data={"state": "{}"},
                )
                self._v1.create_namespaced_config_map(self.namespace, cm)
            else:
                raise

    async def _load_state(self) -> None:
        """Load state from ConfigMap."""
        if not self._v1:
            return

        try:
            cm = self._v1.read_namespaced_config_map(self._configmap_name, self.namespace)
            self._state = json.loads(cm.data.get("state", "{}"))
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")

    async def _save_state(self) -> None:
        """Save state to ConfigMap."""
        if not self._v1:
            return

        try:
            cm = self._v1.read_namespaced_config_map(self._configmap_name, self.namespace)
            cm.data = {"state": json.dumps(self._state)}
            self._v1.replace_namespaced_config_map(self._configmap_name, self.namespace, cm)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")

    async def set(self, key: str, value: Any) -> None:
        """Set a state value."""
        self._state[key] = {
            "value": value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        await self._save_state()

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self._state.get(key, {}).get("value", default)

    async def delete(self, key: str) -> None:
        """Delete a state value."""
        if key in self._state:
            del self._state[key]
            await self._save_state()

    async def get_all(self) -> dict[str, Any]:
        """Get all state values."""
        return {k: v.get("value") for k, v in self._state.items()}


class AgentCoordinator:
    """
    Coordinates actions between agents.

    Prevents duplicate work and manages resource allocation.
    """

    def __init__(self, namespace: str = "spot-render-ai-agents"):
        self.namespace = namespace
        self._active_operations: dict[str, dict] = {}
        self._shared_state: SharedState | None = None

    async def initialize(self) -> None:
        """Initialize the coordinator."""
        self._shared_state = SharedState(self.namespace)
        await self._shared_state.initialize()

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("coordinator")

    async def claim_operation(
        self,
        operation_id: str,
        agent: str,
        operation_type: str,
        target: str,
    ) -> bool:
        """
        Try to claim an operation.

        Returns True if claim was successful, False if already claimed.
        """
        existing = await self._shared_state.get(f"operation:{operation_id}") if self._shared_state else None

        if existing:
            if existing.get("agent") != agent:
                self.logger.info(
                    f"Operation {operation_id} already claimed by {existing.get('agent')}"
                )
                return False

        if self._shared_state:
            await self._shared_state.set(
                f"operation:{operation_id}",
                {
                    "agent": agent,
                    "type": operation_type,
                    "target": target,
                    "started_at": datetime.utcnow().isoformat(),
                },
            )

        self.logger.info(f"Agent {agent} claimed operation {operation_id}")
        return True

    async def release_operation(self, operation_id: str, agent: str) -> None:
        """Release a claimed operation."""
        existing = await self._shared_state.get(f"operation:{operation_id}") if self._shared_state else None

        if existing and existing.get("agent") == agent:
            if self._shared_state:
                await self._shared_state.delete(f"operation:{operation_id}")
            self.logger.info(f"Agent {agent} released operation {operation_id}")

    async def get_active_operations(self) -> list[dict]:
        """Get all active operations."""
        if not self._shared_state:
            return []

        all_state = await self._shared_state.get_all()
        operations = []

        for key, value in all_state.items():
            if key.startswith("operation:"):
                operations.append(value)

        return operations
