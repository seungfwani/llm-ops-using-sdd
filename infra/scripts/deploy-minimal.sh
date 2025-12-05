#!/bin/bash
# LLM Ops Platform 최소 사양 배포 스크립트
# 최소 사양(CPU-only 모드)으로 개발 환경을 구성합니다.
# Usage: ./deploy-minimal.sh [environment]

set -e

ENVIRONMENT="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="llm-ops-${ENVIRONMENT}"

# 최소 사양 설정
MINIKUBE_MEMORY="${MINIKUBE_MEMORY:-8192}"  # 8GB
MINIKUBE_CPUS="${MINIKUBE_CPUS:-4}"
MINIKUBE_DISK_SIZE="${MINIKUBE_DISK_SIZE:-30g}"

echo "🚀 LLM Ops Platform 최소 사양 배포"
echo "   Environment: ${ENVIRONMENT}"
echo "   Namespace: ${NAMESPACE}"
echo "   Mode: CPU-only (최소 사양)"
echo ""

# ============================================================================
# Prerequisites Check
# ============================================================================
echo "🔍 Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl is not installed. Please install kubectl first."
    exit 1
fi

if ! command -v minikube &> /dev/null; then
    echo "❌ minikube is not installed. Please install minikube first."
    echo "   💡 macOS: brew install minikube"
    echo "   💡 Linux: https://minikube.sigs.k8s.io/docs/start/"
    exit 1
fi

echo "   ✅ Prerequisites check passed"
echo ""

# ============================================================================
# Step 1: Start Minikube with Minimum Resources
# ============================================================================
echo "📦 Step 1: Starting Minikube with minimum resources..."

if minikube status &> /dev/null; then
    echo "   ⚠️  Minikube is already running"
    echo "   💡 To restart with minimum resources, run:"
    echo "      minikube stop"
    echo "      minikube start --memory=${MINIKUBE_MEMORY} --cpus=${MINIKUBE_CPUS} --disk-size=${MINIKUBE_DISK_SIZE} --driver=docker"
    read -p "   Continue with existing Minikube? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Stopping Minikube..."
        minikube stop
        echo "   Starting Minikube with minimum resources..."
        minikube start \
            --memory="${MINIKUBE_MEMORY}" \
            --cpus="${MINIKUBE_CPUS}" \
            --disk-size="${MINIKUBE_DISK_SIZE}" \
            --driver=docker
    fi
else
    echo "   Starting Minikube with minimum resources..."
    echo "   Memory: ${MINIKUBE_MEMORY}MB"
    echo "   CPUs: ${MINIKUBE_CPUS}"
    echo "   Disk: ${MINIKUBE_DISK_SIZE}"
    minikube start \
        --memory="${MINIKUBE_MEMORY}" \
        --cpus="${MINIKUBE_CPUS}" \
        --disk-size="${MINIKUBE_DISK_SIZE}" \
        --driver=docker
fi

# Wait for Minikube to be ready
echo "   Waiting for Minikube to be ready..."
minikube status

if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi

echo "   ✅ Minikube is ready"
echo ""

# ============================================================================
# Step 2: Create Namespace
# ============================================================================
echo "📦 Step 2: Creating namespace..."

if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "   ✅ Namespace ${NAMESPACE} already exists"
else
    echo "   Creating namespace: ${NAMESPACE}"
    kubectl create namespace "${NAMESPACE}"
    
    # Add labels
    kubectl label namespace "${NAMESPACE}" \
        environment="${ENVIRONMENT}" \
        managed-by="llm-ops-platform" \
        minimal-resources="true" \
        --overwrite
    
    echo "   ✅ Created ${NAMESPACE}"
fi
echo ""

# ============================================================================
# Step 3: Deploy Dependencies (PostgreSQL, Redis, MinIO) with Minimal Resources
# ============================================================================
echo "📦 Step 3: Deploying dependencies with minimal resources..."
echo "   Note: Services are configured with minimum resource requirements"
echo "   - PostgreSQL: CPU 100m-250m, Memory 128Mi-256Mi, Storage 5Gi"
echo "   - Redis: CPU 100m-200m, Memory 128Mi-256Mi"
echo "   - MinIO: CPU 100m-250m, Memory 256Mi-512Mi, Storage 10Gi"
echo ""

cd "${ROOT_DIR}/infra/k8s/dependencies"

# Create namespace if it doesn't exist (should already exist, but just in case)
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    kubectl create namespace "${NAMESPACE}"
    kubectl label namespace "${NAMESPACE}" \
        managed-by="llm-ops-platform" \
        minimal-resources="true" \
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
# Step 5: Check Resource Usage
# ============================================================================
echo "📊 Step 5: Checking resource usage..."

echo "   Current resource requests:"
kubectl get pods -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources.requests.cpu}{"\t"}{.spec.containers[*].resources.requests.memory}{"\n"}{end}' 2>/dev/null | column -t || echo "   (Resource information not available)"

echo ""
echo "   Total resource requests (approximate):"
TOTAL_CPU=$(kubectl get pods -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.spec.containers[*].resources.requests.cpu}{" "}{end}' 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+m?$' | sed 's/m$//' | awk '{sum+=$1} END {print sum/1000}')
TOTAL_MEMORY=$(kubectl get pods -n "${NAMESPACE}" -o jsonpath='{range .items[*]}{.spec.containers[*].resources.requests.memory}{" "}{end}' 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+Mi?$' | sed 's/Mi$//' | awk '{sum+=$1} END {print sum}')
echo "   CPU: ~${TOTAL_CPU:-0.6} cores"
echo "   Memory: ~${TOTAL_MEMORY:-1000}Mi (~1GB)"
echo ""

# ============================================================================
# Step 6: Setup Port-Forward (Optional)
# ============================================================================
echo "📡 Step 6: Port-forward setup (optional)..."

read -p "   Start port-forward for local development? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo "   Starting port-forward in background..."
    echo "   💡 To stop port-forward, run: pkill -f 'kubectl port-forward'"
    echo ""
    
    # Start port-forwards in background
    kubectl port-forward -n "${NAMESPACE}" svc/postgresql 5432:5432 >/dev/null 2>&1 &
    kubectl port-forward -n "${NAMESPACE}" svc/redis 6379:6379 >/dev/null 2>&1 &
    kubectl port-forward -n "${NAMESPACE}" svc/minio 9000:9000 >/dev/null 2>&1 &
    kubectl port-forward -n "${NAMESPACE}" svc/minio 9001:9001 >/dev/null 2>&1 &
    
    echo "   ✅ Port-forwards started"
    echo "   - PostgreSQL: localhost:5432"
    echo "   - Redis: localhost:6379"
    echo "   - MinIO API: http://localhost:9000"
    echo "   - MinIO Console: http://localhost:9001"
    echo ""
    echo "   💡 To manage port-forwards manually, use:"
    echo "      ${SCRIPT_DIR}/port-forward-all.sh ${ENVIRONMENT}"
else
    echo "   Skipping port-forward setup"
    echo "   💡 To start port-forward later, run:"
    echo "      ${SCRIPT_DIR}/port-forward-all.sh ${ENVIRONMENT}"
fi
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "✅ 최소 사양 배포 완료!"
echo ""
echo "📋 Summary:"
echo "   Environment: ${ENVIRONMENT}"
echo "   Namespace: ${NAMESPACE}"
echo "   Mode: CPU-only (최소 사양)"
echo "   Minikube: Memory ${MINIKUBE_MEMORY}MB, CPUs ${MINIKUBE_CPUS}, Disk ${MINIKUBE_DISK_SIZE}"
echo "   Dependencies: PostgreSQL, Redis, MinIO (최소 리소스)"
echo "   KServe: Not installed (CPU-only mode)"
echo "   Object Storage: Configured"
echo ""
echo "🔍 Check status with:"
echo "   kubectl get pods -n ${NAMESPACE}"
echo "   kubectl get svc -n ${NAMESPACE}"
echo "   kubectl top pods -n ${NAMESPACE}"
echo ""

echo "🖥️  Local Development Setup:"
echo ""
echo "   📡 Services are accessible via port-forward:"
echo "      - PostgreSQL: localhost:5432"
echo "      - Redis: localhost:6379"
echo "      - MinIO API: http://localhost:9000"
echo "      - MinIO Console: http://localhost:9001 (Login: llmops / llmops-secret)"
echo ""
echo "   💡 Backend .env configuration (already set for minimum requirements):"
echo "      DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops"
echo "      REDIS_URL=redis://localhost:6379/0"
echo "      OBJECT_STORE_ENDPOINT=http://localhost:9000"
echo "      OBJECT_STORE_ACCESS_KEY=${ACCESS_KEY}"
echo "      OBJECT_STORE_SECRET_KEY=${SECRET_KEY}"
echo "      USE_GPU=false"
echo "      USE_KSERVE=false"
echo "      SERVING_CPU_ONLY_CPU_REQUEST=500m"
echo "      SERVING_CPU_ONLY_CPU_LIMIT=1"
echo "      SERVING_CPU_ONLY_MEMORY_REQUEST=512Mi"
echo "      SERVING_CPU_ONLY_MEMORY_LIMIT=1Gi"
echo ""
echo "   📝 To configure backend:"
echo "      cd ${ROOT_DIR}/backend"
echo "      cp env.example .env"
echo "      # .env is already configured for minimum requirements"
echo ""

echo "📚 Next steps:"
echo "   1. Configure backend environment:"
echo "      cd ${ROOT_DIR}/backend"
echo "      cp env.example .env"
echo "   2. Run database migrations:"
echo "      cd ${ROOT_DIR}/backend"
echo "      poetry install"
echo "      poetry run alembic upgrade head"
echo "   3. Start backend server:"
echo "      cd ${ROOT_DIR}/backend"
echo "      poetry run uvicorn src.api.main:app --reload --port 8000"
echo "   4. Start frontend (in another terminal):"
echo "      cd ${ROOT_DIR}/frontend"
echo "      npm install"
echo "      npm run dev"
echo ""
echo "📖 For more information, see:"
echo "   - Minimum Requirements: ${ROOT_DIR}/docs/MINIMUM_REQUIREMENTS.md"
echo "   - Environment Setup: ${ROOT_DIR}/backend/ENV_SETUP.md"
echo ""

