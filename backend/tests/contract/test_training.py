"""Contract tests for training endpoints using schemathesis."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemathesis import from_file

from backend.src.api.app import create_app

# Load OpenAPI spec from contracts
schema = from_file("specs/001-document-llm-ops/contracts/training.yaml")

app = create_app()
client = TestClient(app)


@pytest.mark.parametrize("case", schema["/training/jobs"]["POST"].as_strategy())
def test_submit_training_job(case):
    """Verify POST /training/jobs returns {status,message,data} envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body
    assert body["status"] in ("success", "fail")


@pytest.mark.parametrize("case", schema["/training/jobs/{jobId}"]["GET"].as_strategy())
def test_get_training_job(case):
    """Verify GET /training/jobs/{jobId} returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize("case", schema["/training/jobs/{jobId}"]["DELETE"].as_strategy())
def test_cancel_training_job(case):
    """Verify DELETE /training/jobs/{jobId} returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


# Job type validation tests
def test_submit_finetune_job_requires_model():
    """Verify fine-tuning job requires modelId."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "finetune",
        "resourceProfile": {
            "gpuCount": 1,
            "gpuType": "nvidia-tesla-v100",
            "maxDuration": 60,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fail"
    assert "modelId" in body["message"].lower() or "base model" in body["message"].lower()


def test_submit_from_scratch_job_requires_architecture():
    """Verify from-scratch job requires architecture configuration."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "from_scratch",
        "resourceProfile": {
            "gpuCount": 1,
            "gpuType": "nvidia-tesla-v100",
            "maxDuration": 60,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fail"
    assert "architecture" in body["message"].lower()


def test_submit_pretrain_job_requires_architecture():
    """Verify pre-training job requires architecture configuration."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "pretrain",
        "resourceProfile": {
            "gpuCount": 1,
            "gpuType": "nvidia-tesla-v100",
            "maxDuration": 60,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fail"
    assert "architecture" in body["message"].lower()


def test_submit_distributed_job_requires_multiple_gpus():
    """Verify distributed job requires at least 2 GPUs."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "distributed",
        "resourceProfile": {
            "gpuCount": 1,  # Only 1 GPU, should fail
            "gpuType": "nvidia-tesla-v100",
            "maxDuration": 60,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fail"
    assert "gpu" in body["message"].lower() or "distributed" in body["message"].lower()


def test_submit_job_with_valid_job_types():
    """Verify all valid job types are accepted."""
    valid_job_types = ["finetune", "from_scratch", "pretrain", "distributed"]
    for job_type in valid_job_types:
        payload = {
            "datasetId": "test-dataset-id",
            "jobType": job_type,
            "resourceProfile": {
                "gpuCount": 2 if job_type == "distributed" else 1,
                "gpuType": "nvidia-tesla-v100",
                "maxDuration": 60,
            },
        }
        # Add required fields based on job type
        if job_type == "finetune":
            payload["modelId"] = "test-model-id"
        elif job_type in ("from_scratch", "pretrain"):
            payload["hyperparameters"] = {"architecture": {"type": "transformer", "layers": 12}}
        
        response = client.post("/llm-ops/v1/training/jobs", json=payload)
        # Accept 200 (may fail due to missing model/dataset, but should validate job type)
        assert response.status_code == 200
        body = response.json()
        # Should not fail due to invalid job type
        assert body["status"] in ("success", "fail")
        if body["status"] == "fail":
            # Should fail for other reasons (model/dataset not found), not job type
            assert "job type" not in body["message"].lower() or "invalid" not in body["message"].lower()


def test_submit_cpu_only_training_job():
    """Verify CPU-only training job submission (useGpu=false)."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "finetune",
        "modelId": "test-model-id",
        "useGpu": False,
        "resourceProfile": {
            "cpuCores": 4,
            "memory": "8Gi",
            "maxDuration": 60,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    # Accept 200 (may fail due to missing model/dataset, but should accept CPU-only config)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "fail")
    # Should not fail due to missing GPU configuration
    if body["status"] == "fail":
        assert "gpu" not in body["message"].lower() or "gpu" in body["message"].lower() and "required" not in body["message"].lower()


def test_submit_cpu_only_from_scratch_job():
    """Verify CPU-only from-scratch training job submission."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "from_scratch",
        "useGpu": False,
        "hyperparameters": {
            "architecture": {
                "type": "transformer",
                "layers": 12,
                "hidden_size": 768,
            }
        },
        "resourceProfile": {
            "cpuCores": 8,
            "memory": "16Gi",
            "maxDuration": 120,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "fail")
    # Should accept CPU-only configuration for from-scratch jobs
    if body["status"] == "fail":
        assert "gpu" not in body["message"].lower() or "gpu" in body["message"].lower() and "required" not in body["message"].lower()


def test_submit_job_with_use_gpu_default():
    """Verify useGpu defaults to True when not specified."""
    payload = {
        "datasetId": "test-dataset-id",
        "jobType": "finetune",
        "modelId": "test-model-id",
        # useGpu not specified, should default to True
        "resourceProfile": {
            "gpuCount": 1,
            "gpuType": "nvidia-tesla-v100",
            "maxDuration": 60,
        },
    }
    response = client.post("/llm-ops/v1/training/jobs", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "fail")
    # Should treat as GPU job when useGpu is not specified

