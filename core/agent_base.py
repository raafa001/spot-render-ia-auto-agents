"""
Agent Base Module

Base classes and configurations for all agents.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import pydantic
from pydantic import Field

logger = logging.getLogger(__name__)


class AgentProfile(str, Enum):
    """Agent specialization profiles."""

    SRE = "sre"  # Reliability focused
    DEVOPS = "devops"  # Infrastructure focused
    SELF_HEALING = "self_healing"  # Remediation focused


class AgentStatus(str, Enum):
    """Agent operational status."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    IDLE = "idle"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class MessagePriority(str, Enum):
    """Message priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AgentRole(str, Enum):
    """Agent roles in the system."""

    MONITOR = "monitor"
    ANALYZER = "analyzer"
    REMEDIATOR = "remediator"
    COORDINATOR = "coordinator"
    REPORTER = "reporter"


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    profile: AgentProfile
    namespace: str = "spot-render"
    log_level: str = "INFO"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:latest"
    heartbeat_interval: int = 30  # seconds
    snapshot_retention: int = 100  # number of snapshots to keep
    decision_threshold: float = 0.7  # confidence threshold for actions
    max_retries: int = 3
    timeout: int = 30  # seconds for operations


@dataclass
class AgentMessage:
    """Message structure for inter-agent communication."""

    id: str
    sender: str
    receiver: str | None  # None = broadcast
    message_type: str
    payload: dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str | None = None
    reply_to: str | None = None

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "reply_to": self.reply_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """Create message from dictionary."""
        return cls(
            id=data["id"],
            sender=data["sender"],
            receiver=data["receiver"],
            message_type=data["message_type"],
            payload=data["payload"],
            priority=MessagePriority(data.get("priority", "normal")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
        )


@dataclass
class LLMResponse:
    """Response from LLM inference."""

    content: str
    confidence: float
    reasoning: str | None = None
    tool_calls: list[dict] | None = None
    error: str | None = None


@dataclass
class DiagnosticResult:
    """Result from diagnostic analysis."""

    issue: str
    root_cause: str | None
    confidence: float
    recommendations: list[str]
    affected_components: list[str]
    severity: str  # critical, high, medium, low


@dataclass
class RemediationAction:
    """A remediation action to be executed."""

    id: str
    description: str
    action_type: str
    target: str
    parameters: dict[str, Any]
    estimated_impact: str
    risk_level: str  # low, medium, high
    requires_approval: bool = False
    auto_execute: bool = True


class AgentBase(ABC):
    """
    Base class for all agents.

    Provides common functionality for:
    - Configuration management
    - Logging
    - Message handling
    - State management
    - Health checks
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.INITIALIZING
        self.logger = self._setup_logging()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._message_handlers: dict[str, callable] = {}

    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the agent."""
        logger = logging.getLogger(f"agent.{self.config.name}")
        logger.setLevel(getattr(logging, self.config.log_level))

        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(handler)

        return logger

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize agent resources and connections."""
        pass

    @abstractmethod
    async def execute_cycle(self) -> None:
        """Execute one monitoring/remediation cycle."""
        pass

    @abstractmethod
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages from other agents."""
        pass

    async def start(self) -> None:
        """Start the agent main loop."""
        self.logger.info(f"Starting agent: {self.config.name}")
        self.status = AgentStatus.RUNNING
        self._running = True

        try:
            await self.initialize()

            while self._running:
                try:
                    await self.execute_cycle()
                    self.status = AgentStatus.IDLE
                    await asyncio.sleep(self.config.heartbeat_interval)
                except Exception as e:
                    self.logger.error(f"Error in agent cycle: {e}", exc_info=True)
                    self.status = AgentStatus.ERROR
                    await asyncio.sleep(5)

        except Exception as e:
            self.logger.error(f"Fatal error in agent: {e}", exc_info=True)
            self.status = AgentStatus.ERROR
        finally:
            await self.shutdown()

    async def stop(self) -> None:
        """Stop the agent gracefully."""
        self.logger.info(f"Stopping agent: {self.config.name}")
        self._running = False
        self.status = AgentStatus.SHUTDOWN

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def shutdown(self) -> None:
        """Cleanup resources on shutdown."""
        self.logger.info(f"Agent {self.config.name} shutting down")

    def register_handler(self, message_type: str, handler: callable) -> None:
        """Register a message handler for a specific message type."""
        self._message_handlers[message_type] = handler

    async def send_message(self, message: AgentMessage) -> None:
        """Send a message to another agent."""
        from core.communication import MessageBus

        bus = MessageBus.get_instance()
        await bus.publish(message)

    async def broadcast(self, message_type: str, payload: dict) -> None:
        """Broadcast a message to all agents."""
        message = AgentMessage(
            id=f"msg-{datetime.utcnow().timestamp()}",
            sender=self.config.name,
            receiver=None,
            message_type=message_type,
            payload=payload,
        )
        await self.send_message(message)

    def get_status(self) -> dict:
        """Get current agent status."""
        return {
            "name": self.config.name,
            "profile": self.config.profile.value,
            "status": self.status.value,
            "timestamp": datetime.utcnow().isoformat(),
        }
