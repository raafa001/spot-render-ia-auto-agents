"""
Self-Healing Agent

Autonomously diagnoses and remediates issues in the cluster.
Uses LLM for decision making and RAG for knowledge.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from core.agent_base import (
    AgentBase,
    AgentConfig,
    AgentMessage,
    AgentProfile,
    DiagnosticResult,
    RemediationAction,
)
from core.communication import AgentCoordinator, MessageBus, SharedState
from core.llm import LLMClient
from core.rag import RAGKnowledgeBase
from core.snapshot import Snapshot, SnapshotStore, SnapshotType

logger = logging.getLogger(__name__)


class RunbookExecutor:
    """Executes remediation runbooks."""

    # Predefined runbooks for common issues
    RUNBOOKS = {
        "CrashLoopBackOff": {
            "description": "Container is crashing repeatedly",
            "steps": [
                "Check container logs for errors",
                "Verify resource limits are not exceeded",
                "Check for OOMKilled status",
                "Restart the pod",
                "If persists, scale down and debug",
            ],
            "conditions": ["pod restart count > 3", "container not stable"],
        },
        "OOMKilled": {
            "description": "Container was killed due to out of memory",
            "steps": [
                "Check current memory limits",
                "Increase memory limit if needed",
                "Restart the pod",
                "Monitor memory usage",
            ],
            "conditions": ["container memory > limit"],
        },
        "HighCPU": {
            "description": "High CPU usage detected",
            "steps": [
                "Identify the process causing high CPU",
                "Check for infinite loops or memory leaks",
                "Consider scaling horizontally",
                "Implement rate limiting if needed",
            ],
            "conditions": ["cpu usage > 80%"],
        },
        "PodNotReady": {
            "description": "Pod is not in ready state",
            "steps": [
                "Check readiness probe configuration",
                "Verify application health endpoint",
                "Check for dependency issues",
                "Restart the pod",
            ],
            "conditions": ["pod ready = 0"],
        },
        "ServiceUnavailable": {
            "description": "Service endpoint is not responding",
            "steps": [
                "Check service selector matches pods",
                "Verify pod endpoints exist",
                "Check network policies",
                "Restart affected pods",
            ],
            "conditions": ["service endpoints = 0"],
        },
    }

    def __init__(self, k8s_manager: Any = None):
        self.k8s_manager = k8s_manager

    async def execute(
        self,
        runbook_id: str,
        target: str,
        parameters: dict | None = None,
    ) -> dict[str, Any]:
        """
        Execute a runbook.

        Args:
            runbook_id: Identifier of the runbook to execute
            target: Target resource (pod, deployment, etc.)
            parameters: Additional parameters

        Returns:
            Execution result
        """
        runbook = self.RUNBOOKS.get(runbook_id)

        if not runbook:
            return {"success": False, "error": f"Unknown runbook: {runbook_id}"}

        logger.info(f"Executing runbook: {runbook_id} on {target}")

        results = []

        for i, step in enumerate(runbook["steps"], 1):
            logger.info(f"Step {i}: {step}")

            # In a real implementation, each step would be executed
            # For now, simulate execution
            step_result = await self._execute_step(step, target, parameters)
            results.append(
                {
                    "step": i,
                    "description": step,
                    "result": step_result,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # If step fails and is critical, stop
            if not step_result.get("success") and i <= 2:
                logger.warning(f"Critical step {i} failed, aborting")
                break

        success = all(r["result"].get("success", False) for r in results)

        return {
            "success": success,
            "runbook_id": runbook_id,
            "target": target,
            "steps": results,
            "completed_at": datetime.utcnow().isoformat(),
        }

    async def _execute_step(
        self,
        step: str,
        target: str,
        parameters: dict | None = None,
    ) -> dict[str, Any]:
        """Execute a single runbook step."""
        # Simulate step execution
        # In production, this would interact with Kubernetes API

        step_lower = step.lower()

        try:
            if "restart" in step_lower and "pod" in step_lower:
                # Would call k8s_manager.restart_deployment
                return {"success": True, "action": "restart_pod", "target": target}

            elif "scale" in step_lower:
                replicas = parameters.get("replicas", 2) if parameters else 2
                return {
                    "success": True,
                    "action": "scale",
                    "replicas": replicas,
                    "target": target,
                }

            elif "check" in step_lower or "verify" in step_lower:
                # Would perform a check
                return {"success": True, "action": "check", "target": target}

            else:
                return {"success": True, "action": "completed", "target": target}

        except Exception as e:
            return {"success": False, "error": str(e)}


class SelfHealingAgent(AgentBase):
    """
    Self-Healing Agent.

    Responsibilities:
    - Monitor for issues from other agents
    - Diagnose root causes using LLM
    - Plan and execute remediation
    - Document all actions
    - Learn from incidents
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.snapshot_store = SnapshotStore(config.namespace)
        self.llm_client = LLMClient(config)
        self.rag_kb = RAGKnowledgeBase(config)
        self.runbook_executor = RunbookExecutor()
        self.coordinator = AgentCoordinator(config.namespace)
        self._message_bus: MessageBus | None = None
        self._shared_state: SharedState | None = None
        self._pending_incidents: list[dict] = []

    async def initialize(self) -> None:
        """Initialize agent resources."""
        self.logger.info(f"Initializing Self-Healing Agent: {self.config.name}")

        await self.snapshot_store.initialize()
        await self.llm_client.initialize()
        await self.rag_kb.initialize()
        await self.coordinator.initialize()

        self._message_bus = await MessageBus.get_instance(self.config.namespace)
        self._shared_state = SharedState(self.config.namespace)
        await self._shared_state.initialize()

        await self._message_bus.subscribe(self.config.name)

        # Initialize RAG with runbooks
        await self._initialize_runbooks()

        self.logger.info("Self-Healing Agent initialized successfully")

    async def _initialize_runbooks(self) -> None:
        """Initialize runbooks in RAG knowledge base."""
        for runbook_id, runbook in self.runbook_executor.RUNBOOKS.items():
            await self.rag_kb.add_runbook(
                runbook_id=runbook_id,
                title=runbook["description"],
                description=runbook["description"],
                steps=runbook["steps"],
                conditions=runbook["conditions"],
                metadata={"tags": ["self-healing", "automated"]},
            )

    async def execute_cycle(self) -> None:
        """Execute one self-healing cycle."""
        self.logger.debug("Self-Healing Agent executing cycle")

        try:
            # Check for pending alerts
            await self._process_alerts()

            # Check for pending incidents
            await self._process_pending_incidents()

            # Clean up old incidents
            await self._cleanup_old_incidents()

        except Exception as e:
            self.logger.error(f"Error in self-healing cycle: {e}", exc_info=True)
            error_snapshot = Snapshot.error_snapshot(
                error_type="SelfHealingCycleError",
                error_message=str(e),
                source=self.config.name,
                severity="error",
            )
            await self.snapshot_store.store(error_snapshot)

    async def handle_message(self, message: AgentMessage) -> None:
        """Handle incoming messages."""
        self.logger.debug(f"Self-Healing received: {message.message_type}")

        handlers = {
            "alert": self._handle_alert,
            "diagnose_response": self._handle_diagnose_response,
            "incident_report": self._handle_incident_report,
            "approval_response": self._handle_approval_response,
            "heal_request": self._handle_heal_request,
        }

        handler = handlers.get(message.message_type)
        if handler:
            await handler(message)

    async def _process_alerts(self) -> None:
        """Process alerts from other agents."""
        if not self._message_bus:
            return

        messages = await self._message_bus.get_messages(self.config.name)

        for message in messages:
            if message.message_type == "alert":
                await self._handle_alert(message)

    async def _handle_alert(self, message: AgentMessage) -> None:
        """Handle an alert from another agent."""
        alert_data = message.payload

        self.logger.info(f"Received alert: {alert_data}")

        # Check if this is a new issue or related to existing
        incident_id = await self._should_create_incident(alert_data)

        if incident_id:
            # Create new incident
            incident = {
                "id": f"inc-{datetime.utcnow().timestamp()}",
                "alert": alert_data,
                "status": "diagnosing",
                "created_at": datetime.utcnow().isoformat(),
                "diagnostic": None,
                "remediation_plan": None,
            }
            self._pending_incidents.append(incident)

            # Request diagnosis from SRE agent
            diagnostic_request = AgentMessage(
                id=f"msg-{datetime.utcnow().timestamp()}",
                sender=self.config.name,
                receiver="sre-agent",
                message_type="diagnose_request",
                payload={
                    "target": alert_data.get("pod", alert_data.get("deployment", "")),
                    "type": alert_data.get("type", "pod"),
                },
            )
            await self.send_message(diagnostic_request)
        else:
            # Attach to existing incident
            self.logger.info("Alert attached to existing incident")

    async def _should_create_incident(self, alert_data: dict) -> bool:
        """Determine if a new incident should be created."""
        # Simple deduplication - check if same issue in last 5 minutes
        recent_threshold = datetime.utcnow().timestamp() - 300

        for incident in self._pending_incidents:
            if incident.get("created_at"):
                incident_time = datetime.fromisoformat(
                    incident["created_at"]
                ).timestamp()

                if incident_time > recent_threshold:
                    # Check if same target
                    if (
                        incident.get("alert", {}).get("pod")
                        == alert_data.get("pod")
                    ):
                        return False

        return True

    async def _handle_diagnose_response(self, message: AgentMessage) -> None:
        """Handle diagnostic response from SRE agent."""
        diagnostic_data = message.payload.get("diagnostic", {})

        # Find the incident
        incident = self._find_incident_by_correlation(message.correlation_id)

        if incident:
            incident["diagnostic"] = diagnostic_data
            incident["status"] = "planning"

            # Generate remediation plan using LLM
            await self._plan_remediation(incident)

        else:
            self.logger.warning("No incident found for diagnostic response")

    async def _find_incident_by_correlation(
        self, correlation_id: str | None
    ) -> dict | None:
        """Find an incident by correlation ID."""
        if not correlation_id:
            return self._pending_incidents[-1] if self._pending_incidents else None

        for incident in self._pending_incidents:
            # Would need to store correlation_id in incident
            pass

        return self._pending_incidents[-1] if self._pending_incidents else None

    async def _plan_remediation(self, incident: dict) -> None:
        """Plan remediation actions for an incident."""
        diagnostic = incident.get("diagnostic", {})

        if not diagnostic:
            self.logger.warning("No diagnostic data for incident")
            incident["status"] = "failed"
            return

        # Get available actions from runbooks
        available_actions = list(self.runbook_executor.RUNBOOKS.keys())

        # Use LLM to plan remediation
        diagnostic_result = DiagnosticResult(
            issue=diagnostic.get("issue", "Unknown"),
            root_cause=diagnostic.get("root_cause"),
            confidence=diagnostic.get("confidence", 0.5),
            recommendations=diagnostic.get("recommendations", []),
            affected_components=[],
            severity=diagnostic.get("severity", "medium"),
        )

        actions = await self.llm_client.plan_remediation(
            diagnostic=diagnostic_result,
            available_actions=available_actions,
            constraints={"max_risk": "medium"},
        )

        incident["remediation_plan"] = [a.__dict__ for a in actions]
        incident["status"] = "awaiting_approval"

        # Request approval if confidence is low or risk is high
        if diagnostic.get("confidence", 0) < 0.8 or any(
            a.risk_level == "high" for a in actions
        ):
            await self._request_approval(incident)
        else:
            # Auto-execute if confidence is high
            await self._execute_remediation(incident)

    async def _request_approval(self, incident: dict) -> None:
        """Request approval for remediation actions."""
        self.logger.info(
            f"Requesting approval for incident {incident['id']}: {incident['diagnostic'].get('issue')}"
        )

        # Broadcast approval request
        await self.broadcast(
            "approval_request",
            {
                "incident_id": incident["id"],
                "issue": incident["diagnostic"].get("issue"),
                "confidence": incident["diagnostic"].get("confidence"),
                "actions": incident["remediation_plan"],
            },
        )

    async def _handle_approval_response(self, message: AgentMessage) -> None:
        """Handle approval response."""
        response = message.payload

        if response.get("approved"):
            incident = self._find_incident_by_correlation(message.correlation_id)
            if incident:
                await self._execute_remediation(incident)
        else:
            incident = self._find_incident_by_correlation(message.correlation_id)
            if incident:
                incident["status"] = "rejected"
                self.logger.info(f"Remediation rejected for incident {incident['id']}")

    async def _execute_remediation(self, incident: dict) -> None:
        """Execute remediation actions for an incident."""
        incident["status"] = "executing"
        remediation_plan = incident.get("remediation_plan", [])

        self.logger.info(
            f"Executing remediation for incident {incident['id']}: {len(remediation_plan)} actions"
        )

        for action_data in remediation_plan:
            action = RemediationAction(**action_data)

            # Try to claim the operation
            claimed = await self.coordinator.claim_operation(
                operation_id=f"{incident['id']}-{action.id}",
                agent=self.config.name,
                operation_type=action.action_type,
                target=action.target,
            )

            if not claimed:
                self.logger.warning(f"Could not claim operation: {action.id}")
                continue

            try:
                # Execute via runbook executor
                result = await self.runbook_executor.execute(
                    runbook_id=action.action_type,
                    target=action.target,
                    parameters=action.parameters,
                )

                # Store action result
                snapshot = Snapshot.log_snapshot(
                    messages=[
                        f"Action: {action.description}",
                        f"Result: {'Success' if result.get('success') else 'Failed'}",
                    ],
                    source=self.config.name,
                    component=action.target,
                    severity="info" if result.get("success") else "error",
                )
                await self.snapshot_store.store(snapshot)

            finally:
                # Release the operation
                await self.coordinator.release_operation(
                    f"{incident['id']}-{action.id}", self.config.name
                )

        incident["status"] = "resolved"
        incident["resolved_at"] = datetime.utcnow().isoformat()

        # Document the incident in RAG
        await self._document_incident(incident)

    async def _document_incident(self, incident: dict) -> None:
        """Document incident in RAG knowledge base."""
        diagnostic = incident.get("diagnostic", {})
        remediation = incident.get("remediation_plan", [])

        await self.rag_kb.add_incident(
            incident_id=incident["id"],
            description=diagnostic.get("issue", "Unknown issue"),
            symptoms=[incident.get("alert", {}).get("issue", "")],
            root_cause=diagnostic.get("root_cause", "Unknown"),
            resolution="\n".join([a.get("description", "") for a in remediation]),
            metadata={
                "status": incident["status"],
                "created_at": incident["created_at"],
                "resolved_at": incident.get("resolved_at"),
                "tags": ["auto-healed", diagnostic.get("severity", "unknown")],
            },
        )

    async def _process_pending_incidents(self) -> None:
        """Process any pending incidents."""
        for incident in self._pending_incidents:
            if incident.get("status") == "diagnosing":
                # Wait for diagnostic response
                pass

    async def _cleanup_old_incidents(self) -> None:
        """Clean up old resolved incidents."""
        threshold = datetime.utcnow().timestamp() - 3600  # 1 hour

        self._pending_incidents = [
            inc
            for inc in self._pending_incidents
            if datetime.fromisoformat(inc["created_at"]).timestamp() > threshold
            or inc.get("status") not in ["resolved", "rejected"]
        ]

    async def _handle_incident_report(self, message: AgentMessage) -> None:
        """Handle an incident report from another agent."""
        report = message.payload

        # Create incident from report
        incident = {
            "id": report.get("incident_id", f"inc-{datetime.utcnow().timestamp()}"),
            "alert": report,
            "diagnostic": report.get("diagnostic"),
            "status": "planning",
            "created_at": datetime.utcnow().isoformat(),
        }

        self._pending_incidents.append(incident)

        if report.get("diagnostic"):
            await self._plan_remediation(incident)

    async def _handle_heal_request(self, message: AgentMessage) -> None:
        """Handle a direct heal request."""
        request = message.payload
        issue = request.get("issue")
        target = request.get("target")

        self.logger.info(f"Heal request: {issue} on {target}")

        # Create incident
        incident = {
            "id": f"inc-{datetime.utcnow().timestamp()}",
            "alert": {"type": "manual", "issue": issue, "target": target},
            "diagnostic": {
                "issue": issue,
                "confidence": 1.0,
                "recommendations": [f"Manual remediation for {issue}"],
            },
            "status": "planning",
            "created_at": datetime.utcnow().isoformat(),
        }

        self._pending_incidents.append(incident)
        await self._plan_remediation(incident)


def main() -> None:
    """Main entry point for Self-Healing Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Self-Healing Agent")
    parser.add_argument("--name", default="self-healing-agent", help="Agent name")
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
        profile=AgentProfile.SELF_HEALING,
        namespace=args.namespace,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        log_level=args.log_level,
    )

    agent = SelfHealingAgent(config)

    asyncio.run(agent.start())


if __name__ == "__main__":
    main()
