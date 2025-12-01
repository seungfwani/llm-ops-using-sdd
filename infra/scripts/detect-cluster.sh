#!/bin/bash
# Kubernetes 클러스터 타입 감지 스크립트
# Usage: source detect-cluster.sh

detect_cluster_type() {
    # Check if running in minikube
    if command -v minikube &> /dev/null && minikube status &> /dev/null; then
        CLUSTER_TYPE="minikube"
        CLUSTER_NAME="minikube"
        return 0
    fi
    
    # Check kubectl context for common patterns
    if command -v kubectl &> /dev/null; then
        CONTEXT=$(kubectl config current-context 2>/dev/null || echo "")
        
        if [[ "${CONTEXT}" == *"minikube"* ]]; then
            CLUSTER_TYPE="minikube"
            CLUSTER_NAME="minikube"
            return 0
        fi
        
        # Check for common production cluster indicators
        if [[ "${CONTEXT}" == *"gke"* ]] || \
           [[ "${CONTEXT}" == *"eks"* ]] || \
           [[ "${CONTEXT}" == *"aks"* ]] || \
           [[ "${CONTEXT}" == *"production"* ]] || \
           [[ "${CONTEXT}" == *"prod"* ]]; then
            CLUSTER_TYPE="production"
            CLUSTER_NAME="${CONTEXT}"
            return 0
        fi
        
        # Default to generic k8s
        CLUSTER_TYPE="kubernetes"
        CLUSTER_NAME="${CONTEXT:-unknown}"
        return 0
    fi
    
    CLUSTER_TYPE="unknown"
    CLUSTER_NAME="unknown"
    return 1
}

# Auto-detect if sourced
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    detect_cluster_type
    export CLUSTER_TYPE
    export CLUSTER_NAME
fi

