"""Contract tests for governance endpoints using schemathesis."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from schemathesis import from_file

from backend.src.api.app import create_app

# Load OpenAPI spec from contracts
schema = from_file("specs/001-document-llm-ops/contracts/governance.yaml")

app = create_app()
client = TestClient(app)


@pytest.mark.parametrize("case", schema["/governance/policies"]["POST"].as_strategy())
def test_create_policy(case):
    """Verify POST /governance/policies returns {status,message,data} envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body
    assert body["status"] in ("success", "fail")


@pytest.mark.parametrize("case", schema["/governance/policies"]["GET"].as_strategy())
def test_list_policies(case):
    """Verify GET /governance/policies returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize("case", schema["/governance/audit/logs"]["GET"].as_strategy())
def test_list_audit_logs(case):
    """Verify GET /governance/audit/logs returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize("case", schema["/governance/observability/cost-profiles"]["GET"].as_strategy())
def test_list_cost_profiles(case):
    """Verify GET /governance/observability/cost-profiles returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body


@pytest.mark.parametrize("case", schema["/governance/observability/cost-aggregate"]["GET"].as_strategy())
def test_get_cost_aggregate(case):
    """Verify GET /governance/observability/cost-aggregate returns envelope."""
    response = case.call(base_url="http://testserver")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body

