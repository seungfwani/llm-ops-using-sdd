#!/bin/bash
# 리소스 사용량 확인 스크립트
# Usage: ./check-resources.sh [environment]

set -e

ENVIRONMENT="${1:-dev}"
NAMESPACE="llm-ops-${ENVIRONMENT}"

echo "📊 LLM Ops Platform 리소스 사용량 확인"
echo "   Environment: ${ENVIRONMENT}"
echo "   Namespace: ${NAMESPACE}"
echo ""

# Check if namespace exists
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "❌ Namespace ${NAMESPACE} does not exist"
    exit 1
fi

# Check if metrics-server is available
if ! kubectl top nodes &> /dev/null 2>&1; then
    echo "⚠️  Metrics server is not available. Resource usage cannot be displayed."
    echo "   💡 To install metrics-server in Minikube:"
    echo "      minikube addons enable metrics-server"
    echo ""
fi

# Pod status
echo "📦 Pod Status:"
kubectl get pods -n "${NAMESPACE}" -o wide
echo ""

# Resource requests and limits
echo "💾 Resource Requests and Limits:"
echo ""
kubectl get pods -n "${NAMESPACE}" -o custom-columns=NAME:.metadata.name,CPU-REQUEST:.spec.containers[*].resources.requests.cpu,CPU-LIMIT:.spec.containers[*].resources.limits.cpu,MEMORY-REQUEST:.spec.containers[*].resources.requests.memory,MEMORY-LIMIT:.spec.containers[*].resources.limits.memory 2>/dev/null || echo "   (Resource information not available)"
echo ""

# Actual resource usage (if metrics-server is available)
if kubectl top nodes &> /dev/null 2>&1; then
    echo "📈 Actual Resource Usage:"
    echo ""
    echo "   Node Resources:"
    kubectl top nodes
    echo ""
    echo "   Pod Resources:"
    kubectl top pods -n "${NAMESPACE}" 2>/dev/null || echo "   (No resource usage data available)"
    echo ""
fi

# PVC usage
echo "💿 Persistent Volume Claims:"
kubectl get pvc -n "${NAMESPACE}"
echo ""

# Service status
echo "🌐 Services:"
kubectl get svc -n "${NAMESPACE}"
echo ""

# Calculate total resource requests
echo "📊 Total Resource Requests (approximate):"
echo ""

# Get all CPU requests
CPU_REQUESTS=$(kubectl get pods -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.spec.containers[*].resources.requests.cpu}{" "}{end}' 2>/dev/null || echo "")
if [ -n "${CPU_REQUESTS}" ]; then
    TOTAL_CPU_MILLI=0
    for CPU in ${CPU_REQUESTS}; do
        if [[ ${CPU} =~ ^[0-9]+m$ ]]; then
            # Remove 'm' suffix and add
            VALUE=$(echo ${CPU} | sed 's/m$//')
            TOTAL_CPU_MILLI=$((TOTAL_CPU_MILLI + VALUE))
        elif [[ ${CPU} =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            # Convert to milli (multiply by 1000)
            VALUE=$(echo "${CPU} * 1000" | bc 2>/dev/null || echo "${CPU}000")
            TOTAL_CPU_MILLI=$((TOTAL_CPU_MILLI + ${VALUE%.*}))
        fi
    done
    TOTAL_CPU=$(echo "scale=2; ${TOTAL_CPU_MILLI} / 1000" | bc 2>/dev/null || echo "${TOTAL_CPU_MILLI}/1000")
    echo "   CPU: ~${TOTAL_CPU} cores"
else
    echo "   CPU: Unable to calculate"
fi

# Get all memory requests
MEMORY_REQUESTS=$(kubectl get pods -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.spec.containers[*].resources.requests.memory}{" "}{end}' 2>/dev/null || echo "")
if [ -n "${MEMORY_REQUESTS}" ]; then
    TOTAL_MEMORY_MIB=0
    for MEM in ${MEMORY_REQUESTS}; do
        if [[ ${MEM} =~ ^[0-9]+Mi$ ]]; then
            # Remove 'Mi' suffix and add
            VALUE=$(echo ${MEM} | sed 's/Mi$//')
            TOTAL_MEMORY_MIB=$((TOTAL_MEMORY_MIB + VALUE))
        elif [[ ${MEM} =~ ^[0-9]+Gi$ ]]; then
            # Convert Gi to Mi (multiply by 1024)
            VALUE=$(echo ${MEM} | sed 's/Gi$//')
            TOTAL_MEMORY_MIB=$((TOTAL_MEMORY_MIB + VALUE * 1024))
        fi
    done
    TOTAL_MEMORY_GB=$(echo "scale=2; ${TOTAL_MEMORY_MIB} / 1024" | bc 2>/dev/null || echo "${TOTAL_MEMORY_MIB}/1024")
    echo "   Memory: ~${TOTAL_MEMORY_MIB}Mi (~${TOTAL_MEMORY_GB}GB)"
else
    echo "   Memory: Unable to calculate"
fi

# Storage
TOTAL_STORAGE=$(kubectl get pvc -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.status.capacity.storage}{" "}{end}' 2>/dev/null || echo "")
if [ -n "${TOTAL_STORAGE}" ]; then
    echo "   Storage: ${TOTAL_STORAGE}"
else
    echo "   Storage: No PVCs found"
fi

echo ""
echo "💡 Minimum Requirements:"
echo "   CPU: ~0.6 cores"
echo "   Memory: ~1GB"
echo "   Storage: ~15GB (PostgreSQL 5Gi + MinIO 10Gi)"
echo ""

