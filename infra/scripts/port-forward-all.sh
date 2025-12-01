#!/bin/bash
# 모든 의존성 서비스를 port-forward하는 스크립트
# Usage: ./port-forward-all.sh [environment]

set -e

ENVIRONMENT="${1:-dev}"
NAMESPACE="llm-ops-${ENVIRONMENT}"

USED_PORTS=""  # local ports already reserved by this script

is_port_in_use() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    elif command -v netstat >/dev/null 2>&1; then
        netstat -an 2>/dev/null | grep LISTEN | grep -q ":${port} "
        return $?
    else:
        # 도구가 없으면 사용 중이 아닌 것으로 가정 (중복은 USED_PORTS로만 방지)
        return 1
    fi
}

allocate_port() {
    local desired="$1"
    local port="$desired"

    while true; do
        # 이미 이 스크립트에서 사용했는지 또는 다른 프로세스가 사용 중인지 확인
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

# Check if namespace exists
if ! kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo "❌ Namespace ${NAMESPACE} does not exist"
    exit 1
fi

# Start port-forwards in background
echo "📡 Starting core dependency port-forwards..."
echo ""

# PostgreSQL
kubectl port-forward -n "${NAMESPACE}" svc/postgresql 5432:5432 &
POSTGRES_PID=$!
echo "   ✅ PostgreSQL: localhost:5432 (PID: ${POSTGRES_PID})"
USED_PORTS="${USED_PORTS} 5432"

# Redis
kubectl port-forward -n "${NAMESPACE}" svc/redis 6379:6379 &
REDIS_PID=$!
echo "   ✅ Redis: localhost:6379 (PID: ${REDIS_PID})"
USED_PORTS="${USED_PORTS} 6379"

# MinIO API
kubectl port-forward -n "${NAMESPACE}" svc/minio 9000:9000 &
MINIO_API_PID=$!
echo "   ✅ MinIO API: http://localhost:9000 (PID: ${MINIO_API_PID})"
USED_PORTS="${USED_PORTS} 9000"

# MinIO Console
kubectl port-forward -n "${NAMESPACE}" svc/minio 9001:9001 &
MINIO_CONSOLE_PID=$!
echo "   ✅ MinIO Console: http://localhost:9001 (PID: ${MINIO_CONSOLE_PID})"
USED_PORTS="${USED_PORTS} 9001"

# Start port-forwards for all other services in the namespace (llm-ops-*)
echo ""
echo "📡 Discovering and starting port-forwards for all other services in ${NAMESPACE}..."
echo ""

FORWARD_PIDS=()

# List all services in the namespace (excluding already-handled core deps)
SERVICES=$(kubectl get svc -n "${NAMESPACE}" --no-headers | awk '{print $1}')

for SVC in ${SERVICES}; do
    case "${SVC}" in
        postgresql|redis|minio)
            # Already handled explicitly above
            continue
            ;;
    esac

    # Get all ports for the service and port-forward each (localPort == servicePort)
    PORTS=$(kubectl get svc "${SVC}" -n "${NAMESPACE}" -o jsonpath='{range .spec.ports[*]}{.port}{" "}{end}')

    for PORT in ${PORTS}; do
        if [ -z "${PORT}" ]; then
            continue
        fi

        # 원하는 기본 포트는 서비스 포트이지만, 이미 사용 중이면 다음 포트로 자동 증가
        LOCAL_PORT=$(allocate_port "${PORT}")

        kubectl port-forward -n "${NAMESPACE}" "svc/${SVC}" "${LOCAL_PORT}:${PORT}" >/dev/null 2>&1 &
        PID=$!
        FORWARD_PIDS+=("${PID}")
        echo "   ✅ ${SVC}: localhost:${LOCAL_PORT} -> ${SVC}:${PORT} (PID: ${PID})"
    done
done

echo ""
echo "✅ All port-forwards started!"
echo ""
echo "📍 Core service endpoints:"
echo "   PostgreSQL: localhost:5432"
echo "   Redis: localhost:6379"
echo "   MinIO API: http://localhost:9000"
echo "   MinIO Console: http://localhost:9001 (Login: llmops / llmops-secret)"
echo ""
echo "💡 Backend .env configuration:"
echo "   DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops"
echo "   REDIS_URL=redis://localhost:6379/0"
echo "   OBJECT_STORE_ENDPOINT=http://localhost:9000"
echo ""
echo "Press Ctrl+C to stop all port-forwards"

# Wait for user interrupt
trap 'echo ""; echo "🛑 Stopping port-forwards..."; kill ${POSTGRES_PID} ${REDIS_PID} ${MINIO_API_PID} ${MINIO_CONSOLE_PID} "${FORWARD_PIDS[@]}" 2>/dev/null; exit' INT
wait

