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
KSERVE_VERSION="${KSERVE_VERSION:-v0.16.0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
    
    # CA bundle 추출 (base64 인코딩)
    CA_BUNDLE=$(cat cert.pem | base64 -w 0 2>/dev/null || cat cert.pem | base64 | tr -d '\n')
    
    # 정리
    cd - > /dev/null
    rm -rf "${TEMP_DIR}"
    
    echo "   ✅ Self-signed certificate secret created"
    
    # Webhook configuration의 CA bundle 업데이트
    echo "   🔧 Updating webhook configurations with new CA bundle..."
    update_webhook_ca_bundle "${CA_BUNDLE}"
    
    # Pod 재시작
    echo "   🔄 Restarting KServe controller to pick up the new certificate..."
    kubectl delete pod -n "${namespace}" -l control-plane=kserve-controller-manager 2>/dev/null || {
        echo "   ⚠️  Could not restart controller pods (they may not exist yet)"
    }
}

# Webhook configuration의 CA bundle 업데이트 함수
update_webhook_ca_bundle() {
    local ca_bundle="${1}"
    
    if [ -z "$ca_bundle" ]; then
        echo "   ⚠️  CA bundle is empty, skipping webhook update"
        return 1
    fi
    
    # ValidatingWebhookConfiguration 업데이트
    VALIDATING_WEBHOOKS=$(kubectl get validatingwebhookconfiguration -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | grep -oE '[^ ]*kserve[^ ]*' || echo "")
    
    if [ -n "$VALIDATING_WEBHOOKS" ]; then
        for webhook in $VALIDATING_WEBHOOKS; do
            echo "   📝 Updating ValidatingWebhookConfiguration: $webhook"
            # 각 webhook의 clientConfig.caBundle 업데이트
            kubectl patch validatingwebhookconfiguration "$webhook" \
                --type='json' \
                -p="[{\"op\": \"replace\", \"path\": \"/webhooks/0/clientConfig/caBundle\", \"value\": \"${ca_bundle}\"}]" 2>/dev/null || \
            kubectl patch validatingwebhookconfiguration "$webhook" \
                --type='json' \
                -p="[{\"op\": \"add\", \"path\": \"/webhooks/0/clientConfig/caBundle\", \"value\": \"${ca_bundle}\"}]" 2>/dev/null || {
                echo "   ⚠️  Failed to update ValidatingWebhookConfiguration $webhook"
            }
        done
    fi
    
    # MutatingWebhookConfiguration 업데이트
    MUTATING_WEBHOOKS=$(kubectl get mutatingwebhookconfiguration -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | grep -oE '[^ ]*kserve[^ ]*' || echo "")
    
    if [ -n "$MUTATING_WEBHOOKS" ]; then
        for webhook in $MUTATING_WEBHOOKS; do
            echo "   📝 Updating MutatingWebhookConfiguration: $webhook"
            # 각 webhook의 clientConfig.caBundle 업데이트
            # webhook이 여러 개일 수 있으므로 모든 webhook을 업데이트
            WEBHOOK_COUNT=$(kubectl get mutatingwebhookconfiguration "$webhook" -o jsonpath='{.webhooks[*].name}' 2>/dev/null | wc -w | tr -d ' ')
            for i in $(seq 0 $((WEBHOOK_COUNT - 1))); do
                kubectl patch mutatingwebhookconfiguration "$webhook" \
                    --type='json' \
                    -p="[{\"op\": \"replace\", \"path\": \"/webhooks/${i}/clientConfig/caBundle\", \"value\": \"${ca_bundle}\"}]" 2>/dev/null || \
                kubectl patch mutatingwebhookconfiguration "$webhook" \
                    --type='json' \
                    -p="[{\"op\": \"add\", \"path\": \"/webhooks/${i}/clientConfig/caBundle\", \"value\": \"${ca_bundle}\"}]" 2>/dev/null || {
                    echo "   ⚠️  Failed to update webhook $i in MutatingWebhookConfiguration $webhook"
                }
            done
        done
    fi
    
    echo "   ✅ Webhook configurations updated with new CA bundle"
}

# KServe InferenceService 기본 배포 모드를 RawDeployment(Standard)로 설정
set_default_deployment_mode() {
    local namespace="${1:-${KSERVE_NAMESPACE}}"
    
    echo "   🔧 Setting InferenceService defaultDeploymentMode=Standard (RawDeployment)..."
    
    # ConfigMap 존재 여부 확인
    if ! kubectl get configmap inferenceservice-config -n "${namespace}" &> /dev/null; then
        echo "   ⚠️  ConfigMap 'inferenceservice-config' not found in namespace ${namespace}"
        echo "       Skipping defaultDeploymentMode patch."
        return 0
    fi
    
    # defaultDeploymentMode를 Standard(RawDeployment)로 설정
    if kubectl patch configmap inferenceservice-config -n "${namespace}" \
        --type=merge \
        -p '{"data":{"deploy":"{\"defaultDeploymentMode\":\"Standard\"}"}}' >/dev/null 2>&1; then
        echo "   ✅ defaultDeploymentMode set to Standard (RawDeployment)"
    else
        echo "   ⚠️  Failed to patch defaultDeploymentMode. You can apply manually:"
        echo "       kubectl patch configmap inferenceservice-config -n ${namespace} --type=merge -p '{\"data\":{\"deploy\":\"{\\\"defaultDeploymentMode\\\":\\\"Standard\\\"}\"}}'"
    fi
}

# KServe 상태 확인 함수
check_kserve_status() {
    local namespace="${1:-${KSERVE_NAMESPACE}}"
    local has_errors=false
    
    echo "🔍 Checking KServe installation status..."
    echo "   Namespace: ${namespace}"
    echo ""
    
    # Check namespace
    if ! kubectl get namespace "${namespace}" &> /dev/null; then
        echo "❌ KServe namespace '${namespace}' does not exist"
        echo "   Run: ./setup-kserve.sh ${namespace}"
        return 1
    fi
    
    # Check CRDs - 실제로 사용 가능한 리소스 확인
    echo "📋 Checking CRDs..."
    
    # kubectl api-resources로 실제 사용 가능한 리소스 확인
    INFERENCE_SERVICE_RESOURCE=$(kubectl api-resources --api-group=serving.kserve.io -o name 2>/dev/null | grep -i "inferenceservice" || echo "")
    
    if [ -n "$INFERENCE_SERVICE_RESOURCE" ]; then
        echo "   ✅ InferenceService resource is available: $INFERENCE_SERVICE_RESOURCE"
        # 실제로 리소스를 조회할 수 있는지 확인
        if kubectl get "$INFERENCE_SERVICE_RESOURCE" -n "${namespace}" &> /dev/null 2>&1; then
            echo "   ✅ Can query InferenceService resources"
        else
            echo "   ⚠️  InferenceService CRD exists but cannot query resources"
            echo ""
            echo "   🔍 Diagnosing the issue..."
            
            # CRD 상태 확인
            CRD_STATUS=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null || echo "Unknown")
            echo "   CRD Established status: $CRD_STATUS"
            
            # CRD conditions 확인
            echo "   CRD conditions:"
            kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.message}{"\n"}{end}' 2>/dev/null || echo "   (unable to get conditions)"
            
            # Controller 상태 확인
            echo ""
            echo "   🔍 Checking KServe controller..."
            CONTROLLER_PODS=$(kubectl get pods -n "${namespace}" -l control-plane=kserve-controller-manager -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
            if [ -n "$CONTROLLER_PODS" ]; then
                echo "   Controller pods: $CONTROLLER_PODS"
                for pod in $CONTROLLER_PODS; do
                    POD_STATUS=$(kubectl get pod "$pod" -n "${namespace}" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
                    echo "   - $pod: $POD_STATUS"
                    if [ "$POD_STATUS" != "Running" ]; then
                        echo "     Checking logs..."
                        kubectl logs "$pod" -n "${namespace}" --tail=5 2>&1 | head -3 || true
                    fi
                done
            else
                echo "   ❌ No controller pods found"
            fi
            
            # 권한 확인
            echo ""
            echo "   🔍 Checking permissions..."
            if kubectl auth can-i get crd inferenceservices.serving.kserve.io &> /dev/null; then
                echo "   ✅ Have permission to get CRD"
            else
                echo "   ⚠️  May not have permission to get CRD"
            fi
            
            if kubectl auth can-i get "$INFERENCE_SERVICE_RESOURCE" -n "${namespace}" &> /dev/null; then
                echo "   ✅ Have permission to get InferenceService"
            else
                echo "   ⚠️  May not have permission to get InferenceService"
            fi
            
            echo ""
            echo "   💡 Possible solutions:"
            echo "      1. Wait a few minutes for API server to refresh discovery cache"
            echo "      2. Restart KServe controller:"
            echo "         kubectl delete pod -n ${namespace} -l control-plane=kserve-controller-manager"
            echo "      3. Reinstall KServe CRDs:"
            echo "         ./setup-kserve.sh ${namespace} reinstall"
            echo "      4. Check if CRD is properly installed:"
            echo "         kubectl get crd inferenceservices.serving.kserve.io -o yaml"
            echo "      5. If using a managed cluster, contact your cluster administrator"
            
            has_errors=true
        fi
    else
        echo "   ❌ InferenceService CRD not found or not available"
        echo "   Checking CRD directly..."
        
        # CRD 직접 확인
        if kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
            CRD_STATUS=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null || echo "Unknown")
            if [ "$CRD_STATUS" = "True" ]; then
                echo "   ⚠️  CRD exists but resource is not available in api-resources"
                echo "   This may indicate a controller issue"
            else
                echo "   ⚠️  CRD exists but not established (status: $CRD_STATUS)"
            fi
        else
            echo "   ❌ CRD 'inferenceservices.serving.kserve.io' does not exist"
        fi
        
        # 다른 KServe CRD 확인
        echo ""
        echo "   📋 Checking other KServe CRDs..."
        KSERVE_CRDS=$(kubectl get crd 2>/dev/null | grep -i kserve | awk '{print $1}' || echo "")
        if [ -n "$KSERVE_CRDS" ]; then
            echo "   Found KServe CRDs:"
            echo "$KSERVE_CRDS" | while read crd; do
                echo "      - $crd"
            done
        else
            echo "   ❌ No KServe CRDs found at all"
        fi
        
        # 사용 가능한 모든 inference 관련 리소스 확인
        echo ""
        echo "   📋 Available inference-related resources:"
        INFERENCE_RESOURCES=$(kubectl api-resources 2>/dev/null | grep -i inference || echo "   (none)")
        if [ -n "$INFERENCE_RESOURCES" ] && [ "$INFERENCE_RESOURCES" != "   (none)" ]; then
            echo "$INFERENCE_RESOURCES" | while read line; do
                echo "      $line"
            done
        else
            echo "   (none found)"
        fi
        
        has_errors=true
    fi
    
    # Check pods
    echo ""
    echo "📦 Checking Pods..."
    PODS=$(kubectl get pods -n "${namespace}" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    if [ -z "$PODS" ]; then
        echo "   ❌ No pods found in ${namespace} namespace"
        has_errors=true
    else
    for pod in $PODS; do
        STATUS=$(kubectl get pod -n "${namespace}" "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
        READY=$(kubectl get pod -n "${namespace}" "$pod" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null || echo "false")
        RESTARTS=$(kubectl get pod -n "${namespace}" "$pod" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")
        
        if [ "$STATUS" = "Running" ] && [ "$READY" = "true" ]; then
            echo "   ✅ $pod: Running (restarts: $RESTARTS)"
        else
            echo "   ⚠️  $pod: $STATUS (ready: $READY, restarts: $RESTARTS)"
                if [ "$STATUS" != "Running" ] || [ "$READY" != "true" ]; then
                    has_errors=true
                fi
        fi
    done
    fi
    
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
            has_errors=true
        fi
    else
        echo "   ❌ Webhook service not found"
        has_errors=true
    fi
    
    # Check certificate secret
    echo ""
    echo "🔐 Checking Certificate Secret..."
    if kubectl get secret kserve-webhook-server-cert -n "${namespace}" &> /dev/null; then
        echo "   ✅ Certificate secret exists"
    else
        echo "   ❌ Certificate secret not found"
        echo "   Run: ./setup-kserve.sh ${namespace} fix-cert"
        has_errors=true
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
        has_errors=true
    fi
    
    echo ""
    if [ "$has_errors" = "true" ]; then
        echo "❌ KServe status check found issues"
        echo ""
        echo "💡 Troubleshooting steps:"
        echo "   1. Check if KServe was installed correctly:"
        echo "      ./setup-kserve.sh ${namespace} reinstall"
        echo ""
        echo "   2. If CRD exists but resource is not available, check controller logs:"
        echo "      kubectl logs -n ${namespace} -l control-plane=kserve-controller-manager"
        echo ""
        echo "   3. Check if all required dependencies are installed:"
        echo "      kubectl get crd | grep -E 'knative|istio'"
        echo ""
        echo "   4. For more information, see: infra/scripts/README-KSERVE-ISSUES.md"
    else
        echo "✅ KServe status check complete - all checks passed"
    fi
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
        echo "   💡 Using 'create' for CRDs to avoid 256KB annotation size limit"
        
        # CRD는 kubectl apply 대신 create를 사용해야 함 (annotation 256KB 제한 회피)
        # YAML 파일을 임시로 다운로드하여 CRD와 다른 리소스를 분리
        TEMP_YAML=$(mktemp)
        TEMP_CRD=$(mktemp)
        TEMP_NON_CRD=$(mktemp)
        
        echo "   📥 Downloading KServe YAML..."
        curl -sSL "https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml" -o "${TEMP_YAML}" || {
            echo "   ❌ Failed to download KServe YAML"
            rm -f "${TEMP_YAML}" "${TEMP_CRD}" "${TEMP_NON_CRD}"
            exit 1
        }
        
        # CRD만 추출 (YAML에서 CRD 리소스만 분리)
        echo "   📋 Extracting CRDs..."
        # YAML을 ---로 분리하여 각 문서를 개별적으로 처리
        # 각 문서를 임시 디렉토리에 저장하고 CRD인지 확인
        TEMP_DIR=$(mktemp -d)
        SPLIT_COUNT=0
        
        # YAML을 ---로 분리 (첫 문서는 --- 없이 시작할 수 있음)
        awk '
            BEGIN { 
                count = 0
                file = ""
            }
            /^---$/ {
                if(file != "") {
                    close(file)
                }
                count++
                file = "'"${TEMP_DIR}"'/doc" count ".yaml"
                next
            }
            {
                if(file == "") {
                    count++
                    file = "'"${TEMP_DIR}"'/doc" count ".yaml"
                }
                print > file
            }
        ' "${TEMP_YAML}" 2>/dev/null || true
        
        # 각 문서를 확인하여 CRD와 non-CRD로 분리
        for doc in "${TEMP_DIR}"/doc*.yaml; do
            if [ ! -f "$doc" ] || [ ! -s "$doc" ]; then
                continue
            fi
            
            # kind 필드 확인
            if grep -q "^kind: CustomResourceDefinition" "$doc" 2>/dev/null; then
                # CRD인 경우
                if [ -s "${TEMP_CRD}" ]; then
                    echo "---" >> "${TEMP_CRD}"
                fi
                cat "$doc" >> "${TEMP_CRD}"
            else
                # CRD가 아닌 경우
                if [ -s "${TEMP_NON_CRD}" ]; then
                    echo "---" >> "${TEMP_NON_CRD}"
                fi
                cat "$doc" >> "${TEMP_NON_CRD}"
            fi
        done
        
        # 임시 디렉토리 정리
        rm -rf "${TEMP_DIR}"
        
        # CRD 파일 검증
        if [ -s "${TEMP_CRD}" ] && grep -q "^kind: CustomResourceDefinition" "${TEMP_CRD}" 2>/dev/null; then
            echo "   📦 Installing CRDs with 'create' (avoids annotation size limit)..."
            set +e
            # CRD를 create로 설치
            CRD_OUTPUT=$(kubectl create -f "${TEMP_CRD}" --validate=false 2>&1)
            CRD_EXIT=$?
            
            # AlreadyExists 에러가 있으면 replace로 재시도
            if echo "$CRD_OUTPUT" | grep -q "AlreadyExists"; then
                echo "   🔄 Some CRDs already exist, replacing..."
                kubectl replace -f "${TEMP_CRD}" --validate=false 2>&1 | grep -vE "(NotFound|unchanged)" > /dev/null || true
            fi
            set -e
        else
            echo "   ⚠️  Could not extract CRDs properly, will install all resources with apply"
            CRD_EXIT=1
            # CRD 추출 실패 시 전체 YAML을 non-CRD로 사용
            cp "${TEMP_YAML}" "${TEMP_NON_CRD}"
        fi
        
        # CRD가 아닌 리소스 파일 검증
        if [ ! -s "${TEMP_NON_CRD}" ] || ! grep -q "^kind:" "${TEMP_NON_CRD}" 2>/dev/null; then
            echo "   ⚠️  Non-CRD resources file is empty or invalid, using full YAML"
            cp "${TEMP_YAML}" "${TEMP_NON_CRD}"
        fi
        
        echo "   📦 Installing other resources with 'apply'..."
        
        # 나머지 리소스는 apply로 설치
        set +e  # 일시적으로 에러 중단 비활성화
        KSERVE_OUTPUT=$(kubectl apply -f "${TEMP_NON_CRD}" 2>&1)
        KSERVE_EXIT_CODE=$?
        set -e  # 에러 중단 다시 활성화
        
        # 임시 파일 정리
        rm -f "${TEMP_YAML}" "${TEMP_CRD}" "${TEMP_NON_CRD}"
        
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
        echo "   🔍 Verifying KServe CRD installation..."
        CRD_EXISTS=false
        CRD_ESTABLISHED=false
        RESOURCE_AVAILABLE=false
        
        # CRD 존재 확인
        for i in {1..15}; do
        if kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
                echo "   ✅ InferenceService CRD exists"
                CRD_EXISTS=true
                break
        else
                echo "   ⏳ Waiting for CRD to be created... (attempt $i/15)"
                sleep 2
            fi
        done
        
        if [ "$CRD_EXISTS" != "true" ]; then
            echo "   ❌ InferenceService CRD was not created"
            echo ""
            echo "   📋 KServe installation output (last 50 lines):"
            echo "${KSERVE_OUTPUT}" | tail -50
            echo ""
            echo "   💡 Troubleshooting:"
            echo "      1. Check if you have cluster-admin permissions"
            echo "      2. Check if the cluster supports CRD installation"
            echo "      3. Try manual installation:"
            echo "         kubectl apply -f https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml"
            exit 1
        fi
        
        # 컨트롤러가 실행 중인지 확인 (Established는 컨트롤러가 필요)
        echo "   🔍 Checking if KServe controller is running..."
        CONTROLLER_READY=false
        for i in {1..30}; do
            CONTROLLER_PODS=$(kubectl get pods -n "${KSERVE_NAMESPACE}" -l control-plane=kserve-controller-manager -o jsonpath='{.items[*].status.phase}' 2>/dev/null || echo "")
            if echo "$CONTROLLER_PODS" | grep -q "Running"; then
                echo "   ✅ KServe controller is running"
                CONTROLLER_READY=true
                break
            else
                echo "   ⏳ Waiting for controller to start... (attempt $i/30)"
                sleep 3
            fi
        done
        
        if [ "$CONTROLLER_READY" != "true" ]; then
            echo "   ⚠️  Warning: Controller is not running yet"
            echo "   Checking controller pod status..."
            kubectl get pods -n "${KSERVE_NAMESPACE}" -l control-plane=kserve-controller-manager 2>/dev/null || true
            echo ""
            echo "   Checking controller logs..."
            kubectl logs -n "${KSERVE_NAMESPACE}" -l control-plane=kserve-controller-manager --tail=20 2>&1 | head -15 || true
        fi
        
        # CRD가 API server에 등록되었는지 확인 (가장 중요)
        echo ""
        echo "   🔍 Verifying CRD is registered in API server..."
        API_RESOURCE_AVAILABLE=false
        for i in {1..20}; do
            INFERENCE_SERVICE_RESOURCE=$(kubectl api-resources --api-group=serving.kserve.io -o name 2>/dev/null | grep -i "inferenceservice" || echo "")
            if [ -n "$INFERENCE_SERVICE_RESOURCE" ]; then
                echo "   ✅ InferenceService is registered in API server: $INFERENCE_SERVICE_RESOURCE"
                API_RESOURCE_AVAILABLE=true
                break
            else
                if [ $i -le 5 ]; then
                    echo "   ⏳ Waiting for CRD to be registered in API server... (attempt $i/20)"
                fi
                sleep 2
            fi
        done
        
        if [ "$API_RESOURCE_AVAILABLE" != "true" ]; then
            echo ""
            echo "   ❌ CRITICAL: InferenceService CRD is not registered in API server"
            echo "   This means the CRD exists but Kubernetes API server doesn't recognize it."
            echo ""
            echo "   🔧 Attempting to fix by restarting API server discovery..."
            echo "   (This may require cluster admin privileges)"
            
            # Try to trigger API server refresh by deleting and recreating CRD
            echo "   📝 Checking CRD status..."
            CRD_STATUS=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null || echo "Unknown")
            CRD_MESSAGE=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].message}' 2>/dev/null || echo "")
            
            echo "   CRD Established status: $CRD_STATUS"
            if [ -n "$CRD_MESSAGE" ]; then
                echo "   CRD message: $CRD_MESSAGE"
            fi
            
            echo ""
            echo "   💡 Manual fix steps:"
            echo "      1. Restart kube-apiserver (if you have access):"
            echo "         kubectl delete pod -n kube-system -l component=kube-apiserver"
            echo ""
            echo "      2. Or reinstall KServe CRDs:"
            echo "         kubectl delete crd inferenceservices.serving.kserve.io"
            echo "         kubectl apply -f https://github.com/kserve/kserve/releases/download/${KSERVE_VERSION}/kserve.yaml"
            echo ""
            echo "      3. Or wait a few minutes for API server to refresh"
            echo ""
            echo "   ⚠️  Continuing installation, but InferenceService may not work until CRD is registered"
        fi
        
        # CRD Established 상태 확인 (하지만 False여도 리소스는 사용 가능할 수 있음)
        echo "   🔍 Checking CRD Established status..."
        CRD_STATUS=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null || echo "Unknown")
        CRD_MESSAGE=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].message}' 2>/dev/null || echo "")
        
        if [ "$CRD_STATUS" = "True" ]; then
            echo "   ✅ CRD is Established"
            CRD_ESTABLISHED=true
        else
            echo "   ⚠️  CRD Established status: $CRD_STATUS"
            if [ -n "$CRD_MESSAGE" ]; then
                echo "   Message: $CRD_MESSAGE"
            fi
            
            # CRD의 모든 conditions 확인
            echo "   📋 All CRD conditions:"
            kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.message}{"\n"}{end}' 2>/dev/null || echo "   (unable to get conditions)"
            
            # Established가 False여도 리소스가 사용 가능한지 확인
            echo ""
            echo "   🔍 Checking if resource is available despite Established=False..."
        fi
        
        # 실제로 리소스를 사용할 수 있는지 확인 (이것이 가장 중요)
        echo "   🔍 Verifying InferenceService resource is available in api-resources..."
        for i in {1..20}; do
            INFERENCE_SERVICE_RESOURCE=$(kubectl api-resources --api-group=serving.kserve.io -o name 2>/dev/null | grep -i "inferenceservice" || echo "")
            if [ -n "$INFERENCE_SERVICE_RESOURCE" ]; then
                echo "   ✅ InferenceService resource is available: $INFERENCE_SERVICE_RESOURCE"
                RESOURCE_AVAILABLE=true
                break
            else
                if [ $i -le 5 ]; then
                    echo "   ⏳ Waiting for resource to be available... (attempt $i/20)"
                fi
                sleep 2
            fi
        done
        
        # 최종 판단
        if [ "$RESOURCE_AVAILABLE" = "true" ]; then
            echo ""
            echo "   ✅ InferenceService resource is available and can be used"
            if [ "$CRD_ESTABLISHED" != "true" ]; then
                echo "   ⚠️  Note: CRD Established status is False, but resource is usable"
                echo "   This is often acceptable - the resource may work despite the status"
            fi
        else
            echo ""
            echo "   ❌ InferenceService resource is not available in api-resources"
            echo ""
            echo "   🔍 Additional diagnostics:"
            
            # CRD가 존재하는지 다시 확인
            if kubectl get crd inferenceservices.serving.kserve.io &> /dev/null; then
                echo "   ✅ CRD exists: inferenceservices.serving.kserve.io"
                
                # CRD spec 확인
                CRD_VERSIONS=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.spec.versions[*].name}' 2>/dev/null || echo "")
                echo "   CRD versions: $CRD_VERSIONS"
                
                # CRD status 확인
                CRD_STATUS=$(kubectl get crd inferenceservices.serving.kserve.io -o jsonpath='{.status.conditions[?(@.type=="Established")].status}' 2>/dev/null || echo "Unknown")
                echo "   CRD Established: $CRD_STATUS"
                
                if [ "$CRD_STATUS" != "True" ]; then
                    echo ""
                    echo "   ⚠️  CRD is not Established. This usually means:"
                    echo "      - Controller is not running"
                    echo "      - CRD schema has errors"
                    echo "      - API server hasn't processed the CRD yet"
                    echo ""
                    echo "   Checking controller status..."
                    CONTROLLER_PODS=$(kubectl get pods -n "${KSERVE_NAMESPACE}" -l control-plane=kserve-controller-manager -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
                    if [ -z "$CONTROLLER_PODS" ]; then
                        echo "   ❌ No controller pods found"
                        echo "   Controller must be running for CRD to be Established"
                    else
                        for pod in $CONTROLLER_PODS; do
                            POD_STATUS=$(kubectl get pod "$pod" -n "${KSERVE_NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
                            echo "   Controller pod $pod: $POD_STATUS"
                            if [ "$POD_STATUS" != "Running" ]; then
                                echo "   Checking pod events..."
                                kubectl describe pod "$pod" -n "${KSERVE_NAMESPACE}" 2>/dev/null | grep -A 5 "Events:" || true
                            fi
                        done
                    fi
                fi
            else
                echo "   ❌ CRD does not exist: inferenceservices.serving.kserve.io"
            fi
            
            echo ""
            echo "   💡 Try these solutions:"
            echo "      1. Reinstall KServe: ./setup-kserve.sh ${KSERVE_NAMESPACE} reinstall"
            echo "      2. Restart controller: kubectl delete pod -n ${KSERVE_NAMESPACE} -l control-plane=kserve-controller-manager"
            echo "      3. Wait 2-3 minutes for API server discovery cache to refresh"
            echo "      4. Check API server logs if you have access"
            echo ""
            echo "   📋 Troubleshooting steps:"
            echo "      1. Check controller logs:"
            echo "         kubectl logs -n ${KSERVE_NAMESPACE} -l control-plane=kserve-controller-manager"
            echo ""
            echo "      2. Check controller pod status:"
            echo "         kubectl get pods -n ${KSERVE_NAMESPACE} -l control-plane=kserve-controller-manager"
            echo ""
            echo "      3. Check webhook configuration:"
            echo "         kubectl get validatingwebhookconfiguration | grep kserve"
            echo "         kubectl get mutatingwebhookconfiguration | grep kserve"
            echo ""
            echo "      4. Check certificate secret:"
            echo "         kubectl get secret kserve-webhook-server-cert -n ${KSERVE_NAMESPACE}"
            echo ""
            echo "      5. Check for events:"
            echo "         kubectl get events -n ${KSERVE_NAMESPACE} --sort-by='.lastTimestamp' | tail -20"
            echo ""
            echo "      6. Try fixing certificate:"
            echo "         ./setup-kserve.sh ${KSERVE_NAMESPACE} fix-cert"
            echo ""
            echo "      7. If all else fails, reinstall:"
            echo "         ./setup-kserve.sh ${KSERVE_NAMESPACE} reinstall"
            
            # 경고만 출력하고 계속 진행 (일부 경우에는 나중에 작동할 수 있음)
            echo ""
            echo "   ⚠️  Installation may be incomplete, but continuing..."
        fi
        
        # Wait for KServe controller to be ready (이미 위에서 확인했지만 다시 확인)
        echo ""
        echo "⏳ Waiting for KServe controller to be fully ready..."
        set +e
        kubectl wait --for=condition=ready pod -l control-plane=kserve-controller-manager \
            -n "${KSERVE_NAMESPACE}" --timeout=300s 2>&1 > /dev/null
        CONTROLLER_WAIT_EXIT=$?
        set -e
        
        if [ $CONTROLLER_WAIT_EXIT -eq 0 ]; then
            echo "   ✅ KServe controller is ready"
        else
            echo "   ⚠️  Warning: KServe controller may not be fully ready yet"
            echo "   Checking controller status..."
            kubectl get pods -n "${KSERVE_NAMESPACE}" -l control-plane=kserve-controller-manager 2>/dev/null || true
        fi

        # Ensure default deployment mode is RawDeployment(Standard)
        echo ""
        set_default_deployment_mode "${KSERVE_NAMESPACE}"
        
        echo ""
        echo "✅ KServe installed successfully!"
        echo ""
        echo "🔍 Check status with:"
        echo "   ./setup-kserve.sh ${KSERVE_NAMESPACE} check"
        echo "   kubectl get pods -n ${KSERVE_NAMESPACE}"
        echo "   kubectl get crd | grep inferenceservice"
        echo "   kubectl api-resources | grep -i inference"
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
        
        # Check if certificate secret exists
        if kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" &> /dev/null; then
            echo "   📋 Certificate secret exists, extracting CA bundle..."
            # Extract CA bundle from existing secret
            CA_BUNDLE=$(kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" -o jsonpath='{.data.tls\.crt}' 2>/dev/null | base64 -d 2>/dev/null | base64 -w 0 2>/dev/null || \
                       kubectl get secret kserve-webhook-server-cert -n "${KSERVE_NAMESPACE}" -o jsonpath='{.data.tls\.crt}' 2>/dev/null | base64 -d 2>/dev/null | base64 | tr -d '\n' || echo "")
            
            if [ -n "$CA_BUNDLE" ]; then
                echo "   ✅ Extracted CA bundle from existing certificate"
                update_webhook_ca_bundle "${CA_BUNDLE}"
            else
                echo "   ⚠️  Failed to extract CA bundle, recreating certificate..."
                create_self_signed_cert "${KSERVE_NAMESPACE}" "false"
            fi
        else
            echo "   📝 Certificate secret not found, creating new certificate..."
        create_self_signed_cert "${KSERVE_NAMESPACE}" "false"
        fi
        
        echo ""
        echo "✅ Done! KServe webhook certificate has been fixed."
        echo ""
        echo "🔍 Check status with:"
        echo "   ./setup-kserve.sh ${KSERVE_NAMESPACE} check"
        echo ""
        echo "💡 Verify webhook CA bundle:"
        echo "   kubectl get validatingwebhookconfiguration inferenceservice.serving.kserve.io -o jsonpath='{.webhooks[0].clientConfig.caBundle}' | base64 -d | openssl x509 -text -noout"
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
