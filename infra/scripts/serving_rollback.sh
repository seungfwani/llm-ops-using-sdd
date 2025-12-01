#!/bin/bash
# Rollback script for serving endpoints
# Supports both KServe InferenceService and raw Deployment
# Usage: ./serving_rollback.sh <endpoint_id> [namespace] [--kserve]

set -e

ENDPOINT_ID="${1}"
NAMESPACE="${2:-llm-ops-dev}"
USE_KSERVE="${3}"

if [ -z "$ENDPOINT_ID" ]; then
    echo "Error: endpoint_id is required"
    echo "Usage: $0 <endpoint_id> [namespace] [--kserve]"
    exit 1
fi

ENDPOINT_NAME="serving-${ENDPOINT_ID}"

# Detect if KServe is being used
if [ "${USE_KSERVE}" = "--kserve" ] || \
   kubectl get inferenceservice "${ENDPOINT_NAME}" -n "${NAMESPACE}" &> /dev/null; then
    USE_KSERVE="true"
    echo "🔄 Rolling back KServe InferenceService: ${ENDPOINT_NAME} in namespace: ${NAMESPACE}"
    
    # Scale down InferenceService to 0 replicas
    kubectl patch inferenceservice "${ENDPOINT_NAME}" -n "${NAMESPACE}" \
        --type='merge' \
        -p='{"spec":{"predictor":{"minReplicas":0,"maxReplicas":0}}}' || {
        echo "⚠️  Warning: Failed to scale down InferenceService, trying to delete..."
        kubectl delete inferenceservice "${ENDPOINT_NAME}" -n "${NAMESPACE}" || {
            echo "❌ Error: Failed to rollback InferenceService"
            exit 1
        }
    }
    
    echo "✅ Rollback completed for KServe InferenceService: ${ENDPOINT_NAME}"
else
    echo "🔄 Rolling back Deployment: ${ENDPOINT_NAME} in namespace: ${NAMESPACE}"
    
    # Scale down deployment to 0 replicas
    kubectl scale deployment "${ENDPOINT_NAME}" --replicas=0 -n "${NAMESPACE}" || {
        echo "⚠️  Warning: Failed to scale down deployment, continuing..."
    }
    
    # Wait for pods to terminate
    echo "⏳ Waiting for pods to terminate..."
    kubectl wait --for=delete pod -l app="${ENDPOINT_NAME}" -n "${NAMESPACE}" --timeout=60s || {
        echo "⚠️  Warning: Some pods may still be running"
    }
    
    # Delete HPA if it exists
    kubectl delete hpa "${ENDPOINT_NAME}-hpa" -n "${NAMESPACE}" 2>/dev/null || {
        echo "ℹ️  Info: HPA not found or already deleted"
    }
    
    # Delete Ingress if it exists
    kubectl delete ingress "${ENDPOINT_NAME}-ingress" -n "${NAMESPACE}" 2>/dev/null || {
        echo "ℹ️  Info: Ingress not found or already deleted"
    }
    
    # Delete Service if it exists
    kubectl delete service "${ENDPOINT_NAME}-svc" -n "${NAMESPACE}" 2>/dev/null || {
        echo "ℹ️  Info: Service not found or already deleted"
    }
    
    # Delete Deployment
    kubectl delete deployment "${ENDPOINT_NAME}" -n "${NAMESPACE}" || {
        echo "❌ Error: Failed to delete deployment"
        exit 1
    }
    
    echo "✅ Rollback completed for Deployment: ${ENDPOINT_NAME}"
fi

echo ""
echo "🔍 Verify rollback with:"
echo "   kubectl get pods -n ${NAMESPACE} | grep ${ENDPOINT_NAME}"

