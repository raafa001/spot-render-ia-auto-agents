"""
Spot Render IA Auto Agents - Playbook Generator Capability
========================================================

This module provides the capability to generate incident response playbooks
based on the nature and severity of incidents.

PT-BR: Módulo para gerar playbooks de resposta a incidentes baseados na natureza e severidade.
EN-US: Module to generate incident response playbooks based on nature and severity.

Features:
- Generate playbooks for different incident types
- Include communication templates
- Include escalation procedures
- Include post-incident actions
- Support different severity levels
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    """Incident severity levels following industry standards."""
    SEV1_CRITICAL = ("sev1", "Critical", "Complete service outage")
    SEV2_HIGH = ("sev2", "High", "Major feature unavailable or degraded")
    SEV3_MEDIUM = ("sev3", "Medium", "Minor feature degraded")
    SEV4_LOW = ("sev4", "Low", "Minimal impact, no user disruption")


class IncidentStatus(Enum):
    """Incident lifecycle status."""
    DETECTED = "detected"
    triaged = "triaged"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


@dataclass
class PlaybookStep:
    """A step in the incident response playbook."""
    phase: str  # Detection, Triage, Investigation, Resolution, Post-incident
    order: int
    action: str
    responsible: str  # Role or agent
    command: str = ""
    notification: str = ""
    sla_minutes: int = 0
    critical: bool = False


@dataclass
class CommunicationTemplate:
    """Template for incident communication."""
    audience: str  # Users, Team, Leadership, External
    timing: str  # Initial, Update, Resolution
    subject: str = ""
    body: str = ""


@dataclass
class Playbook:
    """
    Complete incident response playbook.

    PT-BR: Playbook completo de resposta a incidentes.
    EN-US: Complete incident response playbook.
    """
    # Identity
    playbook_id: str
    title: str
    incident_type: str
    severity: str

    # Content
    description: str = ""
    impact: str = ""
    scope: str = ""
    phases: List[str] = field(default_factory=list)
    steps: List[PlaybookStep] = field(default_factory=list)
    communication_templates: List[CommunicationTemplate] = field(default_factory=list)
    escalation_matrix: Dict[str, str] = field(default_factory=dict)
    sla_targets: Dict[str, int] = field(default_factory=dict)

    # Post-incident
    postmortem_required: bool = True
    postmortem_template: str = ""

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Generate markdown documentation for the playbook."""
        # Group steps by phase
        phases_content = {}
        for step in self.steps:
            if step.phase not in phases_content:
                phases_content[step.phase] = []
            phases_content[step.phase].append(step)

        phases_md = ""
        for phase in self.phases:
            steps = phases_content.get(phase, [])
            if steps:
                phases_md += f"\n### {phase}\n\n"
                for step in steps:
                    critical = " 🔴" if step.critical else ""
                    phases_md += f"""#### {step.order}. {step.action}{critical}

**Responsible:** {step.responsible}

"""
                    if step.command:
                        phases_md += f"**Command:**\n```bash\n{step.command}\n```\n\n"
                    if step.notification:
                        phases_md += f"**Notification:** {step.notification}\n\n"
                    if step.sla_minutes:
                        phases_md += f"**SLA:** {step.sla_minutes} minutes\n\n"

        comm_md = ""
        for comm in self.communication_templates:
            comm_md += f"""### {comm.audience} - {comm.timing}

**Subject:** {comm.subject}

**Body:**
{comm.body}

---

"""

        escalation_md = ""
        for role, contact in self.escalation_matrix.items():
            escalation_md += f"- **{role}:** {contact}\n"

        sla_md = ""
        for metric, target in self.sla_targets.items():
            sla_md += f"- **{metric}:** {target} minutes\n"

        tags_md = ", ".join(f"`{t}`" for t in self.tags)

        return f"""# Playbook: {self.title}

## Metadata

| Field | Value |
|-------|-------|
| **ID** | `{self.playbook_id}` |
| **Incident Type** | {self.incident_type} |
| **Severity** | {self.severity} |
| **Version** | {self.version} |
| **Created** | {self.created_at.isoformat()} |
| **Tags** | {tags_md} |

## Description

{self.description}

## Impact

{self.impact}

## Scope

{self.scope}

## Phases

{" → ".join(self.phases)}

## Response Procedure

{phases_md}

## Communication Templates

{comm_md if comm_md else "_See standard communication templates_"}

## Escalation Matrix

{escalation_md if escalation_md else "_No escalation defined_"}

## SLA Targets

{sla_md if sla_md else "_No specific SLA targets_"}

## Post-Incident

{"A postmortem is REQUIRED for this incident type." if self.postmortem_required else "Postmortem may be optional for this incident type."}

---
_Generated by Spot Render AI Agents on {datetime.now().isoformat()}_
"""


class PlaybookGenerator:
    """
    Generates incident response playbooks.

    PT-BR: Gera playbooks de resposta a incidentes.
    EN-US: Generates incident response playbooks.
    """

    # Templates for different incident types
    INCIDENT_TEMPLATES = {
        "service_outage": {
            "title": "Service Outage Response",
            "description": "Playbook for responding to complete service outages affecting all users.",
            "impact": "Complete inability for users to access the service. All operations are affected.",
            "scope": "All users, all operations",
            "phases": ["Detection", "Triage", "Escalation", "Investigation", "Mitigation", "Resolution", "Post-Incident"],
            "postmortem_required": True,
            "severity_mapping": {
                "SEV1_CRITICAL": "SEV1",
                "SEV2_HIGH": "SEV1",
                "SEV3_MEDIUM": "SEV2"
            }
        },
        "partial_outage": {
            "title": "Partial Service Degradation",
            "description": "Playbook for responding to partial service degradation affecting some users or features.",
            "impact": "Some users or features are affected. Core functionality remains available.",
            "scope": "Subset of users or features",
            "phases": ["Detection", "Triage", "Investigation", "Mitigation", "Resolution", "Post-Incident"],
            "postmortem_required": True,
            "severity_mapping": {
                "SEV1_CRITICAL": "SEV2",
                "SEV2_HIGH": "SEV2",
                "SEV3_MEDIUM": "SEV3"
            }
        },
        "security_incident": {
            "title": "Security Incident Response",
            "description": "Playbook for responding to security incidents including unauthorized access or data breaches.",
            "impact": "Potential unauthorized access to systems or data. Could include data exposure or privilege escalation.",
            "scope": "Affected systems and data",
            "phases": ["Detection", "Containment", "Investigation", "Eradication", "Recovery", "Post-Incident"],
            "postmortem_required": True,
            "severity_mapping": {
                "SEV1_CRITICAL": "SEV1",
                "SEV2_HIGH": "SEV1",
                "SEV3_MEDIUM": "SEV2"
            }
        },
        "performance_degradation": {
            "title": "Performance Degradation Response",
            "description": "Playbook for responding to performance issues affecting response times.",
            "impact": "Increased latency or reduced throughput. Users may experience timeouts or slow responses.",
            "scope": "Performance-sensitive operations",
            "phases": ["Detection", "Triage", "Investigation", "Mitigation", "Resolution", "Post-Incident"],
            "postmortem_required": False,
            "severity_mapping": {
                "SEV1_CRITICAL": "SEV2",
                "SEV2_HIGH": "SEV3",
                "SEV3_MEDIUM": "SEV4"
            }
        },
        "deployment_failure": {
            "title": "Deployment Failure Response",
            "description": "Playbook for responding to failed deployments causing service disruption.",
            "impact": "New deployment causes issues. May require rollback.",
            "scope": "Deployed version and users of that version",
            "phases": ["Detection", "Assessment", "Rollback Decision", "Rollback", "Investigation", "Resolution", "Post-Incident"],
            "postmortem_required": True,
            "severity_mapping": {
                "SEV1_CRITICAL": "SEV2",
                "SEV2_HIGH": "SEV2",
                "SEV3_MEDIUM": "SEV3"
            }
        }
    }

    def __init__(self, storage_path: str = "/var/log/agents/playbooks"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.generated_playbooks: Dict[str, Playbook] = {}

    def generate_playbook(
        self,
        incident_type: str,
        severity: str,
        context: Dict[str, Any]
    ) -> Playbook:
        """
        Generate a playbook based on incident type and severity.

        PT-BR: Gera um playbook baseado no tipo de incidente e severidade.
        EN-US: Generates a playbook based on incident type and severity.
        """
        template = self.INCIDENT_TEMPLATES.get(incident_type, {
            "title": f"Playbook: {incident_type}",
            "description": "Auto-generated playbook",
            "impact": "See incident details",
            "scope": "See incident details",
            "phases": ["Detection", "Triage", "Investigation", "Resolution", "Post-Incident"],
            "postmortem_required": True
        })

        playbook_id = f"pb-{incident_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        playbook = Playbook(
            playbook_id=playbook_id,
            title=template["title"],
            incident_type=incident_type,
            severity=severity,
            description=template["description"],
            impact=template["impact"],
            scope=template["scope"],
            phases=template["phases"],
            postmortem_required=template["postmortem_required"],
            tags=[incident_type, "auto-generated", severity.lower()]
        )

        # Generate steps based on incident type
        playbook.steps = self._generate_steps(incident_type, context)

        # Generate communication templates
        playbook.communication_templates = self._generate_communication_templates(incident_type, context)

        # Generate escalation matrix
        playbook.escalation_matrix = self._generate_escalation_matrix()

        # Generate SLA targets
        playbook.sla_targets = self._generate_sla_targets(severity)

        # Store and save
        self.generated_playbooks[playbook_id] = playbook
        self._save_playbook(playbook)

        logger.info(f"Generated playbook: {playbook_id} for incident: {incident_type}")

        return playbook

    def _generate_steps(self, incident_type: str, context: Dict[str, Any]) -> List[PlaybookStep]:
        """Generate response steps for the incident type."""
        steps = []
        order = 1

        # Common detection steps
        steps.append(PlaybookStep(
            phase="Detection",
            order=order,
            action="Verify the incident",
            responsible="On-call Engineer",
            command=f"kubectl get pods -n {context.get('namespace', 'spot-render')} | grep -v Running",
            notification="Notify team in #incident-response",
            sla_minutes=5,
            critical=True
        ))
        order += 1

        steps.append(PlaybookStep(
            phase="Detection",
            order=order,
            action="Assess severity",
            responsible="On-call Engineer",
            notification="Based on impact, determine severity (SEV1-4)",
            sla_minutes=10
        ))
        order += 1

        # Type-specific steps
        if incident_type == "service_outage":
            steps.extend([
                PlaybookStep(
                    phase="Triage",
                    order=order,
                    action="Identify affected components",
                    responsible="SRE Agent",
                    command="kubectl get events --sort-by='.lastTimestamp' | tail -20",
                    sla_minutes=15
                ),
                PlaybookStep(
                    phase="Investigation",
                    order=order + 1,
                    action="Check recent deployments",
                    responsible="DevOps Agent",
                    command="kubectl rollout history deployment",
                    sla_minutes=20
                ),
                PlaybookStep(
                    phase="Mitigation",
                    order=order + 2,
                    action="Consider rollback",
                    responsible="DevOps Agent",
                    command="kubectl rollout undo deployment",
                    verification_command="kubectl get pods",
                    sla_minutes=30,
                    critical=True
                )
            ])

        elif incident_type == "security_incident":
            steps.extend([
                PlaybookStep(
                    phase="Containment",
                    order=order,
                    action="Isolate affected systems",
                    responsible="Security Team",
                    command="kubectl label nodes <node> spot.ai/isolated=true",
                    sla_minutes=10,
                    critical=True
                ),
                PlaybookStep(
                    phase="Investigation",
                    order=order + 1,
                    action="Gather evidence",
                    responsible="Security Team",
                    command="kubectl get events --all-namespaces | grep -i security",
                    sla_minutes=30
                ),
                PlaybookStep(
                    phase="Eradication",
                    order=order + 2,
                    action="Remove threat",
                    responsible="Security Team",
                    command="kubectl delete pod <suspicious-pod>",
                    sla_minutes=60
                )
            ])

        elif incident_type == "performance_degradation":
            steps.extend([
                PlaybookStep(
                    phase="Investigation",
                    order=order,
                    action="Identify bottlenecks",
                    responsible="SRE Agent",
                    command="kubectl top pods",
                    sla_minutes=15
                ),
                PlaybookStep(
                    phase="Mitigation",
                    order=order + 1,
                    action="Scale horizontally if needed",
                    responsible="DevOps Agent",
                    command="kubectl scale deployment --replicas=3",
                    verification_command="kubectl get pods",
                    sla_minutes=20
                )
            ])

        # Common post-incident steps
        steps.extend([
            PlaybookStep(
                phase="Resolution",
                order=99,
                action="Verify service is healthy",
                responsible="On-call Engineer",
                command="kubectl get pods && curl -s http://api/health",
                verification_command="kubectl get events | grep -v Normal",
                sla_minutes=5,
                critical=True
            ),
            PlaybookStep(
                phase="Post-Incident",
                order=100,
                action="Schedule postmortem",
                responsible="Team Lead",
                notification="Create postmortem document within 48 hours",
                sla_minutes=1440  # 24 hours
            )
        ])

        return steps

    def _generate_communication_templates(self, incident_type: str, context: Dict[str, Any]) -> List[CommunicationTemplate]:
        """Generate communication templates for the incident."""
        templates = [
            CommunicationTemplate(
                audience="Users",
                timing="Initial",
                subject="[SERVICE ISSUE] Service is currently experiencing issues",
                body=f"""We are aware of an issue affecting the Spot Render service.

Our team is actively investigating and working to resolve the issue.

We will provide updates every 30 minutes.

Affected: {context.get('affected_service', 'Spot Render')}
Started: {datetime.now().isoformat()}

We apologize for the inconvenience."""
            ),
            CommunicationTemplate(
                audience="Team",
                timing="Initial",
                subject="[INCIDENT] {SEV} - {incident_type}",
                body=f"""Incident declared.

Type: {incident_type}
Severity: {{severity}}
Affected: {context.get('affected_service', 'Spot Render')}
Detected: {datetime.now().isoformat()}

Immediate actions:
1. Acknowledge this message
2. Join incident bridge (link)
3. Start response procedure

IC: @oncall-engineer"""
            ),
            CommunicationTemplate(
                audience="Users",
                timing="Resolution",
                subject="[RESOLVED] Service issue has been resolved",
                body=f"""The service issue affecting Spot Render has been resolved.

Duration: {{duration}}
Affected: {context.get('affected_service', 'Spot Render')}

We apologize for the inconvenience. A postmortem will be published within 48 hours."""
            )
        ]
        return templates

    def _generate_escalation_matrix(self) -> Dict[str, str]:
        """Generate standard escalation matrix."""
        return {
            "L1 (On-call Engineer)": "PagerDuty -> +1-555-0100",
            "L2 (Team Lead)": "@team-lead -> Slack DM",
            "L3 (Engineering Manager)": "@eng-manager -> Slack DM",
            "L4 (VP Engineering)": "@vp-eng -> Slack DM",
            "Security Team": "#security-incidents"
        }

    def _generate_sla_targets(self, severity: str) -> Dict[str, int]:
        """Generate SLA targets based on severity."""
        targets = {
            "SEV1": {
                "acknowledge": 5,      # minutes
                "comm_status": 15,     # minutes
                "resolve": 60           # minutes
            },
            "SEV2": {
                "acknowledge": 15,
                "comm_status": 30,
                "resolve": 240
            },
            "SEV3": {
                "acknowledge": 60,
                "comm_status": 120,
                "resolve": 1440  # 24 hours
            },
            "SEV4": {
                "acknowledge": 480,
                "comm_status": 1440,
                "resolve": 10080  # 7 days
            }
        }
        return targets.get(severity, targets["SEV3"])

    def _save_playbook(self, playbook: Playbook):
        """Save playbook to storage."""
        playbook_file = self.storage_path / f"{playbook.playbook_id}.md"
        with open(playbook_file, 'w') as f:
            f.write(playbook.to_markdown())

        # Also save JSON metadata
        metadata_file = self.storage_path / f"{playbook.playbook_id}.json"
        with open(metadata_file, 'w') as f:
            json.dump({
                "playbook_id": playbook.playbook_id,
                "title": playbook.title,
                "incident_type": playbook.incident_type,
                "severity": playbook.severity,
                "created_at": playbook.created_at.isoformat(),
                "tags": playbook.tags
            }, f, indent=2)

    def get_playbook(self, playbook_id: str) -> Optional[Playbook]:
        """Get a playbook by ID."""
        return self.generated_playbooks.get(playbook_id)

    def list_playbooks(self) -> List[Playbook]:
        """List all generated playbooks."""
        return list(self.generated_playbooks.values())


# Need to import Enum
from enum import Enum


# Global instance
_playbook_generator: Optional[PlaybookGenerator] = None


def get_playbook_generator() -> PlaybookGenerator:
    """Get or create the global PlaybookGenerator instance."""
    global _playbook_generator
    if _playbook_generator is None:
        _playbook_generator = PlaybookGenerator()
    return _playbook_generator
