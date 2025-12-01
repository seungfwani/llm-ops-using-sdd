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

