import pytest
from fastapi.testclient import TestClient

from api.app import app
from core.database import get_session


@pytest.fixture(autouse=True)
def override_session_dependency():
    """Avoid real DB for GPU type listing (uses settings only)."""
    app.dependency_overrides[get_session] = lambda: None
    yield
    app.dependency_overrides.pop(get_session, None)


def test_list_gpu_types_returns_configured_options():
    client = TestClient(app)

    response = client.get("/llm-ops/v1/training/gpu-types")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"] is not None
    gpu_types = payload["data"]["gpuTypes"]
    assert isinstance(gpu_types, list)
    # Defaults from settings should include sample entries
    assert any(item["id"] == "nvidia-rtx-4090" for item in gpu_types)

