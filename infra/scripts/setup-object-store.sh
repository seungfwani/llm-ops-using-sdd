#!/bin/bash
# Object Storage 통합 관리 스크립트 (MinIO 포함)
# Usage: 
#   ./setup-object-store.sh [namespace]                    - Secret/ConfigMap 생성 (기본)
#   ./setup-object-store.sh [namespace] create-bucket      - 버킷 생성
#   ./setup-object-store.sh [namespace] setup-all          - Secret/ConfigMap + 버킷 생성
#   ./setup-object-store.sh [namespace] check              - 상태 확인

set -e

NAMESPACE="${1:-llm-ops-dev}"
ACTION="${2:-setup}"
ACCESS_KEY="${3:-llmops}"
SECRET_KEY="${4:-llmops-secret}"
ENDPOINT_URL="${5:-http://minio.${NAMESPACE}.svc.cluster.local:9000}"
BUCKET_NAME="${6:-models}"

# ============================================================================
# Helper Functions
# ============================================================================

# Secret 및 ConfigMap 생성 함수
create_secrets_and_configmap() {
    local namespace="${1}"
    local access_key="${2}"
    local secret_key="${3}"
    local endpoint_url="${4}"
    
    echo "🔐 Setting up Object Storage secrets and config for namespace: ${namespace}"
    echo ""
    
    # Check if namespace exists
    if ! kubectl get namespace "${namespace}" &> /dev/null; then
        echo "❌ Namespace ${namespace} does not exist. Please create it first:"
        echo "   kubectl create namespace ${namespace}"
        return 1
    fi
    
    # Create/Update Secret for object store credentials (minio-secret)
    SECRET_NAME="minio-secret"
    if kubectl get secret "${SECRET_NAME}" -n "${namespace}" &> /dev/null; then
        echo "🔄 Updating existing secret: ${SECRET_NAME}"
        kubectl delete secret "${SECRET_NAME}" -n "${namespace}"
    fi
    
    echo "📦 Creating secret: ${SECRET_NAME}"
    kubectl create secret generic "${SECRET_NAME}" \
        --from-literal=MINIO_ROOT_USER="${access_key}" \
        --from-literal=MINIO_ROOT_PASSWORD="${secret_key}" \
        -n "${namespace}"
    
    # Create ConfigMap for object store endpoint
    CONFIGMAP_NAME="llm-ops-object-store-config"
    if kubectl get configmap "${CONFIGMAP_NAME}" -n "${namespace}" &> /dev/null; then
        echo "🔄 Updating existing configmap: ${CONFIGMAP_NAME}"
        kubectl delete configmap "${CONFIGMAP_NAME}" -n "${namespace}"
    fi
    
    echo "📦 Creating configmap: ${CONFIGMAP_NAME}"
    kubectl create configmap "${CONFIGMAP_NAME}" \
        --from-literal=endpoint-url="${endpoint_url}" \
        -n "${namespace}"
    
    echo ""
    echo "✅ Object storage secrets and config created successfully!"
    echo ""
    echo "📋 Created resources:"
    echo "   Secret: ${SECRET_NAME}"
    echo "   ConfigMap: ${CONFIGMAP_NAME}"
    echo ""
    echo "🔍 Verify with:"
    echo "   kubectl get secret ${SECRET_NAME} -n ${namespace}"
    echo "   kubectl get configmap ${CONFIGMAP_NAME} -n ${namespace}"
}

# MinIO 버킷 생성 함수
create_minio_bucket() {
    local namespace="${1}"
    local bucket_name="${2}"
    local access_key="${3}"
    local secret_key="${4}"
    
    echo "📦 Creating MinIO bucket: ${bucket_name}"
    echo "   Namespace: ${namespace}"
    echo ""
    
    # Check if MinIO deployment exists
    if ! kubectl get deployment minio -n "${namespace}" &> /dev/null; then
        echo "❌ MinIO deployment not found in namespace ${namespace}"
        return 1
    fi
    
    # Wait for MinIO to be ready
    echo "⏳ Waiting for MinIO to be ready..."
    kubectl wait --for=condition=available --timeout=120s deployment/minio -n "${namespace}" || {
        echo "❌ MinIO deployment not ready"
        return 1
    }
    
    sleep 3
    
    # Get MinIO pod name
    MINIO_POD=$(kubectl get pod -n "${namespace}" -l app=minio -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "${MINIO_POD}" ]; then
        echo "❌ Could not find MinIO pod"
        return 1
    fi
    
    echo "📡 Found MinIO pod: ${MINIO_POD}"
    
    # Method 1: Try using Python with boto3 (if available in pod)
    echo "🔄 Attempting to create bucket using Python/boto3..."
    if kubectl exec -n "${namespace}" "${MINIO_POD}" -- sh -c "
        python3 -c \"
import sys
try:
    import boto3
    from botocore.client import Config
    
    s3 = boto3.client(
        's3',
        endpoint_url='http://localhost:9000',
        aws_access_key_id='${access_key}',
        aws_secret_access_key='${secret_key}',
        config=Config(signature_version='s3v4')
    )
    s3.create_bucket(Bucket='${bucket_name}')
    print('SUCCESS')
except ImportError:
    print('NO_BOTO3')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
\" 2>&1
    " 2>/dev/null | grep -q "SUCCESS"; then
        echo "   ✅ Bucket '${bucket_name}' created successfully using Python/boto3"
        return 0
    fi
    
    # Method 2: Try using curl with MinIO API (most reliable)
    echo "🔄 Attempting to create bucket using MinIO API..."
    
    # Try with curl (if available)
    if kubectl exec -n "${namespace}" "${MINIO_POD}" -- sh -c "command -v curl >/dev/null 2>&1" 2>/dev/null; then
        if kubectl exec -n "${namespace}" "${MINIO_POD}" -- sh -c "
            curl -X PUT \"http://localhost:9000/${bucket_name}\" \
                --user \"${access_key}:${secret_key}\" \
                -f -s -o /dev/null 2>&1 && echo 'SUCCESS'
        " 2>/dev/null | grep -q "SUCCESS"; then
            echo "   ✅ Bucket '${bucket_name}' created successfully using MinIO API (curl)"
            return 0
        fi
    fi
    
    # Try installing curl and using it (Alpine-based images)
    if kubectl exec -n "${namespace}" "${MINIO_POD}" -- sh -c "
        apk add --no-cache curl >/dev/null 2>&1 && \
        curl -X PUT \"http://localhost:9000/${bucket_name}\" \
            --user \"${access_key}:${secret_key}\" \
            -f -s -o /dev/null 2>&1 && echo 'SUCCESS'
    " 2>/dev/null | grep -q "SUCCESS"; then
        echo "   ✅ Bucket '${bucket_name}' created successfully using MinIO API (curl installed)"
        return 0
    fi
    
    # Method 3: Use local mc client with port-forward
    echo "🔄 Attempting to create bucket using local mc client..."
    if command -v mc &> /dev/null; then
        echo "   Setting up port-forward..."
        # Start port-forward in background
        kubectl port-forward -n "${namespace}" svc/minio 9000:9000 >/dev/null 2>&1 &
        PF_PID=$!
        sleep 3
        
        # Create bucket
        if mc alias set minio-temp http://localhost:9000 "${access_key}" "${secret_key}" >/dev/null 2>&1 && \
           mc mb "minio-temp/${bucket_name}" >/dev/null 2>&1; then
            echo "   ✅ Bucket '${bucket_name}' created successfully using mc client"
            kill $PF_PID 2>/dev/null || true
            return 0
        else
            kill $PF_PID 2>/dev/null || true
        fi
    fi
    
    # If all methods failed, provide manual instructions
    echo ""
    echo "⚠️  Could not create bucket automatically"
    echo ""
    echo "💡 Please create the bucket manually using one of these methods:"
    echo ""
    echo "Method 1: Using MinIO Console (Recommended)"
    echo "   1. kubectl port-forward -n ${namespace} svc/minio 9001:9001"
    echo "   2. Open http://localhost:9001 in browser"
    echo "   3. Login with: ${access_key} / ${secret_key}"
    echo "   4. Create bucket '${bucket_name}' via UI"
    echo ""
    echo "Method 2: Using mc client"
    echo "   1. kubectl port-forward -n ${namespace} svc/minio 9000:9000"
    echo "   2. In another terminal:"
    echo "      mc alias set minio http://localhost:9000 ${access_key} ${secret_key}"
    echo "      mc mb minio/${bucket_name}"
    echo ""
    echo "Method 3: Using kubectl exec with Python"
    echo "   kubectl exec -n ${namespace} ${MINIO_POD} -- python3 -c \\"
    echo "     \"import boto3; from botocore.client import Config; \\"
    echo "      s3 = boto3.client('s3', endpoint_url='http://localhost:9000', \\"
    echo "                        aws_access_key_id='${access_key}', \\"
    echo "                        aws_secret_access_key='${secret_key}', \\"
    echo "                        config=Config(signature_version='s3v4')); \\"
    echo "      s3.create_bucket(Bucket='${bucket_name}')\""
    
    return 1
}

# 상태 확인 함수
check_object_store_status() {
    local namespace="${1}"
    
    echo "🔍 Checking Object Storage status..."
    echo "   Namespace: ${namespace}"
    echo ""
    
    # Check namespace
    if ! kubectl get namespace "${namespace}" &> /dev/null; then
        echo "❌ Namespace ${namespace} does not exist"
        return 1
    fi
    
    # Check Secret
    echo "📋 Checking Secret..."
    if kubectl get secret minio-secret -n "${namespace}" &> /dev/null; then
        echo "   ✅ Object store credentials secret (minio-secret) exists"
    else
        echo "   ❌ Object store credentials secret (minio-secret) not found"
        echo "   Run: ./setup-object-store.sh ${namespace} setup"
    fi
    
    # Check ConfigMap
    echo ""
    echo "📋 Checking ConfigMap..."
    if kubectl get configmap llm-ops-object-store-config -n "${namespace}" &> /dev/null; then
        ENDPOINT=$(kubectl get configmap llm-ops-object-store-config -n "${namespace}" -o jsonpath='{.data.endpoint-url}' 2>/dev/null || echo "")
        echo "   ✅ Object store config exists"
        if [ -n "${ENDPOINT}" ]; then
            echo "   Endpoint: ${ENDPOINT}"
        fi
    else
        echo "   ❌ Object store config not found"
        echo "   Run: ./setup-object-store.sh ${namespace} setup"
    fi
    
    # Check MinIO deployment
    echo ""
    echo "📦 Checking MinIO..."
    if kubectl get deployment minio -n "${namespace}" &> /dev/null; then
        MINIO_STATUS=$(kubectl get deployment minio -n "${namespace}" -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "Unknown")
        if [ "${MINIO_STATUS}" = "True" ]; then
            echo "   ✅ MinIO deployment is available"
        else
            echo "   ⚠️  MinIO deployment exists but may not be ready"
        fi
        
        # Check MinIO service
        if kubectl get svc minio -n "${namespace}" &> /dev/null; then
            echo "   ✅ MinIO service exists"
        fi
    else
        echo "   ⚠️  MinIO deployment not found"
    fi
    
    echo ""
    echo "✅ Object Storage status check complete"
}

# ============================================================================
# Main Actions
# ============================================================================

case "${ACTION}" in
    setup)
        create_secrets_and_configmap "${NAMESPACE}" "${ACCESS_KEY}" "${SECRET_KEY}" "${ENDPOINT_URL}"
        ;;
        
    create-bucket)
        create_minio_bucket "${NAMESPACE}" "${BUCKET_NAME}" "${ACCESS_KEY}" "${SECRET_KEY}"
        ;;
        
    setup-all)
        echo "🚀 Setting up Object Storage (Secrets + Bucket)..."
        echo "   Namespace: ${NAMESPACE}"
        echo "   Bucket: ${BUCKET_NAME}"
        echo ""
        
        create_secrets_and_configmap "${NAMESPACE}" "${ACCESS_KEY}" "${SECRET_KEY}" "${ENDPOINT_URL}"
        echo ""
        create_minio_bucket "${NAMESPACE}" "${BUCKET_NAME}" "${ACCESS_KEY}" "${SECRET_KEY}"
        ;;
        
    check)
        check_object_store_status "${NAMESPACE}"
        ;;
        
    *)
        echo "❌ Unknown action: ${ACTION}"
        echo ""
        echo "Usage:"
        echo "   ./setup-object-store.sh [namespace]                    - Secret/ConfigMap 생성 (기본)"
        echo "   ./setup-object-store.sh [namespace] create-bucket      - 버킷 생성"
        echo "   ./setup-object-store.sh [namespace] setup-all         - Secret/ConfigMap + 버킷 생성"
        echo "   ./setup-object-store.sh [namespace] check              - 상태 확인"
        echo ""
        echo "Parameters (for setup/create-bucket):"
        echo "   [namespace]     - Kubernetes namespace (default: llm-ops-dev)"
        echo "   [access-key]    - MinIO access key (default: llmops)"
        echo "   [secret-key]    - MinIO secret key (default: llmops-secret)"
        echo "   [endpoint-url]  - Object store endpoint (default: http://minio.<namespace>.svc.cluster.local:9000)"
        echo "   [bucket-name]   - Bucket name (default: models)"
        exit 1
        ;;
esac

