from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.routes import health as health_module
from integrations.base_adapter import BaseAdapter


class _DummyAdapter(BaseAdapter):
  def is_available(self) -> bool:  # type: ignore[override]
      return True

  def health_check(self) -> dict:  # type: ignore[override]
      return {"status": "healthy", "message": "", "details": {}}


def _fake_build_adapters():
    return {
        "experiment_tracking": _DummyAdapter({"enabled": True}),
        "serving": _DummyAdapter({"enabled": True}),
        "orchestration": _DummyAdapter({"enabled": True}),
        "versioning": _DummyAdapter({"enabled": True}),
    }


def test_integration_health_endpoint_returns_envelope():
    # Patch health module to avoid real external calls
    health_module._build_adapters = _fake_build_adapters  # type: ignore[attr-defined]

    client = TestClient(app)
    response = client.get("/llm-ops/v1/health/integrations")

    assert response.status_code == 200
    body = response.json()

    assert "status" in body
    assert "message" in body
    assert "data" in body

    data = body["data"]
    assert "overall_status" in data
    assert "integrations" in data


