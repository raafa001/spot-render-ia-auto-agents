# Spot Render IA Auto Agent

> **PT-BR:** Agentes autônomos de IA para monitoramento, observabilidade e self-healing do cluster Kubernetes.
>
> **EN:** Autonomous AI agents for Kubernetes cluster monitoring, observability, and self-healing.

## Overview

The **Spot Render IA Auto Agent** is a multi-agent system designed to autonomously monitor, diagnose, and heal issues in Kubernetes clusters and applications. It combines traditional AIOps techniques with LLM-powered decision making for intelligent automation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Spot Render IA Auto Agent                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   SRE Agent  │  │  DevOps Agent │  │ Self-Healing │       │
│  │              │  │              │  │    Agent      │       │
│  │ • Metrics    │  │ • K8s State  │  │ • Diagnose    │       │
│  │ • Logs       │  │ • Deploys    │  │ • Remedy      │       │
│  │ • Alerts     │  │ • Scaling    │  │ • Document    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │                │
│         └──────────────────┼──────────────────┘                │
│                            │                                   │
│                    ┌───────▼───────┐                          │
│                    │  Agent Core   │                          │
│                    │  Communication │                          │
│                    │  & Coordination│                          │
│                    └───────────────┘                          │
│                            │                                   │
│                    ┌───────▼───────┐                          │
│                    │   LLM Brain    │                          │
│                    │   (Ollama)     │                          │
│                    └───────────────┘                          │
│                            │                                   │
│                    ┌───────▼───────┐                          │
│                    │  RAG Knowledge │                          │
│                    │     Base       │                          │
│                    └───────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Agents

### 1. SRE Agent (DaemonSet)
- **Role:** Monitor metrics and logs
- **Profile:** Reliability focused
- **Responsibilities:**
  - CPU, Memory, Network, Disk metrics monitoring
  - Application logs parsing and anomaly detection
  - Prometheus/Grafana integration
  - Alert generation and correlation

### 2. DevOps Agent (StatefulSet)
- **Role:** Infrastructure management
- **Profile:** Automation focused
- **Responsibilities:**
  - Kubernetes resource management
  - Deployment orchestration
  - Scaling operations
  - Configuration management

### 3. Self-Healing Agent (Deployment)
- **Role:** Autonomous remediation
- **Profile:** Decision making focused
- **Responsibilities:**
  - Root cause analysis using LLM
  - Remediation action execution
  - Runbook automation
  - Incident documentation

## Features

- **Autonomous Operation**: Agents work independently and coordinate when needed
- **LLM-Powered**: Uses local Ollama for intelligent decision making
- **RAG Integration**: Uses documentation as knowledge base
- **Self-Healing**: Automatically remediates common issues
- **Multi-Profile**: Different agents with different specializations
- **Communication**: Agents share context to avoid overload
- **Snapshots**: Takes error/metric snapshots for analysis
- **Documentation**: All actions and decisions are logged

## Quick Start

### Prerequisites
- Kubernetes cluster 1.28+
- Python 3.11+
- Ollama running (for LLM features)
- kubectl configured

### Installation

```bash
# Clone the repository
git clone https://github.com/raafa001/spot-render-ia-auto-agent.git
cd spot-render-ia-auto-agent

# Install dependencies
pip install -e ".[all]"

# Deploy to Kubernetes
kubectl apply -k kubernetes/base/

# Check agent status
kubectl get pods -n spot-render-ai-agents
```

### Configuration

```bash
# Set environment variables
export OLLAMA_URL=http://ollama.spot-render.svc.cluster.local:11434
export LOG_LEVEL=INFO
export AGENT_PROFILE=sre  # sre, devops, self-healing
```

## Repository Structure

```
spot-render-ia-auto-agent/
├── agents/                 # Agent implementations
│   ├── __init__.py
│   ├── sre_agent.py       # SRE monitoring agent
│   ├── devops_agent.py    # DevOps automation agent
│   └── self_healing_agent.py  # Self-healing agent
├── core/                  # Core framework
│   ├── __init__.py
│   ├── agent_base.py      # Base agent class
│   ├── communication.py   # Inter-agent communication
│   ├── llm.py            # LLM integration
│   ├── rag.py            # RAG knowledge base
│   └── snapshot.py       # Snapshot taking
├── kubernetes/           # K8s manifests
│   ├── base/            # Base manifests
│   └── overlays/        # Environment overlays
├── docs/                # Documentation
│   ├── agents.md        # Agent documentation
│   └── api.md          # API documentation
├── tests/              # Unit tests
├── pyproject.toml       # Python project config
└── README.md           # This file
```

## Documentation

- [Agent Documentation](docs/agents.md) - Detailed agent descriptions
- [API Documentation](docs/api.md) - Agent APIs and interfaces
- [Deployment Guide](docs/deployment.md) - Kubernetes deployment
- [Architecture](docs/architecture.md) - System architecture

## Agent Communication

Agents communicate via:

1. **Kubernetes Events**: For immediate alerts
2. **Shared ConfigMaps**: For state sharing
3. **Message Queue**: For async coordination
4. **LLM Context**: For collaborative reasoning

## Self-Healing Capabilities

| Issue | Detection | Remediation |
|-------|-----------|-------------|
| High CPU | Metrics | Scale/HPA |
| OOM | Metrics | Restart/Scale |
| CrashLoopBackOff | Pod Status | Debug/Restart |
| Network Issues | Connectivity | Retry/Notify |
| Disk Full | Metrics | Cleanup/PVC |
| Service Down | Health | Redeploy/Notify |

## Metrics

The system tracks:
- MTTD (Mean Time to Detect)
- MTTR (Mean Time to Remediate)
- Alert Precision/Recall
- Agent Utilization
- Action Success Rate

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a PR

## License

MIT License - See LICENSE file for details.

## Authors

Spot Render Team
