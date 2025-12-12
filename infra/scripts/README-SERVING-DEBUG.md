# 서빙 엔드포인트 디버깅 가이드

## Pod가 계속 재시작되는 문제

서빙 엔드포인트 Pod가 계속 재시작되는 경우, 다음 단계로 진단하세요.

### 1. Pod 상태 확인

```bash
# Pod 목록 확인
kubectl get pods -n llm-ops-dev | grep serving

# 특정 Pod 상세 정보
kubectl describe pod <pod-name> -n llm-ops-dev
```

### 2. Pod 로그 확인

```bash
# 최신 로그 확인
kubectl logs <pod-name> -n llm-ops-dev

# 이전 컨테이너 로그 확인 (재시작된 경우)
kubectl logs <pod-name> -n llm-ops-dev --previous

# 실시간 로그 스트리밍
kubectl logs -f <pod-name> -n llm-ops-dev
```

### 3. 일반적인 문제와 해결 방법

#### 문제 1: vLLM이 모델을 찾을 수 없음

**증상:**
```
ValueError: Model path does not exist: s3://models/...
```

**원인:**
- 모델 파일이 S3에 없음
- S3 접근 권한 문제
- 모델 경로가 잘못됨

**해결:**
```bash
# 1. 모델 파일이 S3에 있는지 확인
kubectl exec -n llm-ops-dev deployment/minio -- mc ls minio/models/

# 2. S3 접근 권한 확인
kubectl get secret minio-secret -n llm-ops-dev -o yaml

# 3. 모델 카탈로그에서 storage_uri 확인
# API: GET /catalog/models/{model_id}
```

#### 문제 2: vLLM 인자 오류

**증상:**
```
usage: vllm.entrypoints.openai.api_server [-h] --model MODEL [options]
vllm.entrypoints.openai.api_server: error: the following arguments are required: --model
```

**원인:**
- `--model` 인자가 누락됨 (이미 수정됨)

**해결:**
- 최신 코드로 재배포

#### 문제 3: GPU/CUDA 관련 에러

**증상:**
```
libcuda.so.1: cannot open shared object file: No such file or directory
Failed to infer device type
RuntimeError: Failed to infer device type
```

**원인:**
- GPU가 없거나 GPU 드라이버가 설치되지 않음
- vLLM이 기본적으로 GPU를 찾으려고 함

**해결:**
```bash
# CPU-only 모드로 배포 (설정 변경)
# backend/.env 파일에 추가:
USE_GPU=false

# 또는 배포 시 useGpu: false로 설정
```

**자동 설정:**
- `USE_GPU=false`로 설정하면 다음 환경 변수가 자동으로 추가됩니다:
  - `VLLM_LOGGING_LEVEL=DEBUG` - 디버그 로깅 활성화
  - `VLLM_USE_CPU=1` - CPU 모드 강제
  - `CUDA_VISIBLE_DEVICES=""` - CUDA 디바이스 비활성화
  - `--device cpu` 인자 추가

**참고:**
- vLLM의 CPU 모드는 제한적이며, 작은 모델만 지원합니다
- CPU-only 환경에서는 다른 서빙 런타임(예: TGI CPU 버전)을 고려하세요
- 일부 vLLM 버전은 CPU 모드를 지원하지 않을 수 있습니다
- `--device cpu` 인자는 `--model` 인자 **이전**에 위치해야 합니다 (순서 중요!)

**vLLM CPU 모드가 지원되지 않는 경우:**
- vLLM의 일부 버전(특히 nightly 빌드)은 CPU 모드를 지원하지 않을 수 있습니다
- 이 경우 다른 서빙 런타임을 사용하거나, GPU가 있는 노드에서 실행해야 합니다
- 또는 vLLM의 CPU 지원 버전을 사용하세요

#### 문제 4: 리소스 부족

**증상:**
```
Pod Status: Pending
Reason: Insufficient memory/cpu
```

**원인:**
- 클러스터에 충분한 리소스가 없음
- GPU가 필요한데 CPU만 할당됨

**해결:**
```bash
# 리소스 확인
kubectl describe node

# GPU 노드 확인
kubectl get nodes -l accelerator=nvidia-tesla-v100

# CPU-only 모드로 배포 (설정 변경)
# backend/.env: USE_GPU=false
```

#### 문제 5: 모델 로딩 시간 초과

**증상:**
```
Readiness probe failed
Liveness probe failed
```

**원인:**
- 대형 모델 로딩에 시간이 오래 걸림
- Probe 타임아웃이 너무 짧음

**해결:**
- 이미 `initial_delay_seconds`를 60-120초로 설정함
- 더 큰 모델의 경우 추가 조정 필요

### 4. 컨테이너 내부 디버깅

```bash
# 컨테이너에 접속 (디버깅용)
kubectl exec -it <pod-name> -n llm-ops-dev -- /bin/bash

# 환경 변수 확인
kubectl exec <pod-name> -n llm-ops-dev -- env | grep -E "MODEL|AWS"

# 모델 경로 확인
kubectl exec <pod-name> -n llm-ops-dev -- echo $MODEL_STORAGE_URI
```

### 5. S3 접근 테스트

```bash
# MinIO에 접근 가능한지 테스트
kubectl exec -n llm-ops-dev deployment/minio -- mc ls minio/models/

# AWS CLI로 S3 접근 테스트 (Pod 내부에서)
kubectl exec <pod-name> -n llm-ops-dev -- aws s3 ls s3://models/ --endpoint-url $AWS_ENDPOINT_URL
```

### 6. Deployment 재생성

문제가 계속되면 Deployment를 삭제하고 재생성:

```bash
# Deployment 삭제
kubectl delete deployment <deployment-name> -n llm-ops-dev

# API를 통해 재배포
# POST /serving/endpoints
```

### 7. vLLM 특정 문제

#### vLLM이 S3에서 모델을 직접 로드할 수 없는 경우

vLLM은 HuggingFace 모델을 지원하지만, S3 경로를 직접 사용하려면:

1. **모델을 HuggingFace 형식으로 저장**: `config.json`, `model.safetensors` 등이 필요
2. **또는 모델을 먼저 다운로드**: Init Container 사용

**Init Container 추가 예시:**
```yaml
initContainers:
- name: download-model
  image: amazon/aws-cli:latest
  command:
  - sh
  - -c
  - |
    aws s3 sync $MODEL_STORAGE_URI /models --endpoint-url $AWS_ENDPOINT_URL
  env:
  - name: MODEL_STORAGE_URI
    value: "s3://models/..."
  - name: AWS_ENDPOINT_URL
    valueFrom: ...
```

### 8. 로그에서 확인할 주요 메시지

**정상 시작:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**모델 로딩 중:**
```
Loading model weights...
Downloading model files...
```

**에러:**
```
ERROR: Model not found
ERROR: Failed to load model
ValueError: ...
```

### 9. 빠른 체크리스트

- [ ] Pod가 Running 상태인가?
- [ ] 컨테이너가 시작되었는가? (`kubectl logs`로 확인)
- [ ] 모델 파일이 S3에 있는가?
- [ ] S3 접근 권한이 올바른가?
- [ ] 리소스가 충분한가? (메모리, CPU, GPU)
- [ ] GPU가 필요한가? → `USE_GPU=false`로 CPU 모드 사용
- [ ] vLLM 이미지가 올바른가? (`vllm/vllm-openai:nightly`)
- [ ] 환경 변수가 올바르게 설정되었는가?
- [ ] `--device cpu` 인자가 추가되었는가? (GPU 없을 때)

### 10. 추가 도움말

더 자세한 정보는 다음을 참조하세요:
- [vLLM 공식 문서](https://docs.vllm.ai/)
- [Kubernetes Pod 디버깅](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)

