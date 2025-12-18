# Serving Endpoint DB 저장 항목 정리

## serving_endpoints 테이블에 저장되는 항목

### 기본 필드 (항상 저장)
- `id` (UUID, Primary Key)
- `model_entry_id` (UUID, Foreign Key to model_catalog_entries)
- `environment` (TEXT, 'dev'|'stg'|'prod')
- `route` (TEXT, Ingress route path)
- `status` (TEXT, 'deploying'|'healthy'|'degraded'|'failed')
- `min_replicas` (INTEGER, 기본값: 1)
- `max_replicas` (INTEGER, 기본값: 1)
- `created_at` (TIMESTAMPTZ)

### 선택적 필드 (제공되면 저장)
- `runtime_image` (TEXT) - 컨테이너 이미지
- `autoscale_policy` (JSONB) - 자동 스케일링 정책
  - `targetLatencyMs` (number, optional)
  - `gpuUtilization` (number, optional)
  - `cpuUtilization` (number, optional)
- `prompt_policy_id` (UUID, Foreign Key to prompt_templates)
- `use_gpu` (BOOLEAN) - GPU 사용 여부
- `cpu_request` (TEXT) - CPU 요청량 (예: "2", "1000m")
- `cpu_limit` (TEXT) - CPU 제한 (예: "4", "2000m")
- `memory_request` (TEXT) - 메모리 요청량 (예: "4Gi", "2G")
- `memory_limit` (TEXT) - 메모리 제한 (예: "8Gi", "4G")
- `deployment_spec` (JSONB) - DeploymentSpec JSON (training-serving-spec.md 기반)
- `last_health_check` (TIMESTAMPTZ)
- `rollback_plan` (TEXT)

## deployment_spec JSON에 저장되는 항목

DeploymentSpec은 `deployment_spec` JSONB 컬럼에 저장됩니다.

### 필수 필드
- `model_ref` (string) - 모델 참조 (예: "llama-3-8b-sft-v1")
- `model_family` (string) - 모델 패밀리 (예: "llama", "mistral", "gemma")
- `job_type` (string) - 작업 타입 ("SFT"|"RAG_TUNING"|"RLHF"|"PRETRAIN"|"EMBEDDING")
- `serve_target` (string) - 서빙 타겟 ("GENERATION"|"RAG")
- `resources` (object)
  - `gpus` (number) - GPU 개수
  - `gpu_memory_gb` (number, optional) - GPU 메모리 (GB)
- `runtime` (object)
  - `max_concurrent_requests` (number) - 최대 동시 요청 수
  - `max_input_tokens` (number) - 최대 입력 토큰 수
  - `max_output_tokens` (number) - 최대 출력 토큰 수
- `use_gpu` (boolean) - GPU 사용 여부

### 선택적 필드
- `rollout` (object, optional) - 롤아웃 전략
  - `strategy` (string) - "blue-green"|"canary"
  - `traffic_split` (object, optional) - 트래픽 분할
    - `old` (number) - 이전 버전 비율 (%)
    - `new` (number) - 새 버전 비율 (%)

## 저장 흐름

### 배포 시 (deploy_endpoint)
1. 기본 필드 저장 (id, model_entry_id, environment, route, status, min_replicas, max_replicas)
2. runtime_image 저장 (DeploymentSpec 또는 설정에서 결정)
3. autoscale_policy 저장 (제공된 경우)
4. prompt_policy_id 저장 (제공된 경우)
5. use_gpu 저장 (DeploymentSpec 또는 파라미터에서 결정)
6. cpu_request, cpu_limit, memory_request, memory_limit 저장 (제공된 경우)
7. deployment_spec 저장 (제공된 경우, model_family와 job_type 포함)

### 재배포 시 (redeploy_endpoint)
1. 기존 endpoint 업데이트
2. 새로운 설정으로 위 항목들 업데이트
3. deployment_spec이 제공되면 업데이트, 없으면 기존 값 유지 또는 모델 메타데이터에서 재구성

## 확인 사항

✅ `model_family` - deployment_spec JSON에 저장됨
✅ `job_type` - deployment_spec JSON에 저장됨
✅ `use_gpu` - 별도 컬럼과 deployment_spec JSON 둘 다 저장됨
✅ `autoscale_policy` - 별도 JSONB 컬럼에 저장됨
✅ `cpu_request`, `cpu_limit`, `memory_request`, `memory_limit` - 별도 컬럼에 저장됨
✅ `runtime_image` - 별도 컬럼에 저장됨
✅ `deployment_spec` - JSONB 컬럼에 전체 DeploymentSpec 저장됨

## serving_deployments 테이블에 저장되는 항목

`serving_framework`는 별도의 `serving_deployments` 테이블에 저장됩니다.

### 기본 필드
- `id` (UUID, Primary Key)
- `serving_endpoint_id` (UUID, Foreign Key to serving_endpoints)
- `serving_framework` (TEXT) - 서빙 프레임워크 이름 (예: "kserve", "ray_serve")
- `framework_resource_id` (TEXT) - 프레임워크 리소스 ID
- `framework_namespace` (TEXT) - Kubernetes 네임스페이스
- `replica_count` (INTEGER) - 현재 레플리카 수
- `min_replicas` (INTEGER) - 최소 레플리카 수
- `max_replicas` (INTEGER) - 최대 레플리카 수
- `created_at` (TIMESTAMPTZ)
- `updated_at` (TIMESTAMPTZ)

### 선택적 필드
- `autoscaling_metrics` (JSON) - 자동 스케일링 메트릭
- `resource_requests` (JSON) - 리소스 요청량
- `resource_limits` (JSON) - 리소스 제한
- `framework_status` (JSON) - 프레임워크 상태

## 주의사항

- `deployment_spec`이 없어도 배포는 가능하지만, 재배포 시 모델 메타데이터에서 재구성 시도
- `model_family`와 `job_type`은 deployment_spec 내부에만 저장되며, 별도 컬럼은 없음
- `serving_framework`는 `serving_deployments` 테이블에 저장됨 (별도 테이블, ServingEndpoint와 1:1 관계)
- `serving_deployments`는 Kubernetes 배포 후 생성되며, 배포 실패 시 생성되지 않을 수 있음

