#!/bin/bash
# 모든 의존성 서비스를 port-forward하는 스크립트
# Usage: ./port-forward-all.sh [environment]
#
# 특징:
# - k8s 서비스 포트(80, 8000, 8080 등)와 상관없이,
#   "로컬 포트는 지정된 범위 내에서만" 자동 할당됨.
# - 기본 범위: 20000~21000 (환경변수로 조정 가능)
#   예: PORT_RANGE_START=25000 PORT_RANGE_END=26000 ./port-forward-all.sh

set -e

ENVIRONMENT="${1:-dev}"
NAMESPACE="llm-ops-${ENVIRONMENT}"

########################################
# 🔧 로컬 포트 범위 설정 (환경변수로 오버라이드 가능)
########################################
PORT_RANGE_START="${PORT_RANGE_START:-20000}"
PORT_RANGE_END="${PORT_RANGE_END:-21000}"

# 이 스크립트에서 절대 쓰지 않을 예약 포트들
# (이미 다른 용도로 자주 쓰거나, 충돌 위험이 큰 포트들)
RESERVED_PORTS="80 443 8000 8080"

# 이 스크립트에서 이미 사용한 포트 + 예약 포트
USED_PORTS="${RESERVED_PORTS}"

########################################
# 공용 함수들
########################################

is_port_in_use() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    elif command -v netstat >/dev/null 2>&1; then
        netstat -an 2>/dev/null | grep LISTEN | grep -q ":${port} "
        return $?
    else
        # 도구가 없으면 사용 중이 아닌 것으로 가정 (USED_PORTS만 활용)
        return 1
    fi
}

# 지정된 범위(PORT_RANGE_START~PORT_RANGE_END) 안에서만 포트 할당
allocate_port() {
    local desired="$1"
    local port="$desired"

    # 시작 포트가 범위보다 작으면 범위 시작으로 보정
    if (( port < PORT_RANGE_START )); then
        port="${PORT_RANGE_START}"
    fi

    while true; do
        # 범위를 넘어가면 에러
        if (( port > PORT_RANGE_END )); then
            echo "❌ No available ports in range ${PORT_RANGE_START}-${PORT_RANGE_END}" >&2
            exit 1
        fi

        # 예약/이미 사용 포트인지, 다른 프로세스가 사용하는지 확인
        if [[ " ${USED_PORTS} " != *" ${port} "* ]] && ! is_port_in_use "${port}"; then
            USED_PORTS="${USED_PORTS} ${port}"
            echo "${port}"
            return 0
        fi

        port=$((port + 1))
    done
}

echo "🔌 Starting port-forward for services in namespace: ${NAMESPACE}"
echo ""
echo "⚠️  This script will run in the foreground. Press Ctrl+C to stop."
echo ""

# 필요 시 네임스페이스 존재 여부 체크
# if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
#     echo "❌ Namespace ${NAMESPACE} does not exist"
#     exit 1
# fi

# Start port-forwards in background
echo "📡 Starting core dependency port-forwards..."
echo ""

############################################
# 👉 Kubernetes API Server (minikube 등) 포트포워드
############################################

# kube-apiserver Pod 이름 자동 검색
APISERVER_POD=$(kubectl get pod -n kube-system \
  -l component=kube-apiserver \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

if [ -z "${APISERVER_POD}" ]; then
  # 일부 클러스터는 label 이 다를 수 있어서 fallback
  APISERVER_POD=$(kubectl get pod -n kube-system \
    | awk '/kube-apiserver/ {print $1; exit}')
fi

if [ -n "${APISERVER_POD}" ]; then
    # 로컬 포트는 범위 안에서 자동 할당, 원격 포트는 8443 고정
    K8S_API_LOCAL_PORT=$(allocate_port "${PORT_RANGE_START}")

    kubectl port-forward --address 0.0.0.0 \
      -n kube-system "pod/${APISERVER_POD}" \
      "${K8S_API_LOCAL_PORT}:8443" >/dev/null 2>&1 &
    K8S_API_PID=$!
    echo "   ✅ Kubernetes API Server: https://0.0.0.0:${K8S_API_LOCAL_PORT} (PID: ${K8S_API_PID})"
else
    echo "   ⚠️  kube-apiserver Pod 를 kube-system 네임스페이스에서 찾지 못해 API Server port-forward 를 건너뜁니다."
fi

############################################
# ✅ 고정 포트로 포워드할 코어 서비스들
############################################

# PostgreSQL (로컬 5432 고정)
kubectl port-forward --address 0.0.0.0 -n "${NAMESPACE}" svc/postgresql 5432:5432 >/dev/null 2>&1 &
POSTGRES_PID=$!
echo "   ✅ PostgreSQL: 0.0.0.0:5432 (PID: ${POSTGRES_PID})"
USED_PORTS="${USED_PORTS} 5432"

# Redis (로컬 6379 고정)
kubectl port-forward --address 0.0.0.0 -n "${NAMESPACE}" svc/redis 6379:6379 >/dev/null 2>&1 &
REDIS_PID=$!
echo "   ✅ Redis: 0.0.0.0:6379 (PID: ${REDIS_PID})"
USED_PORTS="${USED_PORTS} 6379"

# MinIO API (로컬 9000 고정)
kubectl port-forward --address 0.0.0.0 -n "${NAMESPACE}" svc/minio 9000:9000 >/dev/null 2>&1 &
MINIO_API_PID=$!
echo "   ✅ MinIO API: http://0.0.0.0:9000 (PID: ${MINIO_API_PID})"
USED_PORTS="${USED_PORTS} 9000"

# MinIO Console (로컬 9001 고정)
kubectl port-forward --address 0.0.0.0 -n "${NAMESPACE}" svc/minio 9001:9001 >/dev/null 2>&1 &
MINIO_CONSOLE_PID=$!
echo "   ✅ MinIO Console: http://0.0.0.0:9001 (PID: ${MINIO_CONSOLE_PID})"
USED_PORTS="${USED_PORTS} 9001"

############################################
# 📡 기타 서비스들 자동 포트포워드
############################################

echo ""
echo "📡 Discovering and starting port-forwards for all other services in ${NAMESPACE}..."
echo ""

FORWARD_PIDS=()

# 네임스페이스 내 모든 서비스 조회 (이미 처리한 코어 deps 제외)
SERVICES=$(kubectl get svc -n "${NAMESPACE}" --no-headers | awk '{print $1}')

for SVC in ${SERVICES}; do
    case "${SVC}" in
        postgresql|redis|minio)
            # 위에서 이미 처리
            continue
            ;;
    esac

    # 서비스의 모든 포트를 가져와서 각각 포워드
    PORTS=$(kubectl get svc "${SVC}" -n "${NAMESPACE}" -o jsonpath='{range .spec.ports[*]}{.port}{" "}{end}')

    for PORT in ${PORTS}; do
        if [ -z "${PORT}" ]; then
            continue
        fi

        # ✅ 서비스 포트(PORT)가 80, 8000, 8080이어도 상관 없이
        #    로컬 포트는 PORT_RANGE_START~PORT_RANGE_END 안에서만 자동 할당
        LOCAL_PORT=$(allocate_port "${PORT_RANGE_START}")

        kubectl port-forward --address 0.0.0.0 -n "${NAMESPACE}" "svc/${SVC}" "${LOCAL_PORT}:${PORT}" >/dev/null 2>&1 &
        PID=$!
        FORWARD_PIDS+=("${PID}")
        echo "   ✅ ${SVC}: 0.0.0.0:${LOCAL_PORT} -> ${SVC}:${PORT} (PID: ${PID})"
    done
done

echo ""
echo "✅ All port-forwards started!"
echo ""
echo "📍 Core service endpoints (from other 머신에서는 <이 서버 IP> 기준으로 접속):"
echo "   PostgreSQL: <HOST-IP>:5432"
echo "   Redis: <HOST-IP>:6379"
echo "   MinIO API: http://<HOST-IP>:9000"
echo "   MinIO Console: http://<HOST-IP>:9001 (Login: llmops / llmops-secret)"
echo ""
echo "💡 Backend .env configuration (로컬에서 돌릴 때 예시):"
echo "   DATABASE_URL=postgresql+psycopg://llmops:password@<HOST-IP>:5432/llmops"
echo "   REDIS_URL=redis://<HOST-IP>:6379/0"
echo "   OBJECT_STORE_ENDPOINT=http://<HOST-IP>:9000"
echo ""
echo "🔢 Dynamic service port range (로컬):"
echo "   ${PORT_RANGE_START} ~ ${PORT_RANGE_END}"
echo ""
echo "Press Ctrl+C to stop all port-forwards"

# Ctrl+C 시 모든 포트포워드 종료
trap 'echo ""; echo "🛑 Stopping port-forwards..."; \
      kill ${POSTGRES_PID} ${REDIS_PID} ${MINIO_API_PID} ${MINIO_CONSOLE_PID} ${K8S_API_PID:-} "${FORWARD_PIDS[@]}" 2>/dev/null || true; \
      exit' INT

# 백그라운드 포워드 유지
wait