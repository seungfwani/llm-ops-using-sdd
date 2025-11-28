#!/bin/bash

set -e

echo "🚀 Deploying dependencies to minikube namespace: llm-ops"

# Check if minikube is running
if ! minikube status > /dev/null 2>&1; then
    echo "❌ Minikube is not running. Please start minikube first:"
    echo "   minikube start"
    exit 1
fi

# Apply all manifests
echo "📦 Applying Kubernetes manifests..."
kubectl apply -k .

# Wait for deployments to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/postgresql -n llm-ops

echo "⏳ Waiting for Redis to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/redis -n llm-ops

echo "⏳ Waiting for MinIO to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/minio -n llm-ops

# Get service endpoints
echo ""
echo "✅ Dependencies deployed successfully!"
echo ""
echo "📋 Service endpoints:"
echo "   PostgreSQL: postgresql.llm-ops.svc.cluster.local:5432"
echo "   Redis: redis.llm-ops.svc.cluster.local:6379"
echo "   MinIO API: minio.llm-ops.svc.cluster.local:9000"
echo "   MinIO Console: minio.llm-ops.svc.cluster.local:9001"
echo ""
echo "🔍 Check status with:"
echo "   kubectl get pods -n llm-ops"
echo "   kubectl get svc -n llm-ops"
echo ""
echo "🌐 To access MinIO console from localhost, use port-forward:"
echo "   kubectl port-forward -n llm-ops svc/minio 9001:9001"
echo "   Then open: http://localhost:9001"
echo "   Login: llmops / llmops-secret"

