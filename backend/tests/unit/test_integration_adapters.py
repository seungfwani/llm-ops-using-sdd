from __future__ import annotations

from integrations.base_adapter import BaseAdapter
from integrations.experiment_tracking.mlflow_adapter import MLflowAdapter
from integrations.orchestration.argo_adapter import ArgoWorkflowsAdapter
from integrations.serving.kserve_adapter import KServeAdapter
from integrations.versioning.dvc_adapter import DVCAdapter


def test_base_adapter_config_and_enabled_flag():
    adapter = type(
        "DummyAdapter",
        (BaseAdapter,),
        {
            "is_available": lambda self: True,
            "health_check": lambda self: {"status": "healthy", "message": "", "details": {}},
        },
    )({"enabled": True})

    assert adapter.is_enabled() is True
    assert adapter.get_config()["enabled"] is True


def test_dvc_adapter_init_uses_provided_cache_dir(tmp_path):
    cache_dir = tmp_path / "dvc-cache"
    adapter = DVCAdapter(
        {
            "remote_name": "minio",
            "remote_url": "s3://datasets-dvc",
            "cache_dir": str(cache_dir),
            "enabled": False,
        }
    )
    conf = adapter.get_config()
    assert conf["remote_name"] == "minio"


def test_adapter_classes_are_baseadapter_subclasses():
    assert issubclass(MLflowAdapter, BaseAdapter)
    assert issubclass(KServeAdapter, BaseAdapter)
    assert issubclass(ArgoWorkflowsAdapter, BaseAdapter)
    assert issubclass(DVCAdapter, BaseAdapter)


