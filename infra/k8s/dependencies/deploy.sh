#!/bin/bash
# LLM Ops 의존성 서비스 배포 스크립트
# PostgreSQL, Redis, MinIO를 llm-ops 네임스페이스에 배포합니다.
# minikube와 프로덕션 Kubernetes 클러스터 모두 지원합니다.

set -e

# Get namespace from environment variable or use default
NAMESPACE="${DEPENDENCIES_NAMESPACE:-llm-ops-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect cluster type
source "${SCRIPT_DIR}/../../scripts/detect-cluster.sh" 2>/dev/null || {
    # Fallback detection
    if command -v minikube &> /dev/null && minikube status &> /dev/null 2>&1; then
        CLUSTER_TYPE="minikube"
    else
        CLUSTER_TYPE="kubernetes"
    fi
}

echo "🚀 Deploying dependencies to namespace: ${NAMESPACE}"
echo "   Cluster type: ${CLUSTER_TYPE}"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Check if cluster is accessible
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    if [ "${CLUSTER_TYPE}" = "minikube" ]; then
        echo "   💡 For minikube, try: minikube start"
    fi
    exit 1
fi

# Create namespace if it doesn't exist
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "📦 Creating namespace: ${NAMESPACE}"
    kubectl create namespace "${NAMESPACE}"
    kubectl label namespace "${NAMESPACE}" \
        managed-by="llm-ops-platform" \
        --overwrite
fi

# Apply all manifests with namespace override
echo "📦 Applying Kubernetes manifests..."
# Use kustomize to generate manifests, then replace namespace and apply
# The sed replacement handles all namespace occurrences in metadata
echo "   Generating manifests with kustomize..."
if ! kubectl kustomize . > /tmp/k8s-manifests.yaml 2>&1; then
    echo "❌ Failed to generate manifests with kustomize"
    cat /tmp/k8s-manifests.yaml
    exit 1
fi

echo "   Replacing namespace and applying manifests..."
if ! sed "s/namespace: llm-ops-dev/namespace: ${NAMESPACE}/g" /tmp/k8s-manifests.yaml | kubectl apply -f -; then
    echo "❌ Failed to apply Kubernetes manifests"
    exit 1
fi
rm -f /tmp/k8s-manifests.yaml

# Wait for deployments to be ready
echo ""
echo "⏳ Waiting for deployments to be ready..."

if kubectl get deployment postgresql -n "${NAMESPACE}" &> /dev/null; then
    echo "   Waiting for PostgreSQL..."
    kubectl wait --for=condition=available --timeout=300s deployment/postgresql -n "${NAMESPACE}" || {
        echo "   ⚠️  Warning: PostgreSQL may not be fully ready"
    }
fi

if kubectl get deployment redis -n "${NAMESPACE}" &> /dev/null; then
    echo "   Waiting for Redis..."
    kubectl wait --for=condition=available --timeout=300s deployment/redis -n "${NAMESPACE}" || {
        echo "   ⚠️  Warning: Redis may not be fully ready"
    }
fi

if kubectl get deployment minio -n "${NAMESPACE}" &> /dev/null; then
    echo "   Waiting for MinIO..."
    kubectl wait --for=condition=available --timeout=300s deployment/minio -n "${NAMESPACE}" || {
        echo "   ⚠️  Warning: MinIO may not be fully ready"
    }
fi

# Get service endpoints
echo ""
echo "✅ Dependencies deployed successfully!"
echo ""
echo "📋 Service endpoints (cluster-internal DNS):"
echo "   PostgreSQL: postgresql.${NAMESPACE}.svc.cluster.local:5432"
echo "   Redis: redis.${NAMESPACE}.svc.cluster.local:6379"
echo "   MinIO API: minio.${NAMESPACE}.svc.cluster.local:9000"
echo "   MinIO Console: minio.${NAMESPACE}.svc.cluster.local:9001"
echo ""
echo "🔍 Check status with:"
echo "   kubectl get pods -n ${NAMESPACE}"
echo "   kubectl get svc -n ${NAMESPACE}"
echo ""
# Minikube-specific instructions
if [ "${CLUSTER_TYPE}" = "minikube" ]; then
    echo "🖥️  Minikube detected - Local development mode"
    echo ""
    echo "🌐 To access services from localhost:"
    echo "   Option 1: Use port-forward (recommended for development):"
    echo "      kubectl port-forward -n ${NAMESPACE} svc/minio 9001:9001"
    echo "      Then open: http://localhost:9001"
    echo ""
    echo "   Option 2: Use minikube service (exposes service to host):"
    echo "      minikube service minio -n ${NAMESPACE} --url"
    echo ""
    echo "📦 To create models bucket (with port-forward):"
    echo "   # Terminal 1:"
    echo "   kubectl port-forward -n ${NAMESPACE} svc/minio 9000:9000"
    echo "   # Terminal 2:"
    echo "   mc alias set minio http://localhost:9000 llmops llmops-secret"
    echo "   mc mb minio/models"
else
    echo "🌐 To access MinIO console from localhost, use port-forward:"
    echo "   kubectl port-forward -n ${NAMESPACE} svc/minio 9001:9001"
    echo "   Then open: http://localhost:9001"
    echo "   Login: llmops / llmops-secret"
    echo ""
    echo "📦 To create models bucket:"
    echo "   kubectl port-forward -n ${NAMESPACE} svc/minio 9000:9000"
    echo "   mc alias set minio http://localhost:9000 llmops llmops-secret"
    echo "   mc mb minio/models"
    echo ""
    echo "💡 Production tip: In production, use LoadBalancer or Ingress for external access"
fi

