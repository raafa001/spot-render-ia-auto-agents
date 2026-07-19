# Spot Render IA Auto Agent

> **PT-BR:** Agentes autônomos de IA para monitoramento, observabilidade e self-healing do cluster Kubernetes.
>
> **EN:** Autonomous AI agents for Kubernetes cluster monitoring, observability, and self-healing.

## Table of Contents / Índice

- [Overview](#overview)
- [Architecture](#architecture)
- [Agents](#agents)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)

---

## Overview

O **Spot Render IA Auto Agent** é um sistema multi-agente projetado para monitorar, diagnosticar e corrigir automaticamente problemas em clusters Kubernetes e aplicações.

### Key Features / Principais Funcionalidades

- **Autonomous Operation**: Agentes trabalham independentemente e coordenam quando necessário
- **LLM-Powered**: Usa Ollama local para tomada de decisão inteligente
- **RAG Integration**: Usa documentação como base de conhecimento
- **Self-Healing**: Corrige automaticamente problemas comuns
- **Multi-Profile**: Diferentes agentes com diferentes especializações
- **Communication**: Agentes compartilham contexto para evitar sobrecarga
- **Snapshots**: Captura erros/métricas para análise

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Spot Render IA Auto Agent                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   SRE Agent  │  │  DevOps Agent │  │ Self-Healing │          │
│  │              │  │              │  │    Agent     │          │
│  │ • Metrics    │  │ • K8s State  │  │ • Diagnose   │          │
│  │ • Logs       │  │ • Deploys    │  │ • Remedy     │          │
│  │ • Alerts     │  │ • Scaling   │  │ • Document   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                   │
│                    ┌───────▼───────┐                           │
│                    │  Agent Core   │                           │
│                    │  Communication│                           │
│                    │  & Coordination│                           │
│                    └───────────────┘                           │
│                            │                                   │
│                    ┌───────▼───────┐                           │
│                    │   LLM Brain    │                           │
│                    │   (Ollama)     │                           │
│                    └───────────────┘                           │
│                            │                                   │
│                    ┌───────▼───────┐                           │
│                    │  RAG Knowledge │                           │
│                    │     Base       │                           │
│                    └───────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agents

### 1. SRE Agent (DaemonSet)

**Profile:** Reliability focused

**Responsibilities:**
- CPU, Memory, Network, Disk metrics monitoring
- Application logs parsing and anomaly detection
- Prometheus/Grafana integration
- Alert generation and correlation

**Resources:**
- CPU: 100m-500m
- Memory: 128Mi-512Mi

### 2. DevOps Agent (StatefulSet)

**Profile:** Automation focused

**Responsibilities:**
- Kubernetes resource management
- Deployment orchestration
- Scaling operations
- Configuration management

**Resources:**
- CPU: 200m-1000m
- Memory: 256Mi-1Gi

### 3. Self-Healing Agent (Deployment)

**Profile:** Decision making focused

**Responsibilities:**
- Root cause analysis using LLM
- Remediation action execution
- Runbook automation
- Incident documentation

**Resources:**
- CPU: 300m-1500m
- Memory: 512Mi-2Gi

---

## Deployment

### Prerequisites

- Kubernetes cluster 1.28+
- Python 3.11+
- Ollama running (for LLM features)
- kubectl configured

### Quick Start

```bash
# Clone the repository
git clone https://github.com/raafa001/spot-render-ia-auto-agent.git
cd spot-render-ia-auto-agent

# Install dependencies
pip install -e ".[all]"

# Build Docker image
docker build -t spot-render-ia-agent:latest .

# Deploy to Kubernetes
kubectl apply -k kubernetes/base/

# Check agent status
kubectl get pods -n spot-render-ai-agents
```

### Verify Deployment

```bash
# Check all agents are running
kubectl get pods -n spot-render-ai-agents

# Check logs
kubectl logs -n spot-render-ai-agents deployment/sre-agent
kubectl logs -n spot-render-ai-agents statefulset/devops-agent
kubectl logs -n spot-render-ai-agents deployment/self-healing-agent

# Check ConfigMaps
kubectl get configmaps -n spot-render-ai-agents
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENT_NAME` | Agent identifier | agent-name |
| `AGENT_PROFILE` | Agent profile (sre/devops/self_healing) | - |
| `AGENT_NAMESPACE` | Target namespace to monitor | spot-render |
| `OLLAMA_URL` | Ollama API URL | http://ollama:11434 |
| `OLLAMA_MODEL` | Ollama model name | llama3.2:latest |
| `LOG_LEVEL` | Logging level | INFO |
| `SNAPSHOT_RETENTION_COUNT` | Max snapshots to retain | 1000 |
| `SNAPSHOT_RETENTION_HOURS` | Snapshot retention in hours | 72 |

### ConfigMap Configuration

The `agent-config` ConfigMap contains default configuration:

```yaml
data:
  AGENT_NAMESPACE: "spot-render"
  AGENT_LOG_LEVEL: "INFO"
  OLLAMA_URL: "http://ollama.spot-render.svc.cluster.local:11434"
  OLLAMA_MODEL: "llama3.2:latest"
  SNAPSHOT_RETENTION_COUNT: "1000"
  SNAPSHOT_RETENTION_HOURS: "72"
  DECISION_THRESHOLD: "0.7"
```

---

## How It Works

### Agent Communication

Agents communicate via:

1. **Kubernetes Events**: For immediate alerts
2. **Shared ConfigMaps**: For state sharing
3. **Message Bus**: For async coordination
4. **LLM Context**: For collaborative reasoning

### Self-Healing Flow

```
1. Alert Detection (SRE Agent)
   └─> Takes metric/log snapshots
   └─> Broadcasts alert to agents

2. Diagnosis (Self-Healing Agent)
   └─> Receives alert
   └─> Requests diagnosis from SRE Agent
   └─> Uses LLM to analyze symptoms
   └─> Creates diagnostic result

3. Remediation Planning (Self-Healing Agent)
   └─> Uses LLM to plan actions
   └─> Checks available runbooks
   └─> Determines risk level

4. Execution (DevOps Agent + Self-Healing Agent)
   └─> Claims operation
   └─> Executes remediation
   └─> Documents result
   └─> Updates RAG knowledge base
```

### Snapshot System

Snapshots capture:

- **Metric Snapshots**: CPU, memory, pod counts
- **Error Snapshots**: Crash events, failures
- **Log Snapshots**: Error patterns in logs
- **State Snapshots**: System state at point in time

---

## API Reference

### Message Types

#### Alert Message
```json
{
  "id": "msg-123",
  "sender": "sre-agent",
  "receiver": "self-healing-agent",
  "message_type": "alert",
  "payload": {
    "type": "pod_issue",
    "pod": "spot-render-web-abc123",
    "issue": "CrashLoopBackOff",
    "severity": "error"
  }
}
```

#### Diagnose Request
```json
{
  "message_type": "diagnose_request",
  "payload": {
    "target": "pod-name",
    "type": "pod"
  }
}
```

#### Scale Request
```json
{
  "message_type": "scale_request",
  "payload": {
    "target": "deployment-name",
    "replicas": 3
  }
}
```

---

## Metrics

The system tracks:

- **MTTD** (Mean Time to Detect)
- **MTTR** (Mean Time to Remediate)
- **Alert Precision/Recall**
- **Agent Utilization**
- **Action Success Rate**

---

## Troubleshooting

### Agent Not Starting

```bash
# Check agent logs
kubectl logs -n spot-render-ai-agents <agent-pod>

# Check events
kubectl get events -n spot-render-ai-agents

# Verify ConfigMaps
kubectl describe configmap agent-config -n spot-render-ai-agents
```

### Ollama Connection Issues

```bash
# Test Ollama connectivity
kubectl exec -n spot-render-ai-agents deploy/self-healing-agent -- \
  curl -s http://ollama:11434/api/tags

# Check Ollama service
kubectl get svc -n spot-render | grep ollama
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a PR

---

## License

MIT License - See LICENSE file for details.
