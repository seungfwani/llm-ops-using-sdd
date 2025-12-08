# Spec Compliance Report: Training Job Features

## 구현된 기능과 Spec 비교

### 1. Training Job 상태 체크 스케줄러 ⚠️

**구현 내용:**
- APScheduler를 사용한 주기적 상태 동기화 (기본 30초 간격)
- `sync_all_active_jobs()` 메서드로 모든 active job 상태 동기화
- FastAPI lifespan 이벤트로 백그라운드 스케줄러 실행

**Spec 요구사항:**
- ❌ 명시적인 주기적 상태 동기화 요구사항 없음
- ✅ "Supports real-time status monitoring" (line 1150) 언급
- ✅ API 호출 시 상태 동기화는 구현됨 (`get_job()` 메서드)

**결론:** Spec에는 명시되지 않았지만, 실용적인 기능으로 추가됨. Spec 업데이트 권장.

---

### 2. Training Job 완료 후 모델 등록 🔄

**구현 내용:**
- `POST /llm-ops/v1/training/jobs/{jobId}/register-model` API 엔드포인트
- 수동 모델 등록 UI (JobDetail 페이지)
- TrainingJob 모델에 `output_model_storage_uri`, `output_model_entry_id` 필드 추가

**Spec 요구사항:**
- ✅ Line 142: "creates a new model entry in the catalog upon completion" (from-scratch)
- ✅ Line 147: "creates a new base model in the catalog" (pre-training)
- ⚠️ Spec에서는 "upon completion"으로 자동 생성으로 해석 가능
- ❌ 명시적인 API 엔드포인트 요구사항 없음
- ❌ data-model.md에 `output_model_storage_uri`, `output_model_entry_id` 필드 없음

**결론:** Spec의 의도와 다를 수 있음. Spec에서는 자동 생성으로 보이지만, 현재는 수동 등록 방식으로 구현됨. Spec 명확화 필요.

---

### 3. Storage URI 자동 생성 ✅

**구현 내용:**
- `_generate_storage_uri()` 메서드로 자동 생성
- 형식: `s3://{bucket}/models/{sanitized-name}/{version}/`
- 모델 이름 정규화 (소문자, 하이픈 변환)

**Spec 요구사항:**
- ❌ 명시적인 자동 생성 요구사항 없음
- ✅ Line 33 (data-model.md): `storage_uri` 필드 존재
- ✅ Line 73 (spec.md): "stores files in object storage, records the storage URI"

**결론:** Spec에 명시되지 않았지만, 사용자 편의를 위한 합리적인 기능. Spec 업데이트 권장.

---

## 권장 사항

### Spec 업데이트 필요 사항:

1. **Training Job 상태 동기화 (FR-004e 추가 권장)**
   ```
   - **FR-004e**: The platform MUST periodically synchronize training job statuses 
     with Kubernetes scheduler to ensure accurate status reporting. The platform MUST:
     - Sync status of all queued/running jobs at configurable intervals (default: 30s)
     - Update job status (queued → running → succeeded/failed) automatically
     - Continue training execution even if status sync fails (non-blocking)
     - Provide configuration for sync interval via TRAINING_JOB_STATUS_SYNC_INTERVAL
   ```

2. **Training Job 완료 후 모델 등록 (FR-004f 추가 권장)**
   ```
   - **FR-004f**: The platform MUST support registering output models from completed 
     training jobs to the catalog. The platform MUST:
     - Provide POST /llm-ops/v1/training/jobs/{jobId}/register-model API endpoint
     - Support manual model registration through UI after job completion
     - Auto-generate storage URI based on model name and version if not provided
     - Link registered models to training jobs via output_model_entry_id
     - Store training metrics in model evaluation_summary
   ```

3. **Data Model 업데이트 필요**
   - `TrainingJob` 모델에 다음 필드 추가:
     - `output_model_storage_uri (TEXT, nullable)`
     - `output_model_entry_id (UUID, nullable, FK to model_catalog_entries)`

4. **API Contract 업데이트 필요**
   - `training.yaml`에 `/training/jobs/{jobId}/register-model` 엔드포인트 추가

---

## 구현 상태 요약

| 기능 | Spec 요구사항 | 구현 상태 | 비고 |
|------|--------------|----------|------|
| 상태 동기화 스케줄러 | ❌ 없음 | ✅ 구현됨 | Spec 업데이트 권장 |
| 모델 등록 API | ⚠️ 모호함 | ✅ 구현됨 | Spec 명확화 필요 |
| Storage URI 자동 생성 | ❌ 없음 | ✅ 구현됨 | Spec 업데이트 권장 |
| TrainingJob 필드 확장 | ❌ 없음 | ✅ 구현됨 | data-model.md 업데이트 필요 |

---

## 결론

현재 구현된 기능들은:
1. **실용적이고 필요한 기능**들이지만
2. **Spec에 명시적으로 요구되지 않았거나**
3. **Spec의 의도와 다를 수 있습니다**

따라서 Spec을 업데이트하여 이러한 기능들을 명시적으로 포함시키는 것을 권장합니다.
