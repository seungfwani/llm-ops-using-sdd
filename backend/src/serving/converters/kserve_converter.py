"""DeploymentSpec to KServe InferenceService format converter."""

from typing import Dict, Any, Optional
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
        model_metadata: Optional[dict] = None,
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

        # Determine runtime type for correct startup arguments/envs
        image_lower = container_image.lower()
        is_vllm = "vllm" in image_lower
        is_tgi = "text-generation-inference" in image_lower or "tgi" in image_lower

        # Prepare container args/env so runtime actually loads provided model_uri
        container_args = None
        env = [
            {"name": "PORT", "value": "8080"},
            {"name": "MODEL_URI", "value": model_uri},
            {"name": "MODEL_STORAGE_URI", "value": model_uri},
            {"name": "MAX_CONCURRENT_REQUESTS", "value": str(spec.runtime.max_concurrent_requests)},
            {"name": "MAX_INPUT_TOKENS", "value": str(spec.runtime.max_input_tokens)},
            {"name": "MAX_OUTPUT_TOKENS", "value": str(spec.runtime.max_output_tokens)},
            {"name": "SERVE_TARGET", "value": spec.serve_target},
        ]

        if is_vllm:
            # vLLM entrypoint needs explicit --model argument; set port to 8080 for KServe
            container_args = [
                "--model",
                model_uri,
                "--host",
                "0.0.0.0",
                "--port",
                "8080",
                "--served-model-name",
                service_name,
            ]
            if not spec.use_gpu:
                # Ensure CPU mode is enforced before model flag
                container_args = ["--device", "cpu"] + container_args
        elif is_tgi:
            # TGI defaults to bigscience/bloom-560m when MODEL_ID is missing.
            # Prefer HF ID from metadata; fall back to storage URI (e.g., MinIO/S3).
            hf_model_id = None
            if model_metadata and isinstance(model_metadata, dict):
                hf_model_id = model_metadata.get("huggingface_model_id") or model_metadata.get("model_id")
            model_id = hf_model_id or model_uri
            env.append({"name": "MODEL_ID", "value": model_id})
            # Explicit launcher args so port/model align with KServe expectations
            container_args = [
                "--model-id",
                model_id,
                "--hostname",
                "0.0.0.0",
                "--port",
                "8080",
            ]
            if not spec.use_gpu:
                container_args.append("--disable-custom-kernels")

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
                            "env": env,
                        }
                    ],
                },
            },
        }

        # Attach container args when needed so runtime loads correct model
        if container_args:
            inference_service["spec"]["predictor"]["containers"][0]["args"] = container_args

        # Add canary deployment config if rollout strategy is canary
        if spec.rollout and spec.rollout.strategy == "canary" and spec.rollout.traffic_split:
            # KServe canary deployment uses traffic split annotations
            inference_service["metadata"]["annotations"]["serving.kserve.io/canary-traffic-percent"] = str(
                spec.rollout.traffic_split.new
            )

        return inference_service

