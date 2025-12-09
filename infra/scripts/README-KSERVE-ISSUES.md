# KServe 설치 및 사용 가이드

## 현재 플랫폼의 KServe 사용 방식

**우리 플랫폼은 RawDeployment 모드로 KServe를 사용합니다.**

### 왜 RawDeployment 모드인가?

1. **기존 인프라와의 호환성**
   - 이미 `llm-ops-dev` 네임스페이스에서 표준 Kubernetes Deployment를 사용 중
   - 기존 인프라와 동일한 방식으로 작동

2. **의존성 최소화**
   - Knative Serving, Istio, Kourier 등 추가 컴포넌트 불필요
   - KServe controller만 설치하면 됨

3. **요구사항에 부합**
   - 모델 서빙 관리가 목표 (서버리스/scale-to-zero 불필요)
   - HPA를 통한 오토스케일링 지원
   - 표준 Kubernetes 리소스로 관리 가능

### RawDeployment 모드의 특징

- **생성되는 리소스**: 표준 Kubernetes Deployment (Knative Service 아님)
- **의존성**: Knative/Istio 불필요
- **스케일링**: Kubernetes HPA 사용
- **네트워킹**: 표준 Kubernetes Service 사용

## 문제: KServe Webhook 연결 실패

에러 메시지:
```
failed calling webhook "inferenceservice.kserve-webhook-server.defaulter": 
failed to call webhook: Post "https://kserve-webhook-server-service.kserve.svc:443/...": 
dial tcp 10.109.6.215:443: connect: connection refused
```

## 원인

KServe 컨트롤러가 다음 의존성을 찾지 못합니다:
1. **Knative Serving** - `Service.serving.knative.dev/v1` CRD (RawDeployment 모드에서는 불필요)
2. **Istio** - `VirtualService.networking.istio.io/v1alpha3` CRD (RawDeployment 모드에서는 불필요)
3. **Webhook Server Pod** - webhook 서버가 실행되지 않음

## 해결 방법

### 옵션 1: KServe RawDeployment 모드 사용 (현재 방식, 권장)

**설정:**
```bash
# backend/.env 파일에 추가
USE_KSERVE=true
```

**특징:**
- RawDeployment 모드로 작동 (코드에서 자동 설정)
- Knative/Istio 불필요
- 표준 Kubernetes Deployment 생성
- 기존 인프라와 호환

### 옵션 2: Raw Kubernetes Deployment 사용 (KServe 없이)

KServe 없이 직접 Kubernetes Deployment를 사용합니다.

**설정 변경:**
```bash
# backend/.env 파일에 추가
USE_KSERVE=false
```

또는 `backend/src/core/settings.py`에서 기본값을 변경:
```python
use_kserve: bool = False
```

이 방법은 KServe 없이도 모델 서빙이 가능합니다.

### 옵션 2: KServe 완전 설치 (Knative + Istio 포함)

KServe를 제대로 사용하려면 Knative Serving과 Istio를 설치해야 합니다.

#### 2.1 Knative Serving 설치

```bash
# Knative Serving 설치
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.11.0/serving-core.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.11.0/serving-crds.yaml

# Knative 네트워킹 (Kourier 사용 - Istio 대신)
kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-v1.11.0/kourier.yaml

# Kourier를 기본 ingress로 설정
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'
```

#### 2.2 Istio 설치 (선택사항, Knative와 함께 사용)

```bash
# Istio 설치
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
./bin/istioctl install --set values.defaultRevision=default

# Istio를 Knative ingress로 설정
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"istio.ingress.networking.knative.dev"}}'
```

#### 2.3 KServe 재설치

```bash
# 기존 KServe 삭제
kubectl delete -f https://github.com/kserve/kserve/releases/download/v0.16.0/kserve.yaml

# KServe 재설치
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.16.0/kserve.yaml

# 상태 확인
kubectl get pods -n kserve
kubectl get pods -n knative-serving
```

### 옵션 3: KServe Serverless 모드 (Knative 없이)

KServe v0.11.0+는 Serverless 모드로 Knative 없이도 작동할 수 있습니다.

```bash
# KServe Serverless 설치
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.16.0/kserve-serverless.yaml
```

## 현재 상태 확인

```bash
# KServe 상태 확인
./setup-kserve.sh kserve check

# 또는 수동으로
kubectl get pods -n kserve
kubectl get crd | grep kserve
kubectl get crd | grep knative
kubectl get crd | grep istio
```

## 권장 사항

**개발/테스트 환경:**
- 옵션 1 (Raw Deployment) 사용 권장
- 더 간단하고 빠름
- KServe의 고급 기능이 필요 없음

**프로덕션 환경:**
- 옵션 2 (완전 설치) 또는 옵션 3 (Serverless) 고려
- 트래픽 분할, Canary 배포 등 고급 기능 필요 시

## 참고

- KServe 문서: https://kserve.github.io/website/
- Knative 문서: https://knative.dev/docs/
- Istio 문서: https://istio.io/latest/docs/

