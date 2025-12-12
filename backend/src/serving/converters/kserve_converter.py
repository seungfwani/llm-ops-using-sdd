"""DeploymentSpec to KServe InferenceService format converter."""

from typing import Dict, Any, Optional
from urllib.parse import urlparse

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

        # Detect S3/MinIO URI; if so, sync to local path via initContainer + emptyDir
        parsed = urlparse(model_uri)
        is_s3_scheme = parsed.scheme in ("s3", "minio", "s3+http", "s3+https")
        local_model_path = model_uri

        volumes = []
        volume_mounts = []
        init_containers = []

        if is_s3_scheme:
            local_model_path = f"/models/{parsed.netloc}{parsed.path}".rstrip("/")
            volumes.append(
                {
                    "name": "model-cache",
                    "emptyDir": {},
                }
            )
            volume_mounts.append(
                {
                    "name": "model-cache",
                    "mountPath": "/models",
                }
            )
            init_env = [
                {
                    "name": "AWS_ACCESS_KEY_ID",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "minio-secret",
                            "key": "MINIO_ROOT_USER",
                        }
                    },
                },
                {
                    "name": "AWS_SECRET_ACCESS_KEY",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "minio-secret",
                            "key": "MINIO_ROOT_PASSWORD",
                        }
                    },
                },
                {
                    "name": "AWS_ENDPOINT_URL",
                    "valueFrom": {
                        "configMapKeyRef": {
                            "name": "llm-ops-object-store-config",
                            "key": "endpoint-url",
                        }
                    },
                },
                {"name": "AWS_DEFAULT_REGION", "value": "us-east-1"},
            ]
            sync_cmd = (
                f"mkdir -p '{local_model_path}' && "
                f"aws s3 sync '{model_uri}' '{local_model_path}' --no-progress"
            )
            init_containers.append(
                {
                    "name": "sync-model",
                    "image": "amazon/aws-cli:2.15.50",
                    "command": ["/bin/sh", "-c"],
                    "args": [sync_cmd],
                    "env": init_env,
                    "volumeMounts": volume_mounts,
                }
            )

        env = [
            {"name": "PORT", "value": "8080"},
            {"name": "MODEL_STORAGE_URI", "value": local_model_path},
            {"name": "MAX_CONCURRENT_REQUESTS", "value": str(spec.runtime.max_concurrent_requests)},
            {"name": "MAX_INPUT_TOKENS", "value": str(spec.runtime.max_input_tokens)},
            {"name": "MAX_OUTPUT_TOKENS", "value": str(spec.runtime.max_output_tokens)},
            {"name": "SERVE_TARGET", "value": spec.serve_target},
            # Force offline/local loading; prevent HF Hub lookups
            {"name": "HF_HUB_OFFLINE", "value": "1"},
            {"name": "TRANSFORMERS_OFFLINE", "value": "1"},
            {"name": "HF_ENDPOINT", "value": ""},
            {"name": "HF_HUB_DISABLE_TELEMETRY", "value": "1"},
            {"name": "HF_HOME", "value": "/tmp/hf_cache"},
        ]

        if is_vllm:
            # vLLM entrypoint needs explicit --model argument; set port to 8080 for KServe
            container_args = [
                "--model",
                local_model_path,
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
            # Always use local_model_path as model-id to avoid HF Hub resolution.
            env.append({"name": "MODEL_ID", "value": local_model_path})
            container_args = [
                "--model-id",
                local_model_path,
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

        # Attach container args and mounts when needed so runtime loads correct model
        container_spec = inference_service["spec"]["predictor"]["containers"][0]
        if container_args:
            container_spec["args"] = container_args
        if volume_mounts:
            container_spec["volumeMounts"] = volume_mounts
        if init_containers:
            inference_service["spec"]["predictor"]["initContainers"] = init_containers
        if volumes:
            inference_service["spec"]["predictor"]["volumes"] = volumes

        # Add canary deployment config if rollout strategy is canary
        if spec.rollout and spec.rollout.strategy == "canary" and spec.rollout.traffic_split:
            # KServe canary deployment uses traffic split annotations
            inference_service["metadata"]["annotations"]["serving.kserve.io/canary-traffic-percent"] = str(
                spec.rollout.traffic_split.new
            )

        return inference_service

