#!/bin/bash
# LLM Ops Platform 전체 초기 세팅 및 배포 스크립트
# minikube(로컬 개발)와 프로덕션 Kubernetes 클러스터 모두 지원합니다.
# Usage: ./deploy-all.sh [environment] [--cluster-type minikube|kubernetes]

set -e

ENVIRONMENT="${1:-dev}"
CLUSTER_TYPE_ARG="${2}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="llm-ops-${ENVIRONMENT}"

# Detect cluster type
source "${SCRIPT_DIR}/detect-cluster.sh" 2>/dev/null || {
    # Fallback detection
    if command -v minikube &> /dev/null && minikube status &> /dev/null 2>&1; then
        CLUSTER_TYPE="minikube"
    else
        CLUSTER_TYPE="kubernetes"
    fi
}

# Override with argument if provided
if [ "${CLUSTER_TYPE_ARG}" = "--cluster-type" ] && [ -n "${3}" ]; then
    CLUSTER_TYPE="${3}"
fi

echo "🚀 LLM Ops Platform 초기 세팅 및 배포"
echo "   Environment: ${ENVIRONMENT}"
echo "   Cluster type: ${CLUSTER_TYPE}"
echo "   Namespace: ${NAMESPACE}"
echo ""

# ============================================================================
# Prerequisites Check
# ============================================================================
echo "🔍 Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig."
    if [ "${CLUSTER_TYPE}" = "minikube" ]; then
        echo "   💡 For minikube, try: minikube start"
    fi
    exit 1
fi

echo "   ✅ Prerequisites check passed"
echo ""

# ============================================================================
# Step 1: Create Namespace
# ============================================================================
echo "📦 Step 1: Creating namespace..."

if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "   ✅ Namespace ${NAMESPACE} already exists"
else
    echo "   Creating namespace: ${NAMESPACE}"
    kubectl create namespace "${NAMESPACE}"
    
    # Add labels
    kubectl label namespace "${NAMESPACE}" \
        environment="${ENVIRONMENT}" \
        managed-by="llm-ops-platform" \
        --overwrite
    
    echo "   ✅ Created ${NAMESPACE}"
fi
echo ""

# ============================================================================
# Step 2: Install KServe
# ============================================================================
echo "📦 Step 2: Checking KServe installation..."

KSERVE_NAMESPACE="kserve"
KSERVE_VERSION="${KSERVE_VERSION:-v0.11.0}"

if ! kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
    echo "   KServe not found, installing..."
    
    # Create KServe namespace if it doesn't exist
    if ! kubectl get namespace "${KSERVE_NAMESPACE}" &> /dev/null; then
        echo "   Creating namespace: ${KSERVE_NAMESPACE}"
        kubectl create namespace "${KSERVE_NAMESPACE}"
    fi
    
    # Install KServe
    echo "   Installing KServe ${KSERVE_VERSION}..."
    
    # KServe 설치 (cert-manager 에러는 무시 - cert-manager는 선택적)
    # kubectl apply는 일부 리소스가 실패해도 다른 리소스는 성공할 수 있음
    set +e  # 일시적으로 에러 중단 비활성화
    KSERVE_OUTPUT=$(kubectl apply -f "https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml" 2>&1)
    KSERVE_EXIT_CODE=$?
    set -e  # 에러 중단 다시 활성화
    
    # cert-manager 관련 에러 확인 및 처리
    if echo "${KSERVE_OUTPUT}" | grep -q "cert-manager.io/v1"; then
        echo "   ⚠️  Warning: cert-manager not found"
        echo "   📦 Attempting to install cert-manager or create self-signed certificate..."
        
        # cert-manager 설치 시도
        CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.13.0}"
        set +e
        kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml" 2>&1 | head -10 > /dev/null
        CERT_MANAGER_EXIT=$?
        set -e
        
        if [ $CERT_MANAGER_EXIT -eq 0 ]; then
            # cert-manager가 준비될 때까지 대기
            echo "   ⏳ Waiting for cert-manager to be ready..."
            set +e
            kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager \
                -n cert-manager --timeout=120s 2>&1 > /dev/null
            CERT_MANAGER_READY=$?
            set -e
            
            if [ $CERT_MANAGER_READY -eq 0 ]; then
                # KServe 재적용하여 cert-manager가 certificate 생성하도록 함
                echo "   🔄 Re-applying KServe to trigger certificate creation..."
                kubectl apply -f "https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml" 2>&1 | grep -v "cert-manager.io/v1" > /dev/null || true
                
                # Certificate가 생성될 때까지 대기
                sleep 10
                CERT_CREATED=false
                for i in {1..12}; do
                    if kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" &> /dev/null; then
                        CERT_CREATED=true
                        break
                    fi
                    sleep 5
                done
                
                if [ "$CERT_CREATED" = "false" ]; then
                    echo "   ⚠️  Certificate not created by cert-manager, creating self-signed certificate..."
                    "${SCRIPT_DIR}/setup-kserve.sh" "${KSERVE_NAMESPACE}" fix-cert || {
                        echo "   ⚠️  Failed to create certificate, but continuing..."
                    }
                fi
            else
                echo "   ⚠️  cert-manager not ready, creating self-signed certificate..."
                "${SCRIPT_DIR}/setup-kserve.sh" "${KSERVE_NAMESPACE}" fix-cert || {
                    echo "   ⚠️  Failed to create certificate, but continuing..."
                }
            fi
        else
            echo "   ⚠️  Failed to install cert-manager, creating self-signed certificate..."
            "${SCRIPT_DIR}/setup-kserve.sh" "${KSERVE_NAMESPACE}" fix-cert || {
                echo "   ⚠️  Failed to create certificate, but continuing..."
            }
        fi
    fi
    
    # Certificate secret 확인
    if ! kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" &> /dev/null; then
        echo "   ⚠️  Certificate secret not found, creating self-signed certificate..."
        "${SCRIPT_DIR}/setup-kserve.sh" "${KSERVE_NAMESPACE}" fix-cert || {
            echo "   ⚠️  Failed to create certificate, but continuing..."
        }
    fi
    
    # KServe 핵심 리소스가 생성되었는지 확인
    if kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
        echo "   ✅ KServe CRDs installed"
    else
        echo "   ❌ Failed to install KServe CRDs"
        echo "   Error output: ${KSERVE_OUTPUT}"
        exit 1
    fi
    
    # Wait for KServe to be ready
    echo "   Waiting for KServe controller to be ready..."
    kubectl wait --for=condition=ready pod -l control-plane=kserve-controller-manager \
        -n "${KSERVE_NAMESPACE}" --timeout=300s || {
        echo "   ⚠️  Warning: KServe controller may not be fully ready yet"
    }
    
    echo "   ✅ KServe installed"
else
    echo "   ✅ KServe is already installed"
fi
echo ""

# ============================================================================
# Step 3: Deploy Dependencies (PostgreSQL, Redis, MinIO)
# ============================================================================
echo "📦 Step 3: Deploying dependencies (PostgreSQL, Redis, MinIO)..."

cd "${ROOT_DIR}/infra/k8s/dependencies"

# Create namespace if it doesn't exist (should already exist, but just in case)
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    kubectl create namespace "${NAMESPACE}"
    kubectl label namespace "${NAMESPACE}" \
        managed-by="llm-ops-platform" \
        --overwrite
fi

# Apply all manifests with namespace override
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
echo "   Waiting for deployments to be ready..."

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

echo "   ✅ Dependencies deployed"
echo ""

# ============================================================================
# Step 4: Setup Object Storage Secrets and Bucket
# ============================================================================
echo "📦 Step 4: Setting up object storage (secrets + bucket)..."

ACCESS_KEY="${OBJECT_STORE_ACCESS_KEY:-llmops}"
SECRET_KEY="${OBJECT_STORE_SECRET_KEY:-llmops-secret}"
ENDPOINT_URL="${OBJECT_STORE_ENDPOINT:-http://minio.${NAMESPACE}.svc.cluster.local:9000}"
BUCKET_NAME="${MINIO_BUCKET_NAME:-models}"

"${SCRIPT_DIR}/setup-object-store.sh" "${NAMESPACE}" setup-all "${ACCESS_KEY}" "${SECRET_KEY}" "${ENDPOINT_URL}" "${BUCKET_NAME}" || {
    echo "   ⚠️  Object storage setup had issues, but deployment continues"
    echo "   💡 You can retry later using:"
    echo "      ${SCRIPT_DIR}/setup-object-store.sh ${NAMESPACE} setup-all"
}
echo ""


# ============================================================================
# Summary
# ============================================================================
echo "✅ 초기 세팅 및 배포 완료!"
echo ""
echo "📋 Summary:"
echo "   Environment: ${ENVIRONMENT}"
echo "   Cluster type: ${CLUSTER_TYPE}"
echo "   Namespace: ${NAMESPACE}"
echo "   Dependencies: PostgreSQL, Redis, MinIO"
echo "   KServe: Installed"
echo "   Object Storage: Configured"
echo ""
echo "🔍 Check status with:"
echo "   kubectl get pods -n ${NAMESPACE}"
echo "   kubectl get svc -n ${NAMESPACE}"
echo "   kubectl get inferenceservices -n ${NAMESPACE}"
echo ""

# Minikube-specific instructions
if [ "${CLUSTER_TYPE}" = "minikube" ]; then
    echo "🖥️  Minikube (Local Development) Mode:"
    echo ""
    echo "   📡 To access services from your local machine:"
    echo "      kubectl port-forward -n ${NAMESPACE} svc/postgresql 5432:5432"
    echo "      kubectl port-forward -n ${NAMESPACE} svc/redis 6379:6379"
    echo "      kubectl port-forward -n ${NAMESPACE} svc/minio 9000:9000"
    echo "      kubectl port-forward -n ${NAMESPACE} svc/minio 9001:9001"
    echo ""
    echo "   💡 Backend .env for local development:"
    echo "      DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops"
    echo "      REDIS_URL=redis://localhost:6379/0"
    echo "      OBJECT_STORE_ENDPOINT=http://localhost:9000"
    echo "      OBJECT_STORE_ACCESS_KEY=${ACCESS_KEY}"
    echo "      OBJECT_STORE_SECRET_KEY=${SECRET_KEY}"
else
    echo "☁️  Production Kubernetes Mode:"
    echo ""
    echo "   📡 Services are accessible via:"
    echo "      - Cluster-internal: Use service DNS names"
    echo "      - External: Configure LoadBalancer or Ingress"
    echo ""
    echo "   💡 Backend .env for cluster deployment:"
    echo "      DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.${NAMESPACE}.svc.cluster.local:5432/llmops"
    echo "      REDIS_URL=redis://redis.${NAMESPACE}.svc.cluster.local:6379/0"
    echo "      OBJECT_STORE_ENDPOINT=${ENDPOINT_URL}"
    echo "      OBJECT_STORE_ACCESS_KEY=${ACCESS_KEY}"
    echo "      OBJECT_STORE_SECRET_KEY=${SECRET_KEY}"
fi

echo ""
echo "📚 Next steps:"
echo "   1. Run database migrations:"
echo "      cd backend && alembic upgrade head"
echo "   2. Start backend server:"
echo "      cd backend && python -m src.api.app"
echo "   3. Deploy a model via API or UI"
echo ""
