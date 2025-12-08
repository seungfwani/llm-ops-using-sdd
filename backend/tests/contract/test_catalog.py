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


# Dataset endpoint contract tests
# These endpoints may not be in the OpenAPI spec yet, so we test them directly


def test_upload_dataset_files():
    """Verify POST /catalog/datasets/{dataset_id}/upload accepts multipart files and returns envelope."""
    # Create a test dataset first
    dataset_payload = {
        "name": "test-dataset",
        "version": "1.0.0",
        "owner_team": "test-team",
    }
    create_response = client.post("/llm-ops/v1/catalog/datasets", json=dataset_payload)
    # Accept 201 (created) or 200 (success)
    assert create_response.status_code in (200, 201)
    create_body = create_response.json()
    assert "status" in create_body
    assert "data" in create_body
    
    if create_body["status"] == "success" and create_body["data"]:
        dataset_id = create_body["data"]["id"]
        
        # Test file upload
        files = [("files", ("test.csv", b"col1,col2\nval1,val2", "text/csv"))]
        upload_response = client.post(
            f"/llm-ops/v1/catalog/datasets/{dataset_id}/upload",
            files=files,
        )
        # Accept 200 (success), 400 (validation error), or 404 (dataset not found)
        assert upload_response.status_code in (200, 400, 404)
        if upload_response.status_code == 200:
            body = upload_response.json()
            assert "status" in body
            assert "message" in body
            assert "data" in body
            assert body["status"] in ("success", "fail")


def test_get_dataset_preview():
    """Verify GET /catalog/datasets/{dataset_id}/preview returns {status,message,data} envelope."""
    # Create a test dataset first
    dataset_payload = {
        "name": "test-dataset-preview",
        "version": "1.0.0",
        "owner_team": "test-team",
    }
    create_response = client.post("/llm-ops/v1/catalog/datasets", json=dataset_payload)
    assert create_response.status_code in (200, 201)
    create_body = create_response.json()
    
    if create_body["status"] == "success" and create_body["data"]:
        dataset_id = create_body["data"]["id"]
        
        # Test preview endpoint
        preview_response = client.get(
            f"/llm-ops/v1/catalog/datasets/{dataset_id}/preview?limit=10"
        )
        # Accept 200 (success) or 404 (dataset not found)
        assert preview_response.status_code in (200, 404)
        if preview_response.status_code == 200:
            body = preview_response.json()
            assert "status" in body
            assert "message" in body
            assert "data" in body
            assert body["status"] in ("success", "fail")


def test_get_dataset_validation():
    """Verify GET /catalog/datasets/{dataset_id}/validation returns {status,message,data} envelope."""
    # Create a test dataset first
    dataset_payload = {
        "name": "test-dataset-validation",
        "version": "1.0.0",
        "owner_team": "test-team",
    }
    create_response = client.post("/llm-ops/v1/catalog/datasets", json=dataset_payload)
    assert create_response.status_code in (200, 201)
    create_body = create_response.json()
    
    if create_body["status"] == "success" and create_body["data"]:
        dataset_id = create_body["data"]["id"]
        
        # Test validation endpoint
        validation_response = client.get(
            f"/llm-ops/v1/catalog/datasets/{dataset_id}/validation"
        )
        # Accept 200 (success) or 404 (dataset not found)
        assert validation_response.status_code in (200, 404)
        if validation_response.status_code == 200:
            body = validation_response.json()
            assert "status" in body
            assert "message" in body
            assert "data" in body
            assert body["status"] in ("success", "fail")


def test_compare_dataset_versions():
    """Verify GET /catalog/datasets/{dataset_id}/versions/{version1}/compare/{version2} returns {status,message,data} envelope."""
    # Create a test dataset first
    dataset_payload = {
        "name": "test-dataset-compare",
        "version": "1.0.0",
        "owner_team": "test-team",
    }
    create_response = client.post("/llm-ops/v1/catalog/datasets", json=dataset_payload)
    assert create_response.status_code in (200, 201)
    create_body = create_response.json()
    
    if create_body["status"] == "success" and create_body["data"]:
        dataset_id = create_body["data"]["id"]
        version1 = create_body["data"]["version"]
        version2 = "2.0.0"  # Use a different version for comparison
        
        # Test version comparison endpoint
        compare_response = client.get(
            f"/llm-ops/v1/catalog/datasets/{dataset_id}/versions/{version1}/compare/{version2}"
        )
        # Accept 200 (success), 400 (validation error), or 404 (dataset/version not found)
        assert compare_response.status_code in (200, 400, 404)
        if compare_response.status_code == 200:
            body = compare_response.json()
            assert "status" in body
            assert "message" in body
            assert "data" in body
            assert body["status"] in ("success", "fail")

