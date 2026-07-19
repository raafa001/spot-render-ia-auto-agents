"""
Spot Render IA Auto Agents - Capabilities Package
================================================

This package contains the autonomous capabilities for the AI agents:
- Alert Manager: Create and manage alerts
- Runbook Generator: Generate runbooks for issues
- Playbook Generator: Generate incident response playbooks

PT-BR: Este pacote contém as capacidades autônomas para os agentes de IA.
EN-US: This package contains the autonomous capabilities for the AI agents.
"""

from .alert_manager import AlertManager, Alert, AlertSeverity, AlertStatus, get_alert_manager
from .runbook_generator import RunbookGenerator, Runbook, RunbookStep, get_runbook_generator
from .playbook_generator import PlaybookGenerator, Playbook, PlaybookStep, get_playbook_generator

__all__ = [
    # Alert Manager
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "get_alert_manager",
    # Runbook Generator
    "RunbookGenerator",
    "Runbook",
    "RunbookStep",
    "get_runbook_generator",
    # Playbook Generator
    "PlaybookGenerator",
    "Playbook",
    "PlaybookStep",
    "get_playbook_generator",
]
