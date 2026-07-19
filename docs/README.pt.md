# Spot Render IA Auto Agent

> **PT-BR:** Agentes autônomos de IA para monitoramento, observabilidade e self-healing do cluster Kubernetes.
>
> **EN:** Autonomous AI agents for Kubernetes cluster monitoring, observability, and self-healing.

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Agentes](#agentes)
- [Implantação](#implantação)
- [Configuração](#configuração)
- [Como Funciona](#como-funciona)
- [Referência da API](#referência-da-api)

---

## Visão Geral

O **Spot Render IA Auto Agent** é um sistema multi-agente projetado para monitorar, diagnosticar e corrigir automaticamente problemas em clusters Kubernetes e aplicações.

### Funcionalidades Principais

- **Operação Autônoma**: Agentes trabalham independentemente e coordenam quando necessário
- **Powered by LLM**: Usa Ollama local para tomada de decisão inteligente
- **Integração RAG**: Usa documentação como base de conhecimento
- **Self-Healing**: Corrige automaticamente problemas comuns
- **Multi-Perfil**: Diferentes agentes com diferentes especializações
- **Comunicação**: Agentes compartilham contexto para evitar sobrecarga
- **Snapshots**: Captura erros/métricas para análise

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Spot Render IA Auto Agent                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  SRE Agent   │  │ DevOps Agent │  │Self-Healing │          │
│  │              │  │              │  │    Agent     │          │
│  │ • Métricas   │  │ • Estado K8s │  │ • Diagnostic │          │
│  │ • Logs       │  │ • Deploys    │  │ • Remediar   │          │
│  │ • Alertas    │  │ • Scaling    │  │ • Documentar │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                  │
│         └──────────────────┼──────────────────┘                  │
│                            │                                   │
│                    ┌───────▼───────┐                           │
│                    │  Core Agent   │                           │
│                    │  Comunicação   │                           │
│                    │  & Coordenação │                           │
│                    └───────────────┘                           │
│                            │                                   │
│                    ┌───────▼───────┐                           │
│                    │  Cérebro LLM   │                           │
│                    │   (Ollama)     │                           │
│                    └───────────────┘                           │
│                            │                                   │
│                    ┌───────▼───────┐                           │
│                    │ Base RAG       │                           │
│                    │ Conhecimento   │                           │
│                    └───────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agentes

### 1. SRE Agent (DaemonSet)

**Perfil:** Focado em confiabilidade

**Responsabilidades:**
- Monitoramento de métricas de CPU, Memória, Rede, Disco
- Parsing de logs de aplicação e detecção de anomalias
- Integração com Prometheus/Grafana
- Geração e correlação de alertas

**Recursos:**
- CPU: 100m-500m
- Memória: 128Mi-512Mi

### 2. DevOps Agent (StatefulSet)

**Perfil:** Focado em automação

**Responsabilidades:**
- Gerenciamento de recursos Kubernetes
- Orquestração de deployments
- Operações de scaling
- Gerenciamento de configuração

**Recursos:**
- CPU: 200m-1000m
- Memória: 256Mi-1Gi

### 3. Self-Healing Agent (Deployment)

**Perfil:** Focado em tomada de decisão

**Responsabilidades:**
- Análise de causa raiz usando LLM
- Execução de ações de remediação
- Automação de runbooks
- Documentação de incidentes

**Recursos:**
- CPU: 300m-1500m
- Memória: 512Mi-2Gi

---

## Implantação

### Pré-requisitos

- Cluster Kubernetes 1.28+
- Python 3.11+
- Ollama rodando (para recursos LLM)
- kubectl configurado

### Início Rápido

```bash
# Clonar o repositório
git clone https://github.com/raafa001/spot-render-ia-auto-agent.git
cd spot-render-ia-auto-agent

# Instalar dependências
pip install -e ".[all]"

# Build da imagem Docker
docker build -t spot-render-ia-agent:latest .

# Deploy no Kubernetes
kubectl apply -k kubernetes/base/

# Verificar status dos agentes
kubectl get pods -n spot-render-ai-agents
```

### Verificar Implantação

```bash
# Verificar todos os agentes
kubectl get pods -n spot-render-ai-agents

# Verificar logs
kubectl logs -n spot-render-ai-agents deployment/sre-agent
kubectl logs -n spot-render-ai-agents statefulset/devops-agent
kubectl logs -n spot-render-ai-agents deployment/self-healing-agent

# Verificar ConfigMaps
kubectl get configmaps -n spot-render-ai-agents
```

---

## Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `AGENT_NAME` | Identificador do agente | agent-name |
| `AGENT_PROFILE` | Perfil do agente (sre/devops/self_healing) | - |
| `AGENT_NAMESPACE` | Namespace alvo para monitorar | spot-render |
| `OLLAMA_URL` | URL da API Ollama | http://ollama:11434 |
| `OLLAMA_MODEL` | Nome do modelo Ollama | llama3.2:latest |
| `LOG_LEVEL` | Nível de logging | INFO |
| `SNAPSHOT_RETENTION_COUNT` | Máximo de snapshots | 1000 |
| `SNAPSHOT_RETENTION_HOURS` | Retenção de snapshots em horas | 72 |

### Configuração via ConfigMap

O `agent-config` ConfigMap contém a configuração padrão:

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

## Como Funciona

### Comunicação entre Agentes

Agentes se comunicam via:

1. **Kubernetes Events**: Para alertas imediatos
2. **ConfigMaps Compartilhados**: Para compartilhamento de estado
3. **Message Bus**: Para coordenação assíncrona
4. **Contexto LLM**: Para raciocínio colaborativo

### Fluxo de Self-Healing

```
1. Detecção de Alerta (SRE Agent)
   └─> Captura snapshots de métricas/logs
   └─> Transmite alerta para agentes

2. Diagnóstico (Self-Healing Agent)
   └─> Recebe alerta
   └─> Solicita diagnóstico ao SRE Agent
   └─> Usa LLM para analisar sintomas
   └─> Cria resultado de diagnóstico

3. Planejamento de Remediação (Self-Healing Agent)
   └─> Usa LLM para planejar ações
   └─> Verifica runbooks disponíveis
   └─> Determina nível de risco

4. Execução (DevOps Agent + Self-Healing Agent)
   └─> Claim da operação
   └─> Executa remediação
   └─> Documenta resultado
   └─> Atualiza base RAG
```

### Sistema de Snapshots

Snapshots capturam:

- **Snapshots de Métricas**: CPU, memória, contagem de pods
- **Snapshots de Erros**: Eventos de crash, falhas
- **Snapshots de Logs**: Padrões de erro em logs
- **Snapshots de Estado**: Estado do sistema em um ponto no tempo

---

## Referência da API

### Tipos de Mensagem

#### Mensagem de Alerta
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

#### Solicitação de Diagnóstico
```json
{
  "message_type": "diagnose_request",
  "payload": {
    "target": "nome-do-pod",
    "type": "pod"
  }
}
```

#### Solicitação de Scale
```json
{
  "message_type": "scale_request",
  "payload": {
    "target": "nome-do-deployment",
    "replicas": 3
  }
}
```

---

## Métricas

O sistema rastreia:

- **MTTD** (Mean Time to Detect)
- **MTTR** (Mean Time to Remediate)
- **Precisão/Recall de Alertas**
- **Utilização de Agentes**
- **Taxa de Sucesso de Ações**

---

## Troubleshooting

### Agente Não Inicia

```bash
# Verificar logs do agente
kubectl logs -n spot-render-ai-agents <agent-pod>

# Verificar eventos
kubectl get events -n spot-render-ai-agents

# Verificar ConfigMaps
kubectl describe configmap agent-config -n spot-render-ai-agents
```

### Problemas de Conexão com Ollama

```bash
# Testar conectividade com Ollama
kubectl exec -n spot-render-ai-agents deploy/self-healing-agent -- \
  curl -s http://ollama:11434/api/tags

# Verificar serviço Ollama
kubectl get svc -n spot-render | grep ollama
```

---

## Contribuindo

1. Fork o repositório
2. Crie uma branch de feature
3. Faça suas alterações
4. Execute testes: `pytest tests/`
5. Envie um PR

---

## Licença

MIT License - Ver arquivo LICENSE para detalhes.
