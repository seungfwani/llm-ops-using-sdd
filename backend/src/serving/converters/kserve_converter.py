"""DeploymentSpec to KServe InferenceService format converter."""

from typing import Dict, Any
from serving.schemas import DeploymentSpec


class KServeConverter:
    """
    Converts DeploymentSpec to KServe InferenceService YAML.
    
    Conversion mapping:
    - DeploymentSpec → KServe InferenceService YAML
    - Resource requirements → Kubernetes resource requests/limits
    - Autoscaling config → KServe autoscaling annotations
    - Rollout strategy → KServe canary deployment config
    """

    @staticmethod
    def to_kserve_inference_service(
        spec: DeploymentSpec,
        container_image: str,
        model_uri: str,
        namespace: str = "default",
        endpoint_name: str | None = None,
    ) -> Dict[str, Any]:
        """
        Convert DeploymentSpec to KServe InferenceService YAML.
        
        Args:
            spec: DeploymentSpec to convert
            container_image: Container image to use (from image_config)
            model_uri: Storage URI for model artifacts
            namespace: Kubernetes namespace
            endpoint_name: Name for the InferenceService (defaults to model_ref)
            
        Returns:
            KServe InferenceService dictionary
        """
        service_name = endpoint_name or spec.model_ref.replace("/", "-").replace("_", "-")

        # Build resource requests/limits
        resources: Dict[str, Any] = {}
        if spec.use_gpu and spec.resources.gpus > 0:
            resources = {
                "requests": {
                    "memory": f"{spec.resources.gpu_memory_gb or 40}Gi",
                    "nvidia.com/gpu": str(spec.resources.gpus),
                },
                "limits": {
                    "memory": f"{spec.resources.gpu_memory_gb or 40}Gi",
                    "nvidia.com/gpu": str(spec.resources.gpus),
                },
            }
        else:
            # CPU-only resources
            resources = {
                "requests": {
                    "cpu": "2",
                    "memory": "4Gi",
                },
                "limits": {
                    "cpu": "4",
                    "memory": "8Gi",
                },
            }

        # RawDeployment를 기본으로 설정하되, 기존 Knative autoscaling 주석도 유지
        annotations: Dict[str, str] = {
            "serving.kserve.io/deploymentMode": "Standard",
            "autoscaling.knative.dev/minScale": str(1),
            "autoscaling.knative.dev/maxScale": str(10),
            "autoscaling.knative.dev/target": str(spec.runtime.max_concurrent_requests),
        }

        # Build InferenceService spec
        inference_service = {
            "apiVersion": "serving.kserve.io/v1beta1",
            "kind": "InferenceService",
            "metadata": {
                "name": service_name,
                "namespace": namespace,
                "annotations": annotations,
            },
            "spec": {
                "predictor": {
                    "containers": [
                        {
                            "image": container_image,
                            "name": "kserve-container",
                            "resources": resources,
                            "env": [
                                {"name": "PORT", "value": "8080"},
                                {"name": "MODEL_URI", "value": model_uri},
                                {"name": "MODEL_STORAGE_URI", "value": model_uri},
                                {"name": "MAX_CONCURRENT_REQUESTS", "value": str(spec.runtime.max_concurrent_requests)},
                                {"name": "MAX_INPUT_TOKENS", "value": str(spec.runtime.max_input_tokens)},
                                {"name": "MAX_OUTPUT_TOKENS", "value": str(spec.runtime.max_output_tokens)},
                                {"name": "SERVE_TARGET", "value": spec.serve_target},
                            ],
                        }
                    ],
                },
            },
        }

        # Add canary deployment config if rollout strategy is canary
        if spec.rollout and spec.rollout.strategy == "canary" and spec.rollout.traffic_split:
            # KServe canary deployment uses traffic split annotations
            inference_service["metadata"]["annotations"]["serving.kserve.io/canary-traffic-percent"] = str(
                spec.rollout.traffic_split.new
            )

        return inference_service

