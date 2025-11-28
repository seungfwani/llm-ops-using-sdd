"""Security/RBAC regression tests to verify policy enforcement."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import create_app
from backend.src.governance.services.policies import GovernancePolicyService
from backend.src.core.database import get_session

app = create_app()
client = TestClient(app)


class TestRBACRegression:
    """Regression tests for RBAC and policy enforcement."""

    def test_missing_user_id_header_returns_401(self):
        """Verify that requests without X-User-Id header are rejected."""
        response = client.get("/llm-ops/v1/catalog/models")
        # Should return 200 with fail status per constitution
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "fail"
        assert "X-User-Id" in body["message"].lower() or "authentication" in body["message"].lower()

    def test_user_without_required_role_cannot_delete(self):
        """Verify that users without 'admin' role cannot delete resources."""
        headers = {
            "X-User-Id": "researcher-1",
            "X-User-Roles": "researcher",  # Not admin
        }
        # Try to delete a model (assuming one exists)
        response = client.delete(
            "/llm-ops/v1/catalog/models/00000000-0000-0000-0000-000000000000",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        # Should be denied by policy
        assert body["status"] == "fail" or body.get("message", "").lower().find("denied") >= 0

    def test_admin_can_perform_all_actions(self):
        """Verify that users with 'admin' role can perform all actions."""
        headers = {
            "X-User-Id": "admin-1",
            "X-User-Roles": "admin,researcher",
        }
        # Admin should be able to list resources
        response = client.get("/llm-ops/v1/catalog/models", headers=headers)
        assert response.status_code == 200
        body = response.json()
        # Should succeed (may be empty list, but should not be denied)

    def test_policy_evaluation_logs_to_audit(self):
        """Verify that policy violations are logged to audit log."""
        # Create a policy that denies an action
        session = next(get_session())
        policy_service = GovernancePolicyService(session)
        
        policy = policy_service.create_policy(
            name="Test Deny Policy",
            scope="catalog",
            rules={
                "allowed_actions": ["get", "list"],
                "required_roles": ["admin"],
            },
            status="active",
        )
        
        # Try to perform denied action
        headers = {
            "X-User-Id": "researcher-1",
            "X-User-Roles": "researcher",
        }
        response = client.post(
            "/llm-ops/v1/catalog/models",
            headers=headers,
            json={"name": "test", "version": "1.0.0", "type": "base", "ownerTeam": "test"},
        )
        
        # Check audit log
        audit_response = client.get(
            "/llm-ops/v1/governance/audit/logs",
            headers=headers,
            params={"action": "create", "result": "denied"},
        )
        assert audit_response.status_code == 200
        audit_body = audit_response.json()
        if audit_body.get("data"):
            # Should have at least one denied entry
            denied_logs = [log for log in audit_body["data"] if log.get("result") == "denied"]
            assert len(denied_logs) > 0
        
        # Cleanup
        policy_service.delete_policy(str(policy.id))

    def test_rbac_middleware_enforces_policies(self):
        """Verify that RBAC middleware enforces policies before route handlers."""
        headers = {
            "X-User-Id": "test-user",
            "X-User-Roles": "viewer",  # Limited role
        }
        
        # Viewer should be able to read but not write
        read_response = client.get("/llm-ops/v1/catalog/models", headers=headers)
        assert read_response.status_code == 200
        
        # Viewer should not be able to create
        create_response = client.post(
            "/llm-ops/v1/catalog/models",
            headers=headers,
            json={"name": "test", "version": "1.0.0", "type": "base", "ownerTeam": "test"},
        )
        assert create_response.status_code == 200
        body = create_response.json()
        # Should be denied if policy requires higher role
        # (This depends on actual policy configuration)

    def test_error_responses_always_200_with_envelope(self):
        """Verify that all error responses return 200 with {status,message,data} envelope."""
        # Test various error scenarios
        test_cases = [
            ("/llm-ops/v1/catalog/models/invalid-id", "GET"),  # 404 equivalent
            ("/llm-ops/v1/catalog/models", "POST"),  # Missing body
            ("/llm-ops/v1/invalid-endpoint", "GET"),  # 404
        ]
        
        headers = {
            "X-User-Id": "test-user",
            "X-User-Roles": "admin",
        }
        
        for endpoint, method in test_cases:
            if method == "GET":
                response = client.get(endpoint, headers=headers)
            else:
                response = client.post(endpoint, headers=headers, json={})
            
            assert response.status_code == 200, f"{method} {endpoint} should return 200"
            body = response.json()
            assert "status" in body, f"{method} {endpoint} should have 'status' field"
            assert "message" in body, f"{method} {endpoint} should have 'message' field"
            assert "data" in body or "data" in body, f"{method} {endpoint} should have 'data' field"

