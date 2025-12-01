# Implementation Plan: Catalog UI Enhancement & Model File Upload

**Branch**: `001-document-llm-ops` | **Date**: 2025-01-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification additions for catalog UI pages (FR-001b) and model file upload (FR-001a)

## Summary

This plan addresses two enhancements to the catalog system:
1. **Catalog UI Pages Enhancement (FR-001b)**: Improve the frontend catalog pages with table-based listing, filtering, detailed model views, and status management capabilities.
2. **Model File Upload (FR-001a)**: Add support for uploading actual model files (weights, configs, tokenizers) to object storage when registering models.

**Status**: ✅ **PARTIALLY COMPLETED** - Catalog UI pages are implemented. Model file upload API is pending.

## Technical Context

**Language/Version**: 
- Frontend: TypeScript 5.x, Vue 3.x
- Backend: Python 3.11+, FastAPI

**Primary Dependencies**: 
- Frontend: Vue 3, Vue Router, axios
- Backend: FastAPI, SQLAlchemy, boto3 (for object storage)

**Storage**: 
- PostgreSQL (model metadata)
- MinIO/S3 (model files via object storage)

**Testing**: 
- Frontend: Playwright (E2E), Vitest (unit)
- Backend: pytest, schemathesis (contract tests)

**Target Platform**: 
- Web application (browser-based UI)
- Linux server (backend API)

**Project Type**: Web application (frontend + backend)

**Performance Goals**: 
- Model list page: Load < 2 seconds for 1000+ models
- File upload: Support files up to 10GB with progress tracking
- Status updates: < 500ms response time

**Constraints**: 
- Must maintain backward compatibility with existing catalog API
- File uploads must support resumable uploads for large files
- UI must work on modern browsers (Chrome, Firefox, Safari, Edge)

**Scale/Scope**: 
- 3 new/updated Vue pages (ModelList, ModelDetail, ModelCreate)
- 1 new API endpoint (POST /catalog/models/{model_id}/upload)
- 1 database migration (add storage_uri to ModelCatalogEntry)
- Object storage integration for model artifacts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. ✅ **Structured SDD Ownership** — Catalog UI pages and model file upload are documented in spec.md with acceptance scenarios, functional requirements (FR-001a, FR-001b), and UI component references. SDD sections 1-3 cover catalog governance.

2. ✅ **Architecture Transparency** — Component structure is clear:
   - Frontend: Vue pages in `frontend/src/pages/catalog/`
   - Backend: API routes in `backend/src/api/routes/catalog.py`
   - Object storage: MinIO/S3 via `backend/src/core/clients/object_store.py`
   - Data model: `ModelCatalogEntry` with `storage_uri` field

3. ✅ **Interface Contract Fidelity** — All endpoints follow `/llm-ops/v1` contract:
   - Standard `{status,message,data}` response envelope
   - HTTP 200 for success, 4xx/5xx for errors
   - Contract defined in `specs/001-document-llm-ops/contracts/catalog.yaml`

4. ✅ **Non-Functional Safeguards** — Performance goals defined above. Security: File upload validation, size limits, type checking. Monitoring: Upload progress, error logging, storage metrics.

5. ⚠️ **Operations-Ready Delivery** — Deployment notes needed:
   - Object storage bucket configuration (DEV/STG/PROD)
   - File upload size limits per environment
   - Storage cleanup policies for deprecated models

**Gate Status**: ✅ **PASS** with minor note on operations configuration (non-blocking)

## Project Structure

### Documentation (this feature)

```text
specs/001-document-llm-ops/
├── plan.md              # This file
├── spec.md              # Feature specification (updated)
├── data-model.md        # Data model (updated with storage_uri)
├── contracts/           # API contracts (updated with upload endpoint)
│   └── catalog.yaml
└── tasks.md             # Implementation tasks (to be generated)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── routes/
│   │       └── catalog.py          # Updated with upload endpoint
│   ├── catalog/
│   │   ├── models.py                # Updated with storage_uri field
│   │   ├── schemas.py               # Updated with storage_uri
│   │   └── services/
│   │       └── catalog.py           # Updated with upload logic
│   └── core/
│       └── clients/
│           └── object_store.py      # Existing (to be used)
└── alembic/
    └── versions/                     # New migration for storage_uri

frontend/
├── src/
│   ├── pages/
│   │   └── catalog/
│   │       ├── ModelList.vue         # ✅ Implemented
│   │       ├── ModelDetail.vue       # ✅ Implemented
│   │       └── ModelCreate.vue       # ✅ Implemented
│   └── services/
│       └── catalogClient.ts          # ✅ Updated with updateModelStatus
└── tests/
    └── catalog.spec.ts               # Existing tests
```

**Structure Decision**: Web application structure (frontend + backend) is already established. This enhancement adds new pages and extends existing API endpoints.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations identified. All changes follow existing patterns and conventions.

## Phase 0: Outline & Research

### Research Tasks

1. **File Upload Best Practices**
   - Research: Multipart upload patterns for large files (10GB+)
   - Decision: Use FastAPI's `UploadFile` with streaming to object storage
   - Alternatives: Direct S3 presigned URLs (rejected - requires client-side S3 SDK)

2. **Object Storage Path Structure**
   - Research: Optimal path structure for model versioning
   - Decision: `models/{model_id}/{version}/` structure
   - Rationale: Supports versioning and easy cleanup of deprecated versions

3. **File Validation Requirements**
   - Research: Required files for different model types (base, fine-tuned, external)
   - Decision: Configurable validation per model type
   - Rationale: External models may have different file structures

**Output**: research.md (if needed, otherwise decisions documented inline)

## Phase 1: Design & Contracts

### Data Model Updates

**ModelCatalogEntry** (existing entity, add field):
- `storage_uri (string, nullable)` - URI to model artifacts in object storage
  - Format: `s3://bucket/models/{model_id}/{version}/` or `minio://...`
  - Nullable: Models can exist without files (metadata-only entries)

**Migration Required**: Add `storage_uri` column to `model_catalog_entries` table.

### API Contracts

**New Endpoint**: `POST /catalog/models/{model_id}/upload`
- Request: `multipart/form-data` with file fields
- Response: `{status, message, data: {modelId, storageUri, uploadedFiles[]}}`
- Errors: 400 (invalid files), 404 (model not found), 413 (file too large)

**Updated Endpoint**: `GET /catalog/models/{model_id}`
- Response now includes `storageUri` field in model data

**Updated Endpoint**: `PATCH /catalog/models/{model_id}/status`
- Already implemented in frontend, documented in contracts

**Contract File**: `specs/001-document-llm-ops/contracts/catalog.yaml` (updated)

### Frontend Components

**ModelList.vue** (✅ Implemented):
- Table-based listing with filtering
- Status/type badges
- Navigation to detail pages

**ModelDetail.vue** (✅ Implemented):
- Complete model information display
- Status update dropdown
- Metadata JSON viewer

**ModelCreate.vue** (✅ Implemented):
- Form-based creation
- JSON metadata editor
- Lineage dataset IDs input

**catalogClient.ts** (✅ Updated):
- `updateModelStatus()` method added

### Quickstart Updates

Update `quickstart.md` with:
- Object storage bucket setup instructions
- Model file upload workflow example
- Catalog UI navigation guide

**Output**: 
- ✅ data-model.md (updated)
- ✅ contracts/catalog.yaml (updated)
- ⏳ quickstart.md (needs update)

## Phase 2: Implementation Tasks

**Note**: This phase is handled by `/speckit.tasks` command. Tasks will include:

1. Database migration for `storage_uri` field
2. Backend API endpoint for file upload
3. Object storage integration
4. File validation logic
5. Frontend file upload UI (if not already in ModelCreate/ModelDetail)
6. Progress tracking for large uploads
7. Error handling and retry logic
8. Contract tests for upload endpoint
9. E2E tests for catalog UI workflows

## Next Steps

1. **Immediate**: 
   - ✅ Catalog UI pages are implemented
   - ⏳ Model file upload API needs implementation
   - ⏳ Database migration for `storage_uri` field

2. **When File Upload is Implemented**:
   - Add file upload UI to ModelCreate and ModelDetail pages
   - Add progress indicators
   - Add file validation feedback

3. **Future Enhancements** (if needed):
   - Resumable uploads for very large files
   - Batch file uploads
   - File preview/validation before upload
   - HuggingFace model import integration

## References

- **Spec**: [spec.md](./spec.md#catalog-ui-pages) and [spec.md](./spec.md#model-file-upload)
- **Data Model**: [data-model.md](./data-model.md#modelcatalogentry)
- **Contracts**: [contracts/catalog.yaml](./contracts/catalog.yaml)
- **Frontend Pages**: 
  - [ModelList.vue](../../frontend/src/pages/catalog/ModelList.vue)
  - [ModelDetail.vue](../../frontend/src/pages/catalog/ModelDetail.vue)
  - [ModelCreate.vue](../../frontend/src/pages/catalog/ModelCreate.vue)
