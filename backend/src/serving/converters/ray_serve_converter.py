"""DeploymentSpec to Ray Serve format converter."""

from typing import Dict, Any
from serving.schemas import DeploymentSpec


class RayServeConverter:
    """
    Converts DeploymentSpec to Ray Serve deployment config.
    
    Conversion mapping:
    - DeploymentSpec → Ray Serve deployment config
    - Resource requirements → Ray Serve num_replicas and resource requirements
    - Runtime constraints → Ray Serve configuration
    """

    @staticmethod
    def to_ray_serve_deployment(
        spec: DeploymentSpec,
        model_path: str,
        deployment_name: str | None = None,
    ) -> Dict[str, Any]:
        """
        Convert DeploymentSpec to Ray Serve deployment config.
        
        Args:
            spec: DeploymentSpec to convert
            model_path: Path to model files
            deployment_name: Name for the Ray Serve deployment (defaults to model_ref)
            
        Returns:
            Ray Serve deployment config dictionary
        """
        deployment_name = deployment_name or spec.model_ref.replace("/", "-").replace("_", "-")

        # Build resource requirements
        resources: Dict[str, Any] = {}
        if spec.use_gpu and spec.resources.gpus > 0:
            resources = {
                "num_cpus": 2,
                "num_gpus": spec.resources.gpus,
                "memory": (spec.resources.gpu_memory_gb or 40) * 1024 * 1024 * 1024,  # Convert GB to bytes
            }
        else:
            # CPU-only resources
            resources = {
                "num_cpus": 4,
                "memory": 8 * 1024 * 1024 * 1024,  # 8GB in bytes
            }

        # Build Ray Serve deployment config
        deployment_config = {
            "name": deployment_name,
            "num_replicas": 1,  # Can be scaled based on autoscaling config
            "max_concurrent_queries": spec.runtime.max_concurrent_requests,
            "ray_actor_options": {
                "resources": resources,
            },
            "user_config": {
                "model_path": model_path,
                "max_input_tokens": spec.runtime.max_input_tokens,
                "max_output_tokens": spec.runtime.max_output_tokens,
                "serve_target": spec.serve_target,
            },
        }

        return deployment_config

