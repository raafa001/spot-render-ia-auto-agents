"""
Spot Render IA Auto Agent - Core Package

Core framework for autonomous AI agents for Kubernetes monitoring,
observability, and self-healing.
"""

from core.agent_base import AgentBase, AgentConfig, AgentProfile, AgentMessage
from core.communication import AgentCommunication, MessageBus
from core.llm import LLMClient, LLMResponse
from core.rag import RAGKnowledgeBase, KnowledgeSnapshot
from core.snapshot import Snapshot, SnapshotType, SnapshotStore

__version__ = "0.1.0"

__all__ = [
    "AgentBase",
    "AgentConfig",
    "AgentProfile",
    "AgentMessage",
    "AgentCommunication",
    "MessageBus",
    "LLMClient",
    "LLMResponse",
    "RAGKnowledgeBase",
    "KnowledgeSnapshot",
    "Snapshot",
    "SnapshotType",
    "SnapshotStore",
]
