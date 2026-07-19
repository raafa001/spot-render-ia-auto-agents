#!/bin/bash
# Deploy Spot Render IA Auto Agent to Kubernetes

set -e

NAMESPACE="spot-render-ai-agents"
OLLAMA_NAMESPACE="spot-render"

echo "=== Deploying Spot Render IA Auto Agent ==="

# Check if namespace exists
if ! kubectl get namespace "$NAMESPACE" &>/dev/null; then
    echo "Creating namespace: $NAMESPACE"
    kubectl create namespace "$NAMESPACE"
else
    echo "Namespace $NAMESPACE already exists"
fi

# Check if Ollama is available
if ! kubectl get svc ollama -n "$OLLAMA_NAMESPACE" &>/dev/null; then
    echo "Warning: Ollama service not found in $OLLAMA_NAMESPACE"
    echo "LLM features may not work without Ollama"
fi

# Build Docker image
echo "Building Docker image..."
docker build -t spot-render-ia-agent:latest .

# Load image into kind cluster (if using kind)
if kubectl cluster-info &>/dev/null; then
    echo "Loading image into cluster..."
    docker save spot-render-ia-agent:latest | \
        sudo k3s ctr images import -
fi

# Apply Kubernetes manifests
echo "Applying Kubernetes manifests..."
kubectl apply -k kubernetes/base/

# Wait for agents to be ready
echo "Waiting for agents to start..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=sre-agent -n "$NAMESPACE" --timeout=120s || true
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=devops-agent -n "$NAMESPACE" --timeout=120s || true
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=self-healing-agent -n "$NAMESPACE" --timeout=120s || true

# Show status
echo ""
echo "=== Agent Status ==="
kubectl get pods -n "$NAMESPACE"

echo ""
echo "=== Agent Logs ==="
echo "SRE Agent:"
kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=sre-agent --tail=10 || true
echo ""
echo "DevOps Agent:"
kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=devops-agent --tail=10 || true
echo ""
echo "Self-Healing Agent:"
kubectl logs -n "$NAMESPACE" -l app.kubernetes.io/name=self-healing-agent --tail=10 || true

echo ""
echo "=== Deployment Complete ==="
echo "Access agent logs with: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=<agent-name>"
