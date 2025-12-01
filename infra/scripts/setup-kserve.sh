#!/bin/bash
# KServe 통합 관리 스크립트
# Usage: 
#   ./setup-kserve.sh [namespace]                    - 설치 (기본)
#   ./setup-kserve.sh [namespace] check              - 상태 확인
#   ./setup-kserve.sh [namespace] fix-cert           - Certificate 수정
#   ./setup-kserve.sh [namespace] reinstall          - 재설치

set -e

KSERVE_NAMESPACE="${1:-kserve}"
ACTION="${2:-install}"
KSERVE_VERSION="${KSERVE_VERSION:-v0.11.0}"

# ============================================================================
# Helper Functions
# ============================================================================

# Self-signed certificate 생성 함수
create_self_signed_cert() {
    local namespace="${1:-${KSERVE_NAMESPACE}}"
    local force="${2:-false}"
    
    echo "   📝 Creating self-signed certificate for webhook server..."
    
    # openssl이 있는지 확인
    if ! command -v openssl &> /dev/null; then
        echo "   ❌ openssl not found. Please install openssl or cert-manager."
        return 1
    fi
    
    # 기존 secret 확인
    if [ "$force" != "true" ] && kubectl get secret kserve-webhook-server-cert -n "${namespace}" &> /dev/null; then
        echo "   ⚠️  Certificate secret already exists"
        read -p "   Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "   Skipping..."
            return 0
        fi
        echo "   Deleting existing secret..."
        kubectl delete secret kserve-webhook-server-cert -n "${namespace}"
    fi
    
    # 임시 디렉토리 생성
    TEMP_DIR=$(mktemp -d)
    cd "${TEMP_DIR}"
    
    # Self-signed certificate 생성
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
        -subj "/CN=kserve-webhook-server-service.${namespace}.svc" \
        -addext "subjectAltName=DNS:kserve-webhook-server-service.${namespace}.svc,DNS:kserve-webhook-server-service.${namespace}.svc.cluster.local" 2>/dev/null || {
        # openssl 버전에 따라 -addext가 없을 수 있음
        echo "   Using fallback certificate generation (without SAN)..."
        openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
            -subj "/CN=kserve-webhook-server-service.${namespace}.svc"
    }
    
    # Secret 생성
    kubectl create secret tls kserve-webhook-server-cert \
        --cert=cert.pem \
        --key=key.pem \
        -n "${namespace}" --dry-run=client -o yaml | kubectl apply -f -
    
    # 정리
    cd - > /dev/null
    rm -rf "${TEMP_DIR}"
    
    echo "   ✅ Self-signed certificate secret created"
    
    # Pod 재시작
    echo "   🔄 Restarting KServe controller to pick up the new certificate..."
    kubectl delete pod -n "${namespace}" -l control-plane=kserve-controller-manager 2>/dev/null || {
        echo "   ⚠️  Could not restart controller pods (they may not exist yet)"
    }
}

# KServe 상태 확인 함수
check_kserve_status() {
    local namespace="${1:-${KSERVE_NAMESPACE}}"
    
    echo "🔍 Checking KServe installation status..."
    echo "   Namespace: ${namespace}"
    echo ""
    
    # Check namespace
    if ! kubectl get namespace "${namespace}" &> /dev/null; then
        echo "❌ KServe namespace '${namespace}' does not exist"
        echo "   Run: ./setup-kserve.sh ${namespace}"
        return 1
    fi
    
    # Check CRDs
    echo "📋 Checking CRDs..."
    if kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
        echo "   ✅ InferenceService CRD exists"
    else
        echo "   ❌ InferenceService CRD not found"
        echo "   Run: ./setup-kserve.sh ${namespace}"
        return 1
    fi
    
    # Check pods
    echo ""
    echo "📦 Checking Pods..."
    PODS=$(kubectl get pods -n "${namespace}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    if [ -z "$PODS" ]; then
        echo "   ❌ No pods found in ${namespace} namespace"
        return 1
    fi
    
    for pod in $PODS; do
        STATUS=$(kubectl get pod -n "${namespace}" "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
        READY=$(kubectl get pod -n "${namespace}" "$pod" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null || echo "false")
        RESTARTS=$(kubectl get pod -n "${namespace}" "$pod" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")
        
        if [ "$STATUS" = "Running" ] && [ "$READY" = "true" ]; then
            echo "   ✅ $pod: Running (restarts: $RESTARTS)"
        else
            echo "   ⚠️  $pod: $STATUS (ready: $READY, restarts: $RESTARTS)"
        fi
    done
    
    # Check webhook service
    echo ""
    echo "🔗 Checking Webhook Service..."
    if kubectl get svc kserve-webhook-server-service -n "${namespace}" &> /dev/null; then
        ENDPOINT=$(kubectl get endpoints -n "${namespace}" kserve-webhook-server-service -o jsonpath='{.subsets[0].addresses[0].ip}' 2>/dev/null || echo "none")
        if [ "$ENDPOINT" != "none" ] && [ -n "$ENDPOINT" ]; then
            echo "   ✅ Webhook service exists (endpoint: $ENDPOINT)"
        else
            echo "   ⚠️  Webhook service exists but no endpoints"
            echo "   This means webhook server pods are not running"
        fi
    else
        echo "   ❌ Webhook service not found"
    fi
    
    # Check certificate secret
    echo ""
    echo "🔐 Checking Certificate Secret..."
    if kubectl get secret kserve-webhook-server-cert -n "${namespace}" &> /dev/null; then
        echo "   ✅ Certificate secret exists"
    else
        echo "   ❌ Certificate secret not found"
        echo "   Run: ./setup-kserve.sh ${namespace} fix-cert"
    fi
    
    # Check webhook configurations
    echo ""
    echo "🔧 Checking Webhook Configurations..."
    VALIDATING=$(kubectl get validatingwebhookconfiguration 2>/dev/null | grep kserve | wc -l | tr -d ' ')
    MUTATING=$(kubectl get mutatingwebhookconfiguration 2>/dev/null | grep kserve | wc -l | tr -d ' ')
    echo "   Validating webhooks: $VALIDATING"
    echo "   Mutating webhooks: $MUTATING"
    
    # Check for common issues
    echo ""
    echo "🔍 Diagnosing issues..."
    
    # Check if controller is crash looping
    CRASH_LOOP=$(kubectl get pods -n "${namespace}" -l control-plane=kserve-controller-manager -o jsonpath='{.items[0].status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || echo "")
    if [ "$CRASH_LOOP" = "CrashLoopBackOff" ]; then
        echo "   ⚠️  Controller is in CrashLoopBackOff"
        echo ""
        echo "   📋 Recent logs:"
        kubectl logs -n "${namespace}" -l control-plane=kserve-controller-manager --tail=20 2>&1 | head -10 || true
        echo ""
        echo "   💡 Try:"
        echo "      ./setup-kserve.sh ${namespace} fix-cert"
        echo "      # Or reinstall:"
        echo "      ./setup-kserve.sh ${namespace} reinstall"
    fi
    
    echo ""
    echo "✅ KServe status check complete"
    echo ""
    echo "📚 For more information:"
    echo "   kubectl get all -n ${namespace}"
    echo "   kubectl logs -n ${namespace} -l control-plane=kserve-controller-manager"
}

# ============================================================================
# Main Actions
# ============================================================================

case "${ACTION}" in
    install)
        echo "🚀 Installing KServe to namespace: ${KSERVE_NAMESPACE}"
        echo "   Version: ${KSERVE_VERSION}"
        echo ""
        
        # Check if kubectl is available
        if ! command -v kubectl &> /dev/null; then
            echo "❌ kubectl is not installed. Please install kubectl first."
            exit 1
        fi
        
        # Check if cluster is accessible
        if ! kubectl cluster-info &> /dev/null; then
            echo "❌ Cannot connect to Kubernetes cluster. Please check your kubeconfig."
            exit 1
        fi
        
        # Create namespace if it doesn't exist
        if ! kubectl get namespace "${KSERVE_NAMESPACE}" &> /dev/null; then
            echo "📦 Creating namespace: ${KSERVE_NAMESPACE}"
            kubectl create namespace "${KSERVE_NAMESPACE}"
        fi
        
        # Install KServe
        echo "📦 Installing KServe..."
        
        # KServe 설치 (cert-manager 에러는 무시 - cert-manager는 선택적)
        set +e  # 일시적으로 에러 중단 비활성화
        KSERVE_OUTPUT=$(kubectl apply -f "https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml" 2>&1)
        KSERVE_EXIT_CODE=$?
        set -e  # 에러 중단 다시 활성화
        
        # cert-manager 관련 에러 확인 및 처리
        if echo "${KSERVE_OUTPUT}" | grep -q "cert-manager.io/v1"; then
            echo "   ⚠️  Warning: cert-manager not found"
            echo "   📦 Attempting to install cert-manager or create self-signed certificate..."
            
            # cert-manager 설치
            CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.13.0}"
            set +e  # cert-manager 설치 실패해도 계속 진행
            kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml" 2>&1 | head -20 > /dev/null
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
                    echo "   ⏳ Waiting for certificate to be created..."
                    sleep 10
                    CERT_CREATED=false
                    for i in {1..12}; do
                        if kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" &> /dev/null; then
                            echo "   ✅ Certificate secret created by cert-manager"
                            CERT_CREATED=true
                            break
                        fi
                        sleep 5
                    done
                    
                    if [ "$CERT_CREATED" = "false" ]; then
                        echo "   ⚠️  Certificate not created by cert-manager, creating self-signed certificate..."
                        create_self_signed_cert "${KSERVE_NAMESPACE}" "true"
                    fi
                else
                    echo "   ⚠️  cert-manager not ready, creating self-signed certificate manually..."
                    create_self_signed_cert "${KSERVE_NAMESPACE}" "true"
                fi
            else
                echo "   ⚠️  Failed to install cert-manager, creating self-signed certificate manually..."
                create_self_signed_cert "${KSERVE_NAMESPACE}" "true"
            fi
        fi
        
        # Certificate secret 확인
        if ! kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" &> /dev/null; then
            echo "   ⚠️  Certificate secret not found, creating self-signed certificate..."
            create_self_signed_cert "${KSERVE_NAMESPACE}" "true"
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
        echo "⏳ Waiting for KServe controller to be ready..."
        kubectl wait --for=condition=ready pod -l control-plane=kserve-controller-manager \
            -n "${KSERVE_NAMESPACE}" --timeout=300s || {
            echo "⚠️  Warning: KServe controller may not be fully ready yet"
        }
        
        echo ""
        echo "✅ KServe installed successfully!"
        echo ""
        echo "🔍 Check status with:"
        echo "   ./setup-kserve.sh ${KSERVE_NAMESPACE} check"
        echo "   kubectl get pods -n ${KSERVE_NAMESPACE}"
        echo "   kubectl get crd | grep inferenceservice"
        echo ""
        echo "📚 For more information, visit: https://kserve.github.io/website/"
        ;;
        
    check)
        check_kserve_status "${KSERVE_NAMESPACE}"
        ;;
        
    fix-cert)
        echo "🔧 Fixing KServe webhook certificate..."
        echo "   Namespace: ${KSERVE_NAMESPACE}"
        echo ""
        
        # Check if namespace exists
        if ! kubectl get namespace "${KSERVE_NAMESPACE}" &> /dev/null; then
            echo "❌ Namespace ${KSERVE_NAMESPACE} does not exist"
            exit 1
        fi
        
        create_self_signed_cert "${KSERVE_NAMESPACE}" "false"
        
        echo ""
        echo "✅ Done! KServe controller should start successfully now."
        echo ""
        echo "🔍 Check status with:"
        echo "   ./setup-kserve.sh ${KSERVE_NAMESPACE} check"
        ;;
        
    reinstall)
        echo "🔄 Reinstalling KServe..."
        echo "   Namespace: ${KSERVE_NAMESPACE}"
        echo ""
        
        # Delete existing KServe
        echo "🗑️  Deleting existing KServe installation..."
        kubectl delete -f "https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml" 2>&1 | grep -v "NotFound" || true
        
        # Wait a bit
        sleep 5
        
        # Reinstall
        echo "📦 Reinstalling KServe..."
        ACTION=install "${0}" "${KSERVE_NAMESPACE}" install
        ;;
        
    *)
        echo "❌ Unknown action: ${ACTION}"
        echo ""
        echo "Usage:"
        echo "   ./setup-kserve.sh [namespace]                    - 설치 (기본)"
        echo "   ./setup-kserve.sh [namespace] check              - 상태 확인"
        echo "   ./setup-kserve.sh [namespace] fix-cert           - Certificate 수정"
        echo "   ./setup-kserve.sh [namespace] reinstall          - 재설치"
        exit 1
        ;;
esac
