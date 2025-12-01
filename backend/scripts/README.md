# Database Seeding Scripts

## Overview

이 디렉토리에는 개발 및 테스트를 위한 샘플 데이터를 생성하는 스크립트가 포함되어 있습니다.

## Prerequisites

1. 데이터베이스가 실행 중이어야 합니다
2. 데이터베이스 마이그레이션이 완료되어야 합니다 (테이블이 생성되어 있어야 함)
3. Python 환경이 설정되어 있어야 합니다

## Usage

### 시드 데이터 생성

데이터베이스에 샘플 데이터를 생성하려면:

```bash
# backend 디렉토리에서 실행
cd backend
python scripts/seed_data.py
```

또는 직접 실행:

```bash
python backend/scripts/seed_data.py
```

### 생성되는 데이터

스크립트는 다음 샘플 데이터를 생성합니다:

- **Datasets (4개)**
  - customer-support-dataset v1.0 (approved)
  - code-generation-dataset v2.1 (approved)
  - translation-dataset v1.5 (approved)
  - qa-dataset v1.0 (pending approval)

- **Models (5개)**
  - gpt-4-base v1.0 (base, approved)
  - customer-support-finetuned v2.0 (fine-tuned, approved)
  - code-assistant v1.5 (fine-tuned, approved)
  - translation-model v1.0 (fine-tuned, under_review)
  - claude-3-opus v1.0 (external, approved)

- **Prompt Templates (3개)**
  - customer-support-prompt v1.0
  - customer-support-prompt-v2.0
  - code-generation-prompt v1.0

- **Training Jobs (4개)**
  - 다양한 상태 (succeeded, running, failed)
  - 실험 메트릭 포함

- **Serving Endpoints (3개)**
  - prod, stg, dev 환경
  - Observability 스냅샷 포함

- **Governance Policies (4개)**
  - 다양한 스코프 (catalog, training, serving)
  - active 및 draft 상태

- **Audit Logs (5개)**
  - 다양한 액션 및 결과

- **Cost Profiles**
  - Training jobs 및 serving endpoints에 대한 비용 데이터

- **Prompt Experiments**
  - A/B 테스트 실험 데이터

## 데이터베이스 초기화

기존 데이터를 삭제하고 새로 시작하려면:

```bash
# 주의: 이 명령은 모든 데이터를 삭제합니다!
# PostgreSQL에 직접 연결하여 테이블을 truncate하거나
# 데이터베이스를 재생성해야 합니다
```

또는 Alembic을 사용하여 데이터베이스를 재생성:

```bash
# 데이터베이스 드롭 및 재생성 (주의!)
alembic downgrade base
alembic upgrade head
python scripts/seed_data.py
```

## Troubleshooting

### Import 오류

`ModuleNotFoundError`가 발생하면:

```bash
# backend 디렉토리에서 실행하거나
# PYTHONPATH를 설정
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend/src"
python scripts/seed_data.py
```

### 데이터베이스 연결 오류

`.env` 파일에 올바른 데이터베이스 URL이 설정되어 있는지 확인:

```env
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
```

### Foreign Key 제약 조건 오류

데이터가 이미 존재하는 경우, 중복 키 오류가 발생할 수 있습니다. 
기존 데이터를 삭제하거나 스크립트를 수정하여 중복 체크를 추가하세요.

## Customization

스크립트를 수정하여 자신만의 샘플 데이터를 생성할 수 있습니다.
`seed_data.py` 파일을 열고 각 `seed_*` 함수를 수정하세요.

