# Fine-tuning 예제 데이터셋

이 디렉토리에는 fine-tuning을 테스트하기 위한 샘플 데이터셋 파일들이 포함되어 있습니다.

## 데이터셋 파일

### 1. customer-support-sample.csv
- **용도**: Customer support 챗봇 fine-tuning
- **형식**: CSV (instruction, response 컬럼)
- **크기**: 10개 샘플
- **설명**: 고객 지원 대화 데이터셋 예제

**사용 예제:**
```bash
# 데이터셋 생성 후 업로드
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/datasets/{dataset_id}/upload" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -F "files=@examples/datasets/customer-support-sample.csv"
```

### 2. code-generation-sample.jsonl
- **용도**: Code generation 모델 fine-tuning
- **형식**: JSONL (각 줄이 JSON 객체)
- **크기**: 10개 샘플
- **설명**: Python 코드 생성 예제 데이터셋

**사용 예제:**
```bash
# 데이터셋 생성 후 업로드
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/datasets/{dataset_id}/upload" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -F "files=@examples/datasets/code-generation-sample.jsonl"
```

## Fine-tuning 워크플로우

### 1. Base 모델 등록
```bash
# Base 모델 등록 (예: gpt-4-base)
python examples/register_base_model.py register
```

또는 API로:
```bash
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/models" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "name": "gpt-4-base",
    "version": "1.0",
    "type": "base",
    "ownerTeam": "ml-platform",
    "metadata": {
      "architecture": "transformer",
      "parameters": "175B",
      "framework": "pytorch"
    }
  }'
```

### 2. 데이터셋 생성 및 업로드
```bash
# 1. 데이터셋 생성
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/datasets" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "name": "customer-support-dataset",
    "version": "v1.0",
    "ownerTeam": "ml-platform"
  }'

# 2. 데이터셋 파일 업로드
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/datasets/{dataset_id}/upload" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -F "files=@examples/datasets/customer-support-sample.csv"
```

### 3. Fine-tuning Job 제출
```bash
curl -X POST "http://localhost:8000/llm-ops/v1/training/jobs" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "modelId": "{base_model_id}",
    "datasetId": "{dataset_id}",
    "jobType": "finetune",
    "useGpu": false,
    "resourceProfile": {
      "cpuCores": 4,
      "memory": "8Gi",
      "maxDuration": 60
    }
  }'
```

또는 UI에서:
1. `/training/jobs/submit` 페이지로 이동
2. Job Type: "Fine-tuning" 선택
3. Base Model 선택 (예: gpt-4-base)
4. Dataset 선택 (예: customer-support-dataset)
5. Use GPU Resources 체크 해제 (CPU-only 테스트용)
6. Submit Job 클릭

## 데이터셋 형식

### CSV 형식
```csv
instruction,response
"Customer: 질문 내용","응답 내용"
```

### JSONL 형식
각 줄이 독립적인 JSON 객체:
```json
{"instruction": "질문 또는 지시사항", "response": "응답 또는 코드"}
```

## 참고사항

- 이 예제 데이터셋은 테스트 목적으로만 사용됩니다
- 실제 fine-tuning을 위해서는 더 많은 데이터가 필요합니다 (수백~수천 개 샘플)
- 데이터셋은 승인(approved) 상태여야 training job에 사용할 수 있습니다
- CPU-only training (`useGpu=false`)은 개발/테스트 목적으로 사용 가능합니다

## 추가 리소스

- [Training API 문서](../../specs/001-document-llm-ops/spec.md#training-api)
- [Dataset Management API](../../specs/001-document-llm-ops/spec.md#dataset-management-apis)
- [Quickstart 가이드](../../specs/001-document-llm-ops/quickstart.md)


