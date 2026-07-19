"""
RAG Knowledge Base Module

Retrieval Augmented Generation for agent knowledge.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from core.agent_base import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeSnapshot:
    """A snapshot of knowledge for RAG."""

    id: str
    content: str
    source: str
    source_type: str  # documentation, incident, runbook, log
    timestamp: datetime = field(default_factory=datetime.utcnow)
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_text(
        cls,
        content: str,
        source: str,
        source_type: str = "documentation",
        metadata: dict | None = None,
    ) -> "KnowledgeSnapshot":
        """Create a snapshot from text content."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return cls(
            id=f"ks-{content_hash}",
            content=content,
            source=source,
            source_type=source_type,
            metadata=metadata or {},
        )


@dataclass
class KnowledgeEntry:
    """A searchable knowledge entry."""

    id: str
    title: str
    content: str
    category: str
    tags: list[str]
    embedding: list[float]
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]


class RAGKnowledgeBase:
    """
    Retrieval Augmented Generation knowledge base.

    Provides:
    - Document embedding and storage
    - Similarity search
    - Context retrieval for LLM prompts
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._entries: dict[str, KnowledgeEntry] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the RAG system."""
        self._initialized = True
        self.logger.info("RAG Knowledge Base initialized")

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger("rag_kb")

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for content."""
        hash_val = hashlib.md5(content.encode()).hexdigest()
        return f"kb-{hash_val[:12]}"

    async def add_document(
        self,
        title: str,
        content: str,
        category: str = "general",
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Add a document to the knowledge base.

        Args:
            title: Document title
            content: Document content
            category: Category (documentation, runbook, incident, etc.)
            tags: Searchable tags
            metadata: Additional metadata

        Returns:
            Document ID
        """
        if not self._initialized:
            await self.initialize()

        doc_id = self._generate_id(content)

        # Generate embedding (simplified - in production use proper embeddings)
        embedding = await self._generate_embedding(content)

        entry = KnowledgeEntry(
            id=doc_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            embedding=embedding,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=metadata or {},
        )

        self._entries[doc_id] = entry
        self._embeddings[doc_id] = embedding

        self.logger.info(f"Added document: {title} ({doc_id})")
        return doc_id

    async def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text.

        In production, use sentence-transformers or OpenAI embeddings.
        For now, use a simple hash-based vector.
        """
        # Simple embedding based on word hashes
        words = text.lower().split()
        vector = np.zeros(384)  # Common embedding dimension

        for i, word in enumerate(words[:384]):
            word_hash = hash(word) % 384
            vector[word_hash] += 1

        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.tolist()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> list[KnowledgeEntry]:
        """
        Search for relevant knowledge entries.

        Args:
            query: Search query
            top_k: Number of results to return
            category: Optional category filter

        Returns:
            List of most relevant entries
        """
        if not self._initialized:
            await self.initialize()

        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Calculate similarities
        results = []
        for doc_id, entry in self._entries.items():
            if category and entry.category != category:
                continue

            similarity = self._cosine_similarity(query_embedding, entry.embedding)
            results.append((similarity, entry))

        # Sort by similarity
        results.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in results[:top_k]]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)

        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot / (norm_a * norm_b))

    async def get_context(
        self,
        query: str,
        max_tokens: int = 2048,
    ) -> str:
        """
        Get context for LLM prompt from knowledge base.

        Args:
            query: Query to get context for
            max_tokens: Maximum tokens to return

        Returns:
            Context string for LLM prompt
        """
        entries = await self.search(query, top_k=5)

        if not entries:
            return ""

        context_parts = ["## Relevant Knowledge\n"]

        for entry in entries:
            context_parts.append(f"### {entry.title}\n")
            context_parts.append(f"Source: {entry.category}\n")
            context_parts.append(f"{entry.content}\n")
            context_parts.append("---\n")

        context = "".join(context_parts)

        # Truncate if too long
        if len(context) > max_tokens * 4:  # Rough estimate
            context = context[: max_tokens * 4]

        return context

    async def add_incident(
        self,
        incident_id: str,
        description: str,
        symptoms: list[str],
        root_cause: str,
        resolution: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Add an incident to the knowledge base for future reference.

        Args:
            incident_id: Incident identifier
            description: What happened
            symptoms: Observed symptoms
            root_cause: Root cause of the incident
            resolution: How it was resolved
            metadata: Additional metadata
        """
        content = f"""# Incident: {incident_id}

## Description
{description}

## Symptoms
{chr(10).join(f"- {s}" for s in symptoms)}

## Root Cause
{root_cause}

## Resolution
{resolution}

## Timeline
{metadata.get('timeline', 'Not specified') if metadata else 'Not specified'}
"""

        await self.add_document(
            title=f"Incident: {incident_id}",
            content=content,
            category="incident",
            tags=["incident", incident_id] + metadata.get("tags", []) if metadata else ["incident", incident_id],
            metadata={
                "incident_id": incident_id,
                "root_cause": root_cause,
                **(metadata or {}),
            },
        )

    async def add_runbook(
        self,
        runbook_id: str,
        title: str,
        description: str,
        steps: list[str],
        conditions: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Add a runbook to the knowledge base.

        Args:
            runbook_id: Runbook identifier
            title: Runbook title
            description: What the runbook does
            steps: Remediation steps
            conditions: When to use this runbook
            metadata: Additional metadata
        """
        content = f"""# Runbook: {title}

## Description
{description}

## When to Use
{chr(10).join(f"- {c}" for c in (conditions or ["Always when applicable"]))}

## Steps
{chr(10).join(f"{i + 1}. {s}" for i, s in enumerate(steps))}

## Warnings
{metadata.get('warnings', 'None') if metadata else 'None'}
"""

        await self.add_document(
            title=f"Runbook: {title}",
            content=content,
            category="runbook",
            tags=["runbook", runbook_id] + metadata.get("tags", []) if metadata else ["runbook", runbook_id],
            metadata={
                "runbook_id": runbook_id,
                "steps": steps,
                **(metadata or {}),
            },
        )

    async def get_runbook(self, issue: str) -> KnowledgeEntry | None:
        """Get the most relevant runbook for an issue."""
        results = await self.search(f"runbook {issue}", top_k=1, category="runbook")
        return results[0] if results else None

    async def get_incidents(self, query: str, limit: int = 5) -> list[KnowledgeEntry]:
        """Search past incidents."""
        return await self.search(query, top_k=limit, category="incident")

    def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        categories = {}
        for entry in self._entries.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1

        return {
            "total_documents": len(self._entries),
            "by_category": categories,
            "initialized": self._initialized,
        }
