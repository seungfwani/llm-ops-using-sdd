#!/bin/bash
# Rollback script for serving endpoints
# Usage: ./serving_rollback.sh <endpoint_id> [namespace]

set -e

ENDPOINT_ID="${1}"
NAMESPACE="${2:-default}"

if [ -z "$ENDPOINT_ID" ]; then
    echo "Error: endpoint_id is required"
    echo "Usage: $0 <endpoint_id> [namespace]"
    exit 1
fi

ENDPOINT_NAME="serving-${ENDPOINT_ID}"

echo "Rolling back serving endpoint: ${ENDPOINT_NAME} in namespace: ${NAMESPACE}"

# Scale down deployment to 0 replicas
kubectl scale deployment "${ENDPOINT_NAME}" --replicas=0 -n "${NAMESPACE}" || {
    echo "Warning: Failed to scale down deployment, continuing..."
}

# Wait for pods to terminate
echo "Waiting for pods to terminate..."
kubectl wait --for=delete pod -l app="${ENDPOINT_NAME}" -n "${NAMESPACE}" --timeout=60s || {
    echo "Warning: Some pods may still be running"
}

# Delete HPA if it exists
kubectl delete hpa "${ENDPOINT_NAME}-hpa" -n "${NAMESPACE}" 2>/dev/null || {
    echo "Info: HPA not found or already deleted"
}

# Delete Ingress if it exists
kubectl delete ingress "${ENDPOINT_NAME}-ingress" -n "${NAMESPACE}" 2>/dev/null || {
    echo "Info: Ingress not found or already deleted"
}

# Delete Service if it exists
kubectl delete service "${ENDPOINT_NAME}-svc" -n "${NAMESPACE}" 2>/dev/null || {
    echo "Info: Service not found or already deleted"
}

# Delete Deployment
kubectl delete deployment "${ENDPOINT_NAME}" -n "${NAMESPACE}" || {
    echo "Error: Failed to delete deployment"
    exit 1
}

echo "Rollback completed for endpoint: ${ENDPOINT_NAME}"

# Optionally, restore from previous revision if rollback plan exists
# This would require storing previous deployment manifests
# kubectl apply -f "${ROLLBACK_PLAN_PATH}" -n "${NAMESPACE}"

