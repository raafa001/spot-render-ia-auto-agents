"""
Spot Render IA Auto Agents - Alert Manager Capability
====================================================

This module provides the capability to create, manage, and document alerts
based on detected anomalies and issues.

PT-BR: Módulo para criar, gerenciar e documentar alertas baseados em anomalias detectadas.
EN-US: Module to create, manage, and document alerts based on detected anomalies.

Features:
- Create Prometheus-style alerts
- Document alert rationale
- Track alert history
- Integrate with AlertManager (optional)
- Generate alert annotations and labels
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertStatus(Enum):
    """Alert lifecycle status."""
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"


@dataclass
class Alert:
    """
    Represents an alert with full context and documentation.

    PT-BR: Representa um alerta com contexto completo e documentação.
    EN-US: Represents an alert with full context and documentation.
    """
    # Core alert info
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.FIRING

    # Detection context
    detected_at: datetime = field(default_factory=datetime.now)
    detected_by: str = ""  # Agent that detected
    detected_from: str = ""  # Source (metrics, logs, etc.)

    # Issue details
    issue_type: str = ""
    issue_summary: str = ""
    affected_resources: List[str] = field(default_factory=list)

    # Diagnosis
    possible_causes: List[str] = field(default_factory=list)
    primary_cause: str = ""
    confidence: float = 0.0  # 0.0 to 1.0

    # Remediation
    recommended_actions: List[Dict[str, str]] = field(default_factory=list)
    automated_actions: List[str] = field(default_factory=list)
    manual_actions: List[str] = field(default_factory=list)

    # Metadata
    alert_id: str = ""
    runbook_url: str = ""
    dashboard_url: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)

    # History
    resolved_at: Optional[datetime] = None
    duration_seconds: int = 0
    occurrences: int = 1

    def __post_init__(self):
        """Generate alert ID if not provided."""
        if not self.alert_id:
            content = f"{self.name}-{self.detected_at.isoformat()}"
            self.alert_id = hashlib.md5(content.encode()).hexdigest()[:12]

    def to_prometheus_rule(self) -> Dict[str, Any]:
        """
        Convert alert to Prometheus alerting rule format.

        PT-BR: Converte alerta para formato de regra de alerta Prometheus.
        EN-US: Converts alert to Prometheus alerting rule format.
        """
        return {
            "alert": self.name,
            "expr": self.annotations.get("prometheus_expr", "up == 0"),
            "for": self.annotations.get("for_duration", "5m"),
            "labels": {
                "severity": self.severity.value,
                "component": self.labels.get("component", "unknown"),
                "team": self.labels.get("team", "platform"),
                **self.labels
            },
            "annotations": {
                "summary": self.issue_summary,
                "description": self.description,
                "runbook_url": self.runbook_url,
                "dashboard_url": self.dashboard_url,
                "alert_id": self.alert_id,
                **self.annotations
            }
        }

    def to_markdown(self) -> str:
        """
        Generate markdown documentation for the alert.

        PT-BR: Gera documentação em markdown para o alerta.
        EN-US: Generates markdown documentation for the alert.
        """
        duration = self.duration_seconds or int((datetime.now() - self.detected_at).total_seconds())

        md = f"""# Alert: {self.name}

## Overview

| Field | Value |
|-------|-------|
| **ID** | `{self.alert_id}` |
| **Severity** | {self.severity.value.upper()} |
| **Status** | {self.status.value.upper()} |
| **Detected At** | {self.detected_at.isoformat()} |
| **Duration** | {duration} seconds |
| **Detected By** | {self.detected_by} |
| **Source** | {self.detected_from} |

## Issue Details

**Type:** {self.issue_type}

**Summary:** {self.issue_summary}

**Description:** {self.description}

## Affected Resources

{"".join(f"- {r}" for r in self.affected_resources)}

## Diagnosis

**Primary Cause:** {self.primary_cause}

**Confidence:** {self.confidence * 100:.1f}%

**Possible Causes:**

{"".join(f"{i+1}. {c}" for i, c in enumerate(self.possible_causes))}

## Recommended Actions

### Automated Actions (Auto-Heal)

{"".join(f"- `{a}`" for a in self.automated_actions) if self.automated_actions else "_None configured_"}

### Manual Actions

{"".join(f"- {a}" for a in self.manual_actions) if self.manual_actions else "_None required_"}

## Documentation

**Runbook:** {self.runbook_url if self.runbook_url else "_Not created yet_"}

**Dashboard:** {self.dashboard_url if self.dashboard_url else "_Not available_"}

## Prometheus Rule

```yaml
{json.dumps(self.to_prometheus_rule(), indent=2)}
```

## History

- **Occurrences:** {self.occurrences}
- **Resolved At:** {self.resolved_at.isoformat() if self.resolved_at else "_Not resolved_"}

---
_Generated by Spot Render AI Agents on {datetime.now().isoformat()}_
"""
        return md

    def to_json(self) -> str:
        """Convert alert to JSON string."""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        data['detected_at'] = self.detected_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return json.dumps(data, indent=2)


class AlertManager:
    """
    Manages alerts lifecycle - creation, tracking, and documentation.

    PT-BR: Gerencia ciclo de vida de alertas - criação, rastreamento e documentação.
    EN-US: Manages alert lifecycle - creation, tracking, and documentation.
    """

    def __init__(self, storage_path: str = "/var/log/agents/alerts"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._load_history()

    def _load_history(self):
        """Load alert history from storage."""
        history_file = self.storage_path / "alert_history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    data = json.load(f)
                    for alert_data in data:
                        alert_data['severity'] = AlertSeverity(alert_data['severity'])
                        alert_data['status'] = AlertStatus(alert_data['status'])
                        alert_data['detected_at'] = datetime.fromisoformat(alert_data['detected_at'])
                        if alert_data.get('resolved_at'):
                            alert_data['resolved_at'] = datetime.fromisoformat(alert_data['resolved_at'])
                        alert = Alert(**alert_data)
                        self.alert_history.append(alert)
                logger.info(f"Loaded {len(self.alert_history)} alerts from history")
            except Exception as e:
                logger.error(f"Failed to load alert history: {e}")

    def _save_history(self):
        """Save alert history to storage."""
        history_file = self.storage_path / "alert_history.json"
        data = []
        for alert in self.alert_history[-1000:]:  # Keep last 1000
            d = asdict(alert)
            d['severity'] = alert.severity.value
            d['status'] = alert.status.value
            d['detected_at'] = alert.detected_at.isoformat()
            if alert.resolved_at:
                d['resolved_at'] = alert.resolved_at.isoformat()
            data.append(d)
        with open(history_file, 'w') as f:
            json.dump(data, f, indent=2)

    def create_alert(
        self,
        name: str,
        description: str,
        severity: AlertSeverity,
        issue_type: str,
        issue_summary: str,
        detected_by: str,
        detected_from: str,
        affected_resources: List[str],
        possible_causes: List[str],
        primary_cause: str = "",
        confidence: float = 0.0,
        **kwargs
    ) -> Alert:
        """
        Create a new alert with full context.

        PT-BR: Cria novo alerta com contexto completo.
        EN-US: Creates a new alert with full context.
        """
        alert = Alert(
            name=name,
            description=description,
            severity=severity,
            issue_type=issue_type,
            issue_summary=issue_summary,
            detected_by=detected_by,
            detected_from=detected_from,
            affected_resources=affected_resources,
            possible_causes=possible_causes,
            primary_cause=primary_cause,
            confidence=confidence,
            **kwargs
        )

        # Check if similar alert exists
        existing = self._find_similar_alert(alert)
        if existing:
            existing.occurrences += 1
            existing.status = AlertStatus.FIRING
            alert = existing
            logger.info(f"Alert {name} already exists, incrementing occurrences to {existing.occurrences}")
        else:
            self.active_alerts[alert.alert_id] = alert
            logger.info(f"Created new alert: {name} ({alert.alert_id})")

        # Save alert documentation
        self._save_alert_doc(alert)

        return alert

    def _find_similar_alert(self, alert: Alert) -> Optional[Alert]:
        """Find similar existing alert."""
        for existing in self.active_alerts.values():
            if existing.name == alert.name:
                return existing
        return None

    def _save_alert_doc(self, alert: Alert):
        """Save alert documentation."""
        doc_file = self.storage_path / f"{alert.alert_id}.md"
        with open(doc_file, 'w') as f:
            f.write(alert.to_markdown())

    def resolve_alert(self, alert_id: str, resolution_note: str = ""):
        """
        Resolve an active alert.

        PT-BR: Resuelve um alerta ativo.
        EN-US: Resolves an active alert.
        """
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()
            alert.duration_seconds = int((alert.resolved_at - alert.detected_at).total_seconds())
            self.alert_history.append(alert)
            self._save_history()
            logger.info(f"Resolved alert: {alert.name} ({alert_id})")

            # Update documentation
            self._save_alert_doc(alert)

            # Create resolution summary
            self._create_resolution_summary(alert, resolution_note)

    def _create_resolution_summary(self, alert: Alert, note: str):
        """Create resolution summary document."""
        summary_file = self.storage_path / f"{alert.alert_id}_resolution.md"
        duration_min = alert.duration_seconds // 60

        content = f"""# Alert Resolution: {alert.name}

## Summary

| Field | Value |
|-------|-------|
| **Alert ID** | {alert.alert_id} |
| **Duration** | {duration_min} minutes |
| **Occurrences** | {alert.occurrences} |
| **Resolved At** | {alert.resolved_at.isoformat()} |

## Resolution Note

{note if note else "_No additional notes_"}

## Root Cause

{alert.primary_cause}

## Actions Taken

### Automated
{"".join(f"- {a}" for a in alert.automated_actions) if alert.automated_actions else "- None"}

### Manual
{"".join(f"- {a}" for a in alert.manual_actions) if alert.manual_actions else "- None"}

## Lessons Learned

<!-- LLM can fill this in based on the incident -->

## Prevention

<!-- Recommendations for preventing recurrence -->

---
_Resolved by Spot Render AI Agents on {datetime.now().isoformat()}_
"""
        with open(summary_file, 'w') as f:
            f.write(content)

    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        return self.alert_history[-limit:]

    def generate_prometheus_rules(self) -> Dict[str, Any]:
        """
        Generate Prometheus alerting rules from all active alerts.

        PT-BR: Gera regras de alerta Prometheus de todos os alertas ativos.
        EN-US: Generates Prometheus alerting rules from all active alerts.
        """
        rules = []
        for alert in self.active_alerts.values():
            rules.append(alert.to_prometheus_rule())

        return {
            "groups": [{
                "name": "spot-render-ai-agents.rules",
                "interval": "30s",
                "rules": rules
            }]
        }

    def export_alertmanager_config(self) -> Dict[str, Any]:
        """
        Export AlertManager configuration for active alerts.

        PT-BR: Exporta configuração do AlertManager para alertas ativos.
        EN-US: Exports AlertManager configuration for active alerts.
        """
        routes = []
        for alert in self.active_alerts.values():
            routes.append({
                "match": {"alertname": alert.name},
                "receiver": f"alerts-{alert.severity.value}",
                "group_wait": "30s",
                "group_interval": "5m",
                "repeat_interval": "4h"
            })

        return {
            "route": {
                "receiver": "alerts-critical",
                "routes": routes
            },
            "receivers": [
                {"name": "alerts-critical", "slack_configs": [{"channel": "#alerts-critical"}]},
                {"name": "alerts-warning", "slack_configs": [{"channel": "#alerts-warning"}]},
                {"name": "alerts-info", "slack_configs": [{"channel": "#alerts-info"}]}
            ]
        }


# Global instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global AlertManager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
