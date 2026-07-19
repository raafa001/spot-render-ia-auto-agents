# Spot Render IA Auto Agents - Monitoring Guide

> **PT-BR:** Guia completo de monitoramento para os Agentes Autônomos
> **EN-US:** Complete monitoring guide for Autonomous Agents

## 📊 Overview

This document describes the monitoring strategy, metrics, dashboards, and alerts for the Autonomous AI Agents in the Spot Render platform.

## 🤖 Agent Metrics

### SRE Agent Metrics

| Metric | Description | Type | Alert Threshold |
|--------|-------------|------|-----------------|
| `sre_agent_cycle_duration_seconds` | Time for one monitoring cycle | Histogram | p99 > 60s |
| `sre_agent_errors_detected_total` | Total errors detected | Counter | > 10/hour |
| `sre_agent_snapshots_created_total` | Total metric snapshots | Counter | N/A |
| `sre_agent_anomalies_detected_total` | Anomalies found | Counter | > 5/hour |
| `sre_agent_messages_sent_total` | Messages to other agents | Counter | N/A |

### DevOps Agent Metrics

| Metric | Description | Type | Alert Threshold |
|--------|-------------|------|-----------------|
| `devops_agent_operations_total` | Total operations performed | Counter | N/A |
| `devops_agent_scale_operations_total` | Scale up/down operations | Counter | N/A |
| `devops_agent_restart_operations_total` | Pod restart operations | Counter | N/A |
| `devops_agent_operation_duration_seconds` | Operation duration | Histogram | p99 > 30s |
| `devops_agent_errors_total` | Operation errors | Counter | > 5/hour |

### Self-Healing Agent Metrics

| Metric | Description | Type | Alert Threshold |
|--------|-------------|------|-----------------|
| `self_healing_agent_decisions_total` | LLM decisions made | Counter | N/A |
| `self_healing_agent_remediations_total` | Remediations executed | Counter | N/A |
| `self_healing_agent_remediations_successful` | Successful remediations | Counter | > 80% success |
| `self_healing_agent_llm_calls_total` | LLM API calls | Counter | N/A |
| `self_healing_agent_llm_latency_seconds` | LLM response time | Histogram | p99 > 30s |
| `self_healing_agent_rollbacks_total` | Rollbacks due to failure | Counter | > 2/hour |

### Cross-Agent Metrics

| Metric | Description | Type | Alert Threshold |
|--------|-------------|------|-----------------|
| `agent_communication_messages_total` | Inter-agent messages | Counter | N/A |
| `agent_communication_errors_total` | Message delivery errors | Counter | > 1/hour |
| `agent_shared_state_updates_total` | Shared state updates | Counter | N/A |
| `ollama_unavailable_total` | Ollama unreachable events | Counter | > 0 |

## 📈 Prometheus Configuration

### Agent Metrics Exporter

Each agent should expose metrics on port 8080 at `/metrics`:

```python
# metrics_server.py
from prometheus_client import start_http_server, Counter, Histogram, Gauge
import time

# Define metrics
CYCLE_DURATION = Histogram('sre_agent_cycle_duration_seconds', 'Cycle duration')
ERRORS_DETECTED = Counter('sre_agent_errors_detected_total', 'Errors detected')
ANOMALIES_DETECTED = Counter('sre_agent_anomalies_detected_total', 'Anomalies detected')

def start_metrics_server(port=8080):
    start_http_server(port)
    print(f"Metrics server started on port {port}")
```

### Prometheus Scrape Config

```yaml
# prometheus-scrape-configs.yaml
scrape_configs:
  # AI Agents
  - job_name: 'ai-agents'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_namespace]
        action: keep
        regex: spot-render-ai-agents
      - source_labels: [__meta_kubernetes_pod_container_port_number]
        action: keep
        regex: "8080"
    metrics_path: '/metrics'

  # Ollama
  - job_name: 'ollama'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_namespace]
        action: keep
        regex: spot-ai
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: ollama
```

## 📊 Grafana Dashboards

### Dashboard: AI Agents Overview

```json
{
  "dashboard": {
    "title": "Spot Render - AI Agents Overview",
    "uid": "ai-agents-overview",
    "panels": [
      {
        "title": "Agent Status",
        "type": "table",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 6},
        "targets": [
          {
            "expr": "kube_pod_status_phase{namespace='spot-render-ai-agents'}",
            "format": "table"
          }
        ]
      },
      {
        "title": "SRE Agent - Monitoring Cycles",
        "type": "graph",
        "gridPos": {"x": 0, "y": 6, "w": 8, "h": 8},
        "targets": [
          {
            "expr": "rate(sre_agent_cycle_duration_seconds_count[5m])",
            "legendFormat": "Cycles/min"
          }
        ]
      },
      {
        "title": "SRE Agent - Errors Detected",
        "type": "graph",
        "gridPos": {"x": 8, "y": 6, "w": 8, "h": 8},
        "targets": [
          {
            "expr": "rate(sre_agent_errors_detected_total[5m])",
            "legendFormat": "Errors/min"
          }
        ]
      },
      {
        "title": "SRE Agent - Anomalies",
        "type": "graph",
        "gridPos": {"x": 16, "y": 6, "w": 8, "h": 8},
        "targets": [
          {
            "expr": "rate(sre_agent_anomalies_detected_total[5m])",
            "legendFormat": "Anomalies/min"
          }
        ]
      },
      {
        "title": "DevOps Agent - Operations",
        "type": "graph",
        "gridPos": {"x": 0, "y": 14, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(devops_agent_scale_operations_total[5m])",
            "legendFormat": "Scale Ops/min"
          },
          {
            "expr": "rate(devops_agent_restart_operations_total[5m])",
            "legendFormat": "Restart Ops/min"
          }
        ]
      },
      {
        "title": "Self-Healing - Remediations",
        "type": "graph",
        "gridPos": {"x": 12, "y": 14, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(self_healing_agent_remediations_total[5m])",
            "legendFormat": "Remediations/min"
          },
          {
            "expr": "rate(self_healing_agent_remediations_successful[5m])",
            "legendFormat": "Successful/min"
          }
        ]
      },
      {
        "title": "LLM Latency (p99)",
        "type": "graph",
        "gridPos": {"x": 0, "y": 22, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(self_healing_agent_llm_latency_seconds_bucket[5m]))",
            "legendFormat": "p99 LLM Latency"
          }
        ],
        "alert": {
          "name": "High LLM Latency",
          "conditions": [
            {
              "evaluator": {"params": [30], "type": "gt"},
              "operator": {"type": "and"},
              "query": {"params": ["A", "5m", "now"]}
            }
          ]
        }
      },
      {
        "title": "Ollama Availability",
        "type": "stat",
        "gridPos": {"x": 12, "y": 22, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "1 - rate(ollama_unavailable_total[5m])",
            "legendFormat": "Availability"
          }
        ]
      },
      {
        "title": "Inter-Agent Messages",
        "type": "graph",
        "gridPos": {"x": 18, "y": 22, "w": 6, "h": 8},
        "targets": [
          {
            "expr": "rate(agent_communication_messages_total[5m])",
            "legendFormat": "Messages/min"
          }
        ]
      }
    ]
  }
}
```

## 🚨 Alert Rules

```yaml
# ai-agents-alerts.yaml
groups:
  - name: ai-agents-alerts
    interval: 30s
    rules:
      # SRE Agent Down
      - alert: SREAgentDown
        expr: absent(kube_pod_status_phase{namespace="spot-render-ai-agents", pod=~"sre-agent-.*", phase="Running"})
        for: 2m
        labels:
          severity: critical
          component: sre-agent
        annotations:
          summary: "SRE Agent is down"
          description: "SRE Agent has been down for more than 2 minutes"
          runbook_url: "https://docs.spot-render.local/runbooks/sre-agent-down"

      # DevOps Agent Down
      - alert: DevOpsAgentDown
        expr: absent(kube_pod_status_phase{namespace="spot-render-ai-agents", pod=~"devops-agent-.*", phase="Running"})
        for: 2m
        labels:
          severity: critical
          component: devops-agent
        annotations:
          summary: "DevOps Agent is down"
          description: "DevOps Agent has been down for more than 2 minutes"
          runbook_url: "https://docs.spot-render.local/runbooks/devops-agent-down"

      # Self-Healing Agent Down
      - alert: SelfHealingAgentDown
        expr: absent(kube_pod_status_phase{namespace="spot-render-ai-agents", pod=~"self-healing-agent-.*", phase="Running"})
        for: 2m
        labels:
          severity: critical
          component: self-healing-agent
        annotations:
          summary: "Self-Healing Agent is down"
          description: "Self-Healing Agent has been down for more than 2 minutes"
          runbook_url: "https://docs.spot-render.local/runbooks/self-healing-agent-down"

      # High Error Detection Rate
      - alert: SREAgentHighErrorRate
        expr: rate(sre_agent_errors_detected_total[1h]) > 10
        for: 10m
        labels:
          severity: warning
          component: sre-agent
        annotations:
          summary: "SRE Agent is detecting many errors"
          description: "Error detection rate is {{ $value }} per hour"
          runbook_url: "https://docs.spot-render.local/runbooks/sre-agent-high-error-rate"

      # High LLM Latency
      - alert: SelfHealingHighLLMLatency
        expr: histogram_quantile(0.99, rate(self_healing_agent_llm_latency_seconds_bucket[5m])) > 30
        for: 5m
        labels:
          severity: warning
          component: self-healing-agent
        annotations:
          summary: "Self-Healing Agent LLM latency is high"
          description: "p99 LLM latency is {{ $value }} seconds"
          runbook_url: "https://docs.spot-render.local/runbooks/self-healing-high-latency"

      # Low Remediation Success Rate
      - alert: SelfHealingLowSuccessRate
        expr: |
          (
            rate(self_healing_agent_remediations_successful[1h]) /
            rate(self_healing_agent_remediations_total[1h])
          ) < 0.8
        for: 30m
        labels:
          severity: warning
          component: self-healing-agent
        annotations:
          summary: "Self-Healing Agent success rate is low"
          description: "Remediation success rate is {{ $value | humanizePercentage }}"
          runbook_url: "https://docs.spot-render.local/runbooks/self-healing-low-success-rate"

      # Ollama Unreachable
      - alert: OllamaUnreachableFromAgents
        expr: increase(ollama_unavailable_total[5m]) > 0
        for: 1m
        labels:
          severity: critical
          component: ai-agents
        annotations:
          summary: "AI Agents cannot reach Ollama"
          description: "Ollama has been unreachable for 1 minute"
          runbook_url: "https://docs.spot-render.local/runbooks/ollama-unreachable"

      # High Agent Restart Rate
      - alert: AIAgentsHighRestartRate
        expr: increase(kube_pod_restart_total{namespace="spot-render-ai-agents"}[1h]) > 3
        for: 5m
        labels:
          severity: warning
          component: ai-agents
        annotations:
          summary: "AI Agents are restarting frequently"
          description: "Agents have restarted {{ $value }} times in the last hour"
          runbook_url: "https://docs.spot-render.local/runbooks/ai-agents-restarting"

      # Inter-Agent Communication Failure
      - alert: AgentCommunicationFailure
        expr: rate(agent_communication_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
          component: ai-agents
        annotations:
          summary: "Inter-agent communication is failing"
          description: "Communication error rate is {{ $value }} per second"
          runbook_url: "https://docs.spot-render.local/runbooks/agent-communication-failure"
```

## 🔧 Custom Metrics Implementation

### Example: SRE Agent Metrics

```python
# sre_agent/metrics.py
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

registry = CollectorRegistry()

# Counters
errors_detected = Counter(
    'sre_agent_errors_detected_total',
    'Total errors detected',
    ['error_type'],
    registry=registry
)

anomalies_detected = Counter(
    'sre_agent_anomalies_detected_total',
    'Total anomalies detected',
    ['anomaly_type'],
    registry=registry
)

snapshots_created = Counter(
    'sre_agent_snapshots_created_total',
    'Total snapshots created',
    registry=registry
)

messages_sent = Counter(
    'sre_agent_messages_sent_total',
    'Messages sent to other agents',
    ['destination'],
    registry=registry
)

# Histograms
cycle_duration = Histogram(
    'sre_agent_cycle_duration_seconds',
    'Time for one monitoring cycle',
    buckets=[5, 10, 30, 60, 120, 300],
    registry=registry
)

# Gauges
last_cycle_time = Gauge(
    'sre_agent_last_cycle_timestamp',
    'Timestamp of last cycle',
    registry=registry
)

active_alerts = Gauge(
    'sre_agent_active_alerts',
    'Number of active alerts',
    registry=registry
)
```

### Example: Self-Healing Agent Metrics

```python
# self_healing_agent/metrics.py
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

registry = CollectorRegistry()

# Counters
decisions_total = Counter(
    'self_healing_agent_decisions_total',
    'Total LLM decisions',
    ['decision_type', 'outcome'],
    registry=registry
)

remediations_total = Counter(
    'self_healing_agent_remediations_total',
    'Total remediations attempted',
    ['action_type'],
    registry=registry
)

remediations_successful = Counter(
    'self_healing_agent_remediations_successful',
    'Successful remediations',
    ['action_type'],
    registry=registry
)

llm_calls = Counter(
    'self_healing_agent_llm_calls_total',
    'Total LLM API calls',
    ['status'],
    registry=registry
)

rollbacks = Counter(
    'self_healing_agent_rollbacks_total',
    'Total rollbacks',
    registry=registry
)

# Histograms
llm_latency = Histogram(
    'self_healing_agent_llm_latency_seconds',
    'LLM response time',
    buckets=[1, 5, 10, 20, 30, 60],
    registry=registry
)

remediation_duration = Histogram(
    'self_healing_agent_remediation_duration_seconds',
    'Time to complete remediation',
    buckets=[5, 10, 30, 60, 120, 300],
    registry=registry
)

# Gauges
pending_decisions = Gauge(
    'self_healing_agent_pending_decisions',
    'Pending LLM decisions',
    registry=registry
)

active_remediations = Gauge(
    'self_healing_agent_active_remediations',
    'Active remediations in progress',
    registry=registry
)
```

## 📝 Runbooks

### Runbook: SRE Agent Down

```markdown
# Runbook: SRE Agent Down

## Severity: Critical

## Symptoms
- SRE Agent pod is not Running
- No metric snapshots being created
- Alert: SREAgentDown

## Diagnosis
1. Check pod status:
   ```bash
   kubectl get pods -n spot-render-ai-agents -l app=sre-agent
   kubectl describe pod -n spot-render-ai-agents -l app=sre-agent
   ```

2. Check logs:
   ```bash
   kubectl logs -n spot-render-ai-agents -l app=sre-agent --tail=100
   ```

3. Verify RBAC:
   ```bash
   kubectl auth can-i get pods --as=system:serviceaccount:spot-render-ai-agents:sre-agent
   ```

## Resolution
1. If CrashLoopBackOff:
   - Check logs for errors
   - Verify dependencies (Ollama connectivity)
   - Adjust memory limits if needed

2. If ImagePullBackOff:
   - Verify image exists
   - Check registry credentials

3. Restart deployment:
   ```bash
   kubectl rollout restart daemonset/sre-agent -n spot-render-ai-agents
   ```

## Prevention
- Set appropriate resource limits
- Monitor memory usage
- Configure proper health checks
```

### Runbook: Self-Healing Low Success Rate

```markdown
# Runbook: Self-Healing Low Success Rate

## Severity: Warning

## Symptoms
- Remediation success rate < 80%
- High number of rollbacks
- Alert: SelfHealingLowSuccessRate

## Diagnosis
1. Check recent remediations:
   ```bash
   kubectl logs -n spot-render-ai-agents -l app=self-healing-agent --tail=500 | grep remediation
   ```

2. Check LLM responses:
   ```bash
   kubectl logs -n spot-render-ai-agents -l app=self-healing-agent --tail=500 | grep "llm"
   ```

3. Review recent decisions:
   ```bash
   kubectl exec -it -n spot-render-ai-agents deploy/self-healing-agent -- cat /var/log/decisions.json
   ```

## Resolution
1. If LLM is returning poor responses:
   - Check Ollama health
   - Verify model is loaded correctly
   - Consider adjusting system prompt

2. If actions are failing:
   - Verify RBAC permissions
   - Check target resource availability
   - Review action definitions

3. Adjust threshold temporarily:
   ```bash
   kubectl edit configmap agent-config -n spot-render-ai-agents
   # Increase DECISION_THRESHOLD
   ```

## Prevention
- Monitor LLM response quality
- Regular review of remediation patterns
- A/B test different prompts
```

## 🔍 Quick Reference Commands

```bash
# Check all agents
kubectl get pods -n spot-render-ai-agents

# View SRE Agent logs
kubectl logs -n spot-render-ai-agents daemonset/sre-agent -f

# View DevOps Agent logs
kubectl logs -n spot-render-ai-agents deployment/devops-agent -f

# View Self-Healing Agent logs
kubectl logs -n spot-render-ai-agents deployment/self-healing-agent -f

# Check agent metrics
kubectl exec -it -n spot-render-ai-agents deploy/self-healing-agent -- curl localhost:8080/metrics

# Verify RBAC
kubectl auth can-i get pods --as=system:serviceaccount:spot-render-ai-agents:ai-agents -n spot-render

# Check ConfigMaps
kubectl get configmap -n spot-render-ai-agents

# View shared state
kubectl get configmap agent-shared-state -n spot-render-ai-agents -o yaml

# View inter-agent messages
kubectl get configmap agent-messages -n spot-render-ai-agents -o yaml

# Restart agents
kubectl rollout restart daemonset/sre-agent -n spot-render-ai-agents
kubectl rollout restart deployment/devops-agent -n spot-render-ai-agents
kubectl rollout restart deployment/self-healing-agent -n spot-render-ai-agents
```

---

**Document Version:** 1.0.0
**Last Updated:** 2026-07-19
