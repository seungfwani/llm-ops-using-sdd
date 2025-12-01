"""Contract tests for catalog endpoints using schemathesis."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemathesis import from_file

from backend.src.api.app import create_app

# Load OpenAPI spec from contracts
schema = from_file("specs/001-document-llm-ops/contracts/catalog.yaml")

app = create_app()
client = TestClient(app)


@pytest.mark.parametrize("case", schema["/catalog/models"]["GET"].as_strategy())
def test_list_models(case):
    """Verify GET /catalog/models returns {status,message,data} envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body
    assert body["status"] in ("success", "fail")


@pytest.mark.parametrize("case", schema["/catalog/models"]["POST"].as_strategy())
def test_create_model(case):
    """Verify POST /catalog/models accepts valid input and returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize(
    "case",
    schema["/catalog/models/{modelId}/versions/{version}/approve"]["POST"].as_strategy(),
)
def test_approve_model(case):
    """Verify approval endpoint enforces {status,message,data} contract."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize("case", schema["/catalog/models/{modelId}/upload"]["POST"].as_strategy())
def test_upload_model_files(case):
    """Verify POST /catalog/models/{modelId}/upload accepts multipart files and returns envelope."""
    # Note: This test may need mocking for object storage
    # For contract testing, we verify the endpoint exists and follows envelope format
    response = case.call(base_url="http://testserver")
    # Accept 200 (success), 400 (validation error), or 404 (model not found)
    assert response.status_code in (200, 400, 404)
    if response.status_code == 200:
        body = response.json()
        assert "status" in body
        assert "message" in body
        assert body["status"] in ("success", "fail")

