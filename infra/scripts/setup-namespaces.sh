#!/bin/bash
# LLM Ops 네임스페이스 생성 스크립트
# Usage: ./setup-namespaces.sh [env1] [env2] ...

set -e

# Default environments
ENVIRONMENTS="${@:-dev stg prod}"

echo "🚀 Creating LLM Ops namespaces"
echo "   Environments: ${ENVIRONMENTS}"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

# Create namespaces for each environment
for env in ${ENVIRONMENTS}; do
    namespace="llm-ops-${env}"
    
    if kubectl get namespace "${namespace}" &> /dev/null; then
        echo "✅ Namespace ${namespace} already exists"
    else
        echo "📦 Creating namespace: ${namespace}"
        kubectl create namespace "${namespace}"
        
        # Add labels
        kubectl label namespace "${namespace}" \
            environment="${env}" \
            managed-by="llm-ops-platform" \
            --overwrite
        
        echo "   ✅ Created ${namespace}"
    fi
done

echo ""
echo "✅ All namespaces created successfully!"
echo ""
echo "📋 Created namespaces:"
for env in ${ENVIRONMENTS}; do
    echo "   - llm-ops-${env}"
done
echo ""
echo "🔍 Check namespaces with:"
echo "   kubectl get namespaces | grep llm-ops"

