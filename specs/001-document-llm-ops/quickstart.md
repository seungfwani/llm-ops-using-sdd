# Quickstart: LLM Ops Platform Documentation Alignment

**Branch**: `001-document-llm-ops`  
**Date**: 2025-11-27

---

## 1. Prerequisites

1. Kubernetes clusters `dev`, `stg`, `prod` with GPU nodes (NVIDIA device plugin)
   and ingress controller installed.
2. **KServe installed** in the Kubernetes cluster (recommended for model serving).
   Install KServe using:
   ```bash
   # Install KServe
   kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml
   # Or use KServe operator
   kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve-runtimes.yaml
   ```
3. PostgreSQL 14+ with logical replication enabled for audit log archiving.
4. Object storage bucket (MinIO/S3) reachable from clusters for artifacts and
   experiment outputs.
5. Redis cluster for prompt cache metadata.
6. Prometheus + Grafana stack with service discovery for backend + serving pods.
7. Organization-wide SSO or IdP configured for RBAC integration.

## 2. Bootstrap Steps

1. **Clone & Checkout**
   ```bash
   git clone <repo> && cd llm-ops-platform-cursor
   git checkout 001-document-llm-ops
   ```
2. **Install Tooling**
   ```bash
   cd backend && poetry install
   cd ../frontend && npm install
   cd ..
   ```
3. **Provision Config Secrets**
   - Copy `backend/.env.example` and `frontend/.env.example` to environment-specific
     secret stores covering DB, Redis, object storage, telemetry, and API base URLs.
   - Store training scheduler credentials in sealed secrets per cluster.
   - **Object Storage Setup**: Create bucket named `models` in MinIO/S3 for model file storage:
     ```bash
     # For MinIO
     mc mb minio/models
     mc anonymous set download minio/models
     
     # For AWS S3
     aws s3 mb s3://models
     ```
4. **Apply Infrastructure Manifests**
   ```bash
   # Use deployment script (recommended)
   cd infra/scripts
   ./deploy-all.sh dev
   
   # Or manually
   kubectl apply -k infra/k8s/dependencies
   ```
   Repeat for `stg` and `prod` once smoke tests pass.
5. **Configure Local Development Access** (if running backend locally)
   
   **Important**: If you're running the backend server on your local machine (not in Kubernetes),
   you need to set up port-forwarding to access services in the cluster:
   
   ```bash
   # Option 1: Use automated script (recommended)
   cd infra/scripts
   ./port-forward-all.sh dev
   
   # Option 2: Manual port-forwarding
   kubectl port-forward -n llm-ops-dev svc/postgresql 5432:5432 &
   kubectl port-forward -n llm-ops-dev svc/redis 6379:6379 &
   kubectl port-forward -n llm-ops-dev svc/minio 9000:9000 &
   kubectl port-forward -n llm-ops-dev svc/minio 9001:9001 &
   ```
   
   **Backend .env for local development** (with port-forward):
   ```bash
   DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
   REDIS_URL=redis://localhost:6379/0
   OBJECT_STORE_ENDPOINT=http://localhost:9000
   OBJECT_STORE_ACCESS_KEY=llmops
   OBJECT_STORE_SECRET_KEY=llmops-secret
   OBJECT_STORE_SECURE=false
   ```
   
   **Backend .env for cluster deployment** (backend running in Kubernetes):
   ```bash
   DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/llmops
   REDIS_URL=redis://redis.llm-ops-dev.svc.cluster.local:6379/0
   OBJECT_STORE_ENDPOINT=http://minio.llm-ops-dev.svc.cluster.local:9000
   OBJECT_STORE_ACCESS_KEY=llmops
   OBJECT_STORE_SECRET_KEY=llmops-secret
   OBJECT_STORE_SECURE=false
   ```
6. **Run Database Migrations**
   ```bash
   cd backend
   poetry run alembic upgrade head
   cd ..
   ```
   Applies the SQL-backed Alembic revision aligning with `data-model.md`.
   
   **Note**: If you get "Connection refused" errors, ensure port-forwarding is active
   (see step 5) or that your backend is running in the cluster with correct environment
   variables.
7. **Seed Reference Data**
   - Import baseline models, datasets, and prompt templates via `/llm-ops/v1`
     catalog endpoints.
   - Register governance policies (RBAC roles, data classification).
8. **Deploy Backend & Workers**
   ```bash
   helm upgrade --install catalog backend/helm/catalog -f infra/helm/dev.yaml
   helm upgrade --install trainers backend/helm/trainers -f infra/helm/dev.yaml
   ```
9. **Deploy Frontend**
   ```bash
   npm install --prefix frontend
   npm run build --prefix frontend
   helm upgrade --install ui frontend/helm -f infra/helm/dev.yaml
   ```
10. **Configure Observability**
   - Register services with Prometheus scrape configs.
   - Import Grafana dashboards for latency, error, token, GPU metrics.
11. **Validate API Contracts**
   ```bash
   cd backend
   poetry run pytest tests/contract/ -v
   # Or using schemathesis directly:
   poetry run schemathesis run --base-url=http://localhost:8000/llm-ops/v1 \
     specs/001-document-llm-ops/contracts/*.yaml
   ```
12. **Run Load Tests** (optional, for performance validation)
   ```bash
   # Install k6: https://k6.io/docs/getting-started/installation/
   k6 run --env BASE_URL=http://localhost:8000/llm-ops/v1 \
          --env MODEL_ID=<model-id> \
          --env DATASET_ID=<dataset-id> \
          backend/tests/load/k6_serving_test.js
   k6 run --env BASE_URL=http://localhost:8000/llm-ops/v1 \
          --env MODEL_ID=<model-id> \
          --env DATASET_ID=<dataset-id> \
          backend/tests/load/k6_training_test.js
   ```
   Review output files: `serving_load_test_summary.json`, `training_load_test_summary.json`
13. **Document SDD Updates**
    - Update `docs/Constitution.txt` sections impacted by new features.
    - Link catalog entries to doc anchors for traceability.

## 3. Smoke Test Checklist

- [ ] Catalog POST/GET returns `{status,message,data}` envelope.
- [ ] **Model file upload stores files in object storage and updates catalog entry with storage_uri.**
- [ ] **Catalog UI pages display models with filtering, status updates, and file upload capabilities.**
- [ ] Training job submission triggers Kubernetes job and logs experiment URL.
- [ ] Serving promotion deploys healthy endpoint and records audit entry.
- [ ] **Serving endpoints list returns filtered results by environment/model/status.**
- [ ] **Serving endpoint detail page displays route, health status, scaling config, and model metadata.**
- [ ] Prompt experiment toggles traffic between variants with metrics.
- [ ] Governance policy change reflected in RBAC enforcement within 5 minutes.
- [ ] Cost dashboard shows GPU/token consumption for latest 24h window.

## 4. Deployment & Rollback

### 4.1 Serving Endpoint Deployment

1. **Deploy via API**
   ```bash
   curl -X POST https://dev.llm-ops.local/llm-ops/v1/serving/endpoints \
     -H "Content-Type: application/json" \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin" \
     -d '{
       "modelId": "<approved-model-id>",
       "environment": "dev",
       "route": "/llm-ops/v1/serve/model-name",
       "minReplicas": 1,
       "maxReplicas": 3,
       "autoscalePolicy": {"cpuUtilization": 70}
     }'
   ```

2. **List Endpoints**
   ```bash
   # List all endpoints
   curl https://dev.llm-ops.local/llm-ops/v1/serving/endpoints \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin"
   
   # Filter by environment
   curl "https://dev.llm-ops.local/llm-ops/v1/serving/endpoints?environment=dev" \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin"
   
   # Filter by model and status
   curl "https://dev.llm-ops.local/llm-ops/v1/serving/endpoints?modelId=<model-id>&status=healthy" \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin"
   ```

3. **View Endpoint Details**
   ```bash
   curl https://dev.llm-ops.local/llm-ops/v1/serving/endpoints/<endpoint-id> \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin"
   ```

4. **Verify Deployment**
   ```bash
   # Kubernetes namespace uses llm-ops-{environment} format
   kubectl get deployment serving-<endpoint-id> -n llm-ops-<environment>
   kubectl get hpa serving-<endpoint-id>-hpa -n llm-ops-<environment>
   kubectl get ingress serving-<endpoint-id>-ingress -n llm-ops-<environment>
   
   # Example for dev environment:
   kubectl get deployment serving-<endpoint-id> -n llm-ops-dev
   kubectl get hpa serving-<endpoint-id>-hpa -n llm-ops-dev
   kubectl get ingress serving-<endpoint-id>-ingress -n llm-ops-dev
   ```

5. **Check Health**
   ```bash
   curl https://dev.llm-ops.local/llm-ops/v1/serve/model-name/health
   ```

### 4.2 Prompt A/B Experiment Setup

1. **Create Experiment via API**
   ```bash
   curl -X POST https://dev.llm-ops.local/llm-ops/v1/prompts/experiments \
     -H "Content-Type: application/json" \
     -d '{
       "templateAId": "<template-a-id>",
       "templateBId": "<template-b-id>",
       "allocation": 50,
       "metric": "latency_ms"
     }'
   ```

2. **Monitor Experiment Metrics**
   - View metrics in Grafana dashboard
   - Check experiment status via API: `GET /prompts/experiments/{id}`

3. **Conclude Experiment**
   ```bash
   curl -X POST https://dev.llm-ops.local/llm-ops/v1/prompts/experiments/{id}/conclude \
     -d '{"winnerTemplateId": "<template-id>", "notes": "Template A won"}'
   ```

### 4.3 Model File Upload

The platform supports uploading model files (weights, configs, tokenizers) when registering models in the catalog.

1. **Create Model Entry**
   ```bash
   curl -X POST https://dev.llm-ops.local/llm-ops/v1/catalog/models \
     -H "Content-Type: application/json" \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin" \
     -d '{
       "name": "my-model",
       "version": "1.0.0",
       "type": "base",
       "owner_team": "ml-team",
       "metadata": {"description": "Test model", "framework": "pytorch"}
     }'
   ```

2. **Upload Model Files via API**
   ```bash
   curl -X POST https://dev.llm-ops.local/llm-ops/v1/catalog/models/{model-id}/upload \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin" \
     -F "files=@config.json" \
     -F "files=@pytorch_model.bin" \
     -F "files=@tokenizer.json"
   ```

3. **Upload via Frontend UI**
   - Navigate to `/catalog/models/new` to create a model
   - Use the file upload area to drag-and-drop or select model files
   - Files are uploaded automatically after model creation
   - Or navigate to `/catalog/models/{model-id}` to upload files to an existing model

4. **Verify Upload**
   ```bash
   curl https://dev.llm-ops.local/llm-ops/v1/catalog/models/{model-id} \
     -H "X-User-Id: admin" \
     -H "X-User-Roles: admin"
   ```
   The response will include a `storage_uri` field pointing to the uploaded files.

5. **File Validation**
   - Required files for base/fine-tuned models: `config.json`
   - Allowed file extensions: `.bin`, `.safetensors`, `.json`, `.txt`, `.pt`, `.pth`, `.onnx`
   - Maximum file size: 10GB per file
   - Files are stored in object storage under `models/{model_id}/{version}/`

### 4.4 Rollback Procedures

- Use GitOps pipeline (ArgoCD/Flux) to promote manifests between environments.
- Record deployment diagram deltas and backup verification steps in change
  requests per constitution gate #5.
- For rollback, keep previous Helm release values and object-storage snapshots;
  `helm rollback <release> <revision>` restores services, while catalog version
  snapshots revert metadata.

**Serving Endpoint Rollback:**
```bash
# Via API
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serving/endpoints/{id}/rollback

# Via script (manual)
./infra/scripts/serving_rollback.sh <endpoint-id> [namespace]
```

The rollback script:
- Scales down deployment to 0 replicas
- Deletes HPA, Ingress, Service, and Deployment
- Optionally restores from previous revision if rollback plan exists

## 5. Error Handling & Troubleshooting

### 5.1 Global Error Handling

All API endpoints return HTTP 200 with a standardized envelope:
```json
{
  "status": "success|fail",
  "message": "Error message if status is fail",
  "data": { ... } // Response data if status is success
}
```

Exceptions are caught by `ErrorHandlerMiddleware` and logged with:
- Request path, method, and user ID
- Error category (client_error, server_error)
- Error ID for correlation
- Full stack trace (server-side only)

### 5.2 Common Issues

**Database Connection Errors:**

If you see "Connection refused" errors when connecting to PostgreSQL:

1. **Check if you're running backend locally** (most common case):
   ```bash
   # Verify port-forward is running
   kubectl get pods -n llm-ops-dev
   
   # Start port-forward if not running
   cd infra/scripts
   ./port-forward-all.sh dev
   ```
   
   Ensure your `.env` uses `localhost`:
   ```bash
   DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
   ```

2. **Check if backend is running in cluster**:
   ```bash
   # Verify backend pod is running
   kubectl get pods -n llm-ops-dev -l app=backend
   
   # Check environment variables
   kubectl exec -n llm-ops-dev <backend-pod> -- env | grep DATABASE_URL
   ```
   
   Ensure your `.env` uses cluster DNS:
   ```bash
   DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/llmops
   ```

3. **Test PostgreSQL connectivity**:
   ```bash
   # From local (with port-forward)
   psql postgresql+psycopg://llmops:password@localhost:5432/llmops -c "SELECT 1"
   
   # From cluster
   kubectl exec -n llm-ops-dev deployment/postgresql -- psql -U llmops -d llmops -c "SELECT 1"
   ```

4. **Verify Alembic migrations**:
   ```bash
   cd backend && poetry run alembic current
   ```

5. **Connection test script**:
   ```bash
   cd infra/scripts
   ./test-connections.sh dev
   ```

**Kubernetes Scheduler Errors:**
```bash
# Check kubeconfig
kubectl config current-context

# Verify GPU nodes
kubectl get nodes -l accelerator=nvidia-tesla-v100
```

**RBAC Policy Violations:**
- Check `X-User-Id` and `X-User-Roles` headers are set
- Verify policy status is "active" in governance policies
- Review audit logs: `GET /governance/audit/logs?result=denied`

**Cost Aggregation Not Running:**
```bash
# Check cost aggregator worker logs
kubectl logs -l app=cost-aggregator -n default

# Manually trigger aggregation (if worker supports it)
kubectl exec -it <cost-aggregator-pod> -- python -m backend.workers.evaluators.cost_aggregator
```

## 6. Support & Handover

- On-call rotations own Prometheus/Grafana alerts for latency, error rate, cost
  anomalies, and policy violations.
- Knowledge base entries reference this quickstart plus `research.md` decisions.
- Post-release reviews must confirm success metrics (SC-001–SC-006) are trending
  in observability dashboards before closing the initiative.
- Error handling middleware logs all exceptions with error IDs for correlation.

## 7. Serving Examples & Client Usage

This section provides practical examples for using the serving APIs programmatically. For comprehensive examples, see [`docs/serving-examples.md`](../../docs/serving-examples.md).

### 7.1 Using the Python Client

The platform provides a reusable Python client for interacting with serving endpoints:

```bash
# Install required dependencies
cd backend && pip install requests

# Run example scripts
cd ../examples
python serving_client.py workflow
python serving_client.py deploy
python serving_client.py list
python serving_client.py rollback
```

**Basic Python Client Usage:**

```python
from examples.serving_client import ServingClient

# Initialize client
client = ServingClient(
    base_url="https://dev.llm-ops.local/llm-ops/v1",
    user_id="admin",
    user_roles="admin"
)

# Deploy an endpoint
endpoint = client.deploy_endpoint(
    model_id="your-model-id",
    environment="dev",
    route="/llm-ops/v1/serve/chat-model",
    min_replicas=1,
    max_replicas=3
)

# Wait for healthy status
if client.wait_for_healthy(endpoint["id"], max_wait_seconds=120):
    print("Endpoint is ready!")

# Check health
health = client.check_health("chat-model")
print(f"Health status: {health['status']}")

# List endpoints with filters
endpoints = client.list_endpoints(environment="dev", status="healthy")
for ep in endpoints:
    print(f"{ep['route']}: {ep['status']}")
```

### 7.2 Complete Workflow Example

The following example demonstrates a full workflow from deployment to health check:

```python
from examples.serving_client import ServingClient
import time

client = ServingClient("https://dev.llm-ops.local/llm-ops/v1")

# Step 1: Deploy endpoint
endpoint = client.deploy_endpoint(
    model_id="123e4567-e89b-12d3-a456-426614174000",
    environment="dev",
    route="/llm-ops/v1/serve/my-model",
    min_replicas=1,
    max_replicas=3
)
endpoint_id = endpoint["id"]

# Step 2: Wait for healthy status
print("Waiting for endpoint to be healthy...")
if client.wait_for_healthy(endpoint_id):
    print("✓ Endpoint is healthy")
else:
    print("✗ Timeout waiting for healthy status")
    exit(1)

# Step 3: Verify health check
health = client.check_health("my-model")
print(f"✓ Health check passed: {health['status']}")

# Step 4: List all endpoints
all_endpoints = client.list_endpoints()
print(f"✓ Found {len(all_endpoints)} total endpoints")
```

### 7.3 JavaScript/TypeScript Example

For frontend integration, you can use the serving client directly in TypeScript:

```typescript
import { servingClient } from '@/services/servingClient';

// Deploy endpoint
const endpoint = await servingClient.deployEndpoint({
  modelId: 'your-model-id',
  environment: 'dev',
  route: '/llm-ops/v1/serve/chat-model',
  minReplicas: 1,
  maxReplicas: 3
});

// List endpoints
const endpoints = await servingClient.listEndpoints({
  environment: 'dev',
  status: 'healthy'
});

// Get endpoint details
const details = await servingClient.getEndpoint(endpoint.data.id);

// Rollback endpoint
const rolledBack = await servingClient.rollbackEndpoint(endpoint.data.id);
```

### 7.4 Example Files Reference

- **Python Client**: [`examples/serving_client.py`](../../examples/serving_client.py) - Full-featured Python client with reusable classes
- **Comprehensive Examples**: [`docs/serving-examples.md`](../../docs/serving-examples.md) - Detailed examples for all serving operations
- **Example README**: [`examples/README.md`](../../examples/README.md) - Usage guide for all example files

### 7.5 Model Inference (Planned)

> **Note**: The model inference API (`POST /inference/{model_name}` or `/serve/{model-name}/chat`) is specified in the PRD but not yet implemented. Once available, inference examples will be added to the client library.

**Expected usage (once implemented):**

```python
# Chat completion (future API)
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
]
response = client.call_chat_model("chat-model", messages, temperature=0.7)
print(response)
```

