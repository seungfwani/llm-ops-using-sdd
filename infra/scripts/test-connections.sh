#!/bin/bash
# 의존성 서비스 연결 테스트 스크립트
# Usage: ./test-connections.sh [environment]

set -e

ENVIRONMENT="${1:-dev}"
NAMESPACE="llm-ops-${ENVIRONMENT}"

echo "🔍 Testing connections to dependencies in namespace: ${NAMESPACE}"
echo ""

# Check if namespace exists
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "❌ Namespace ${NAMESPACE} does not exist"
    exit 1
fi

# Test PostgreSQL
echo "📊 Testing PostgreSQL connection..."
if kubectl exec -n "${NAMESPACE}" deployment/postgresql -- psql -U llmops -d llmops -c "SELECT version();" &> /dev/null; then
    echo "   ✅ PostgreSQL: Connected successfully"
    kubectl exec -n "${NAMESPACE}" deployment/postgresql -- psql -U llmops -d llmops -c "SELECT version();" 2>/dev/null | grep -i postgresql | head -1
else
    echo "   ❌ PostgreSQL: Connection failed"
fi

# Test Redis
echo ""
echo "📊 Testing Redis connection..."
if kubectl exec -n "${NAMESPACE}" deployment/redis -- redis-cli ping &> /dev/null; then
    RESPONSE=$(kubectl exec -n "${NAMESPACE}" deployment/redis -- redis-cli ping 2>/dev/null)
    if [ "${RESPONSE}" = "PONG" ]; then
        echo "   ✅ Redis: Connected successfully (${RESPONSE})"
    else
        echo "   ❌ Redis: Unexpected response: ${RESPONSE}"
    fi
else
    echo "   ❌ Redis: Connection failed"
fi

# Test MinIO
echo ""
echo "📊 Testing MinIO connection..."
if kubectl exec -n "${NAMESPACE}" deployment/minio -- mc --version &> /dev/null; then
    echo "   ✅ MinIO: Container is running"
    # Test MinIO API endpoint
    if kubectl exec -n "${NAMESPACE}" deployment/minio -- wget -q -O- http://localhost:9000/minio/health/live &> /dev/null; then
        echo "   ✅ MinIO API: Health check passed"
    else
        echo "   ⚠️  MinIO API: Health check failed (may still be starting)"
    fi
else
    echo "   ❌ MinIO: Container not accessible"
fi

# Test Service DNS resolution
echo ""
echo "📊 Testing Service DNS resolution..."
echo "   Testing from within cluster..."

# Create a test pod to check DNS
TEST_POD="connection-test-$(date +%s)"
kubectl run "${TEST_POD}" \
    --image=busybox:latest \
    --rm -i --restart=Never \
    -n "${NAMESPACE}" \
    -- sh -c "
        echo 'Testing PostgreSQL DNS...'
        nslookup postgresql.${NAMESPACE}.svc.cluster.local || echo '  ❌ PostgreSQL DNS failed'
        
        echo 'Testing Redis DNS...'
        nslookup redis.${NAMESPACE}.svc.cluster.local || echo '  ❌ Redis DNS failed'
        
        echo 'Testing MinIO DNS...'
        nslookup minio.${NAMESPACE}.svc.cluster.local || echo '  ❌ MinIO DNS failed'
    " 2>&1 | grep -E "(Testing|DNS|postgresql|redis|minio)" || true

echo ""
echo "📋 Service Endpoints:"
echo "   PostgreSQL: postgresql.${NAMESPACE}.svc.cluster.local:5432"
echo "   Redis: redis.${NAMESPACE}.svc.cluster.local:6379"
echo "   MinIO API: minio.${NAMESPACE}.svc.cluster.local:9000"
echo "   MinIO Console: minio.${NAMESPACE}.svc.cluster.local:9001"
echo ""
echo "💡 For local development, use port-forward:"
echo "   kubectl port-forward -n ${NAMESPACE} svc/postgresql 5432:5432"
echo "   kubectl port-forward -n ${NAMESPACE} svc/redis 6379:6379"
echo "   kubectl port-forward -n ${NAMESPACE} svc/minio 9000:9000"

