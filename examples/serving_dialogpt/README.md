# DialogGPT-small Serving Example (huggingface/transformers-pytorch-cpu)

This example shows how to build a simple HTTP serving runtime image for
`microsoft/DialoGPT-small` using the `huggingface/transformers-pytorch-cpu`
base image, and how to plug it into the llm-ops platform as a
`servingRuntimeImage`.

## 1. Build the example image

From the repository root:

```bash
cd examples/serving_dialogpt

# Build a local image
docker build -t dialogpt-serving:latest .
```

If you are using a remote registry (recommended for Kubernetes):

```bash
docker tag dialogpt-serving:latest <your-registry>/dialogpt-serving:latest
docker push <your-registry>/dialogpt-serving:latest
```

## 2. How the server works

- Base image: `huggingface/transformers-pytorch-cpu`
- Server stack: FastAPI + Uvicorn
- Code: `serve_dialogpt.py`
  - Resolves model location from:
    1. `MODEL_STORAGE_URI` (e.g. `s3://models/...` in MinIO/S3)
    2. `MODEL_PATH` (local path)
    3. Fallback: `"microsoft/DialoGPT-small"` from the Hugging Face Hub
  - Exposes:
    - `POST /generate` – simple text generation
    - `GET /health`, `GET /ready` – for liveness/readiness probes

When deployed by the platform, `MODEL_STORAGE_URI` and `AWS_*` environment
variables are injected automatically from the object store configuration,
so the server can load the model directly from MinIO.

## 3. Register and deploy via llm-ops platform

1. **Register the model** (Hugging Face / MinIO) using the existing examples under `examples/` (e.g. `download_and_register_hf_model.py`).

2. **Deploy a serving endpoint** using the API:

```bash
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serving/endpoints \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin" \
  -d '{
    "modelId": "<registered-model-id>",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/dialogpt",
    "minReplicas": 1,
    "maxReplicas": 1,
    "servingRuntimeImage": "<your-registry>/dialogpt-serving:latest",
    "useGpu": false
  }'
```

> Note: `servingRuntimeImage` must match the image name you built/pushed.

3. **Call the example endpoint** after it becomes healthy:

```bash
curl -X POST https://dev.llm-ops.local/llm-ops/v1/serve/dialogpt/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you?",
    "max_new_tokens": 64
  }'
```

## 4. Relation to KServe / deployer

- This image is intentionally simple:
  - It binds to `0.0.0.0:8000`
  - It exposes `/health` and `/ready` for probes
  - It uses `MODEL_STORAGE_URI` and `AWS_*` envs that are already set by
    `backend/src/serving/services/deployer.py`.
- Because of that, it can be used both:
  - In **legacy** Deployment mode, and
  - In **KServe** mode, without any extra runtime-specific logic.


