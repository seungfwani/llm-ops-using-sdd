"""Contract tests for serving endpoints using schemathesis."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemathesis import from_file

from backend.src.api.app import create_app

# Load OpenAPI spec from contracts
schema = from_file("specs/001-document-llm-ops/contracts/serving.yaml")

app = create_app()
client = TestClient(app)


@pytest.mark.parametrize("case", schema["/serving/endpoints"]["GET"].as_strategy())
def test_list_endpoints(case):
    """Verify GET /serving/endpoints returns {status,message,data} envelope with list."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body
    assert body["status"] in ("success", "fail")
    if body["status"] == "success" and body["data"] is not None:
        assert isinstance(body["data"], list)


@pytest.mark.parametrize("case", schema["/serving/endpoints"]["POST"].as_strategy())
def test_deploy_endpoint(case):
    """Verify POST /serving/endpoints returns {status,message,data} envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body
    assert body["status"] in ("success", "fail")


@pytest.mark.parametrize("case", schema["/serving/endpoints/{endpointId}"]["GET"].as_strategy())
def test_get_endpoint(case):
    """Verify GET /serving/endpoints/{endpointId} returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize("case", schema["/serving/endpoints/{endpointId}/rollback"]["POST"].as_strategy())
def test_rollback_endpoint(case):
    """Verify POST /serving/endpoints/{endpointId}/rollback returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body

