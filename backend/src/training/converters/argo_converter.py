"""TrainJobSpec to Argo Workflow format converter."""

from typing import Dict, Any, List
from training.schemas import TrainJobSpec


class ArgoConverter:
    """
    Converts TrainJobSpec to Argo Workflow template.
    
    Conversion mapping:
    - TrainJobSpec → Argo Workflow template with container spec
    - Resource requirements → Kubernetes resource requests/limits
    - Hyperparameters → Environment variables or command arguments
    """

    @staticmethod
    def to_argo_workflow_template(
        spec: TrainJobSpec,
        container_image: str,
        namespace: str = "default",
    ) -> Dict[str, Any]:
        """
        Convert TrainJobSpec to Argo Workflow template.
        
        Args:
            spec: TrainJobSpec to convert
            container_image: Container image to use (from image_config)
            namespace: Kubernetes namespace
            
        Returns:
            Argo Workflow template dictionary
        """
        # Build environment variables from hyperparameters
        env_vars = [
            {"name": "JOB_TYPE", "value": spec.job_type},
            {"name": "MODEL_FAMILY", "value": spec.model_family},
            {"name": "DATASET_NAME", "value": spec.dataset_ref.name},
            {"name": "DATASET_VERSION", "value": spec.dataset_ref.version},
            {"name": "DATASET_URI", "value": spec.dataset_ref.storage_uri},
            {"name": "LR", "value": str(spec.hyperparams.lr)},
            {"name": "BATCH_SIZE", "value": str(spec.hyperparams.batch_size)},
            {"name": "NUM_EPOCHS", "value": str(spec.hyperparams.num_epochs)},
            {"name": "MAX_SEQ_LEN", "value": str(spec.hyperparams.max_seq_len)},
            {"name": "PRECISION", "value": spec.hyperparams.precision},
            {"name": "METHOD", "value": spec.method},
            {"name": "ARTIFACT_NAME", "value": spec.output.artifact_name},
            {"name": "SAVE_FORMAT", "value": spec.output.save_format},
            {"name": "USE_GPU", "value": str(spec.use_gpu).lower()},
        ]

        if spec.base_model_ref:
            env_vars.append({"name": "BASE_MODEL_REF", "value": spec.base_model_ref})

        # Build resource requests/limits
        resources: Dict[str, Any] = {}
        if spec.use_gpu and spec.resources.gpus > 0:
            resources = {
                "requests": {
                    "memory": "32Gi",
                    "nvidia.com/gpu": str(spec.resources.gpus),
                },
                "limits": {
                    "memory": "64Gi",
                    "nvidia.com/gpu": str(spec.resources.gpus),
                },
            }
        else:
            # CPU-only resources
            resources = {
                "requests": {
                    "cpu": "4",
                    "memory": "8Gi",
                },
                "limits": {
                    "cpu": "8",
                    "memory": "16Gi",
                },
            }

        # Build Argo Workflow template
        workflow_template = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "WorkflowTemplate",
            "metadata": {
                "name": f"train-{spec.output.artifact_name}",
                "namespace": namespace,
            },
            "spec": {
                "entrypoint": "train-job",
                "templates": [
                    {
                        "name": "train-job",
                        "container": {
                            "image": container_image,
                            "command": ["python", "/app/train.py"],
                            "env": env_vars,
                            "resources": resources,
                        },
                    }
                ],
            },
        }

        return workflow_template

    @staticmethod
    def to_argo_workflow_args(spec: TrainJobSpec) -> List[str]:
        """
        Convert TrainJobSpec to command-line arguments for training script.
        
        Args:
            spec: TrainJobSpec to convert
            
        Returns:
            List of command-line argument strings
        """
        args = [
            f"--job-type={spec.job_type}",
            f"--model-family={spec.model_family}",
            f"--dataset-name={spec.dataset_ref.name}",
            f"--dataset-version={spec.dataset_ref.version}",
            f"--dataset-uri={spec.dataset_ref.storage_uri}",
            f"--lr={spec.hyperparams.lr}",
            f"--batch-size={spec.hyperparams.batch_size}",
            f"--num-epochs={spec.hyperparams.num_epochs}",
            f"--max-seq-len={spec.hyperparams.max_seq_len}",
            f"--precision={spec.hyperparams.precision}",
            f"--method={spec.method}",
            f"--artifact-name={spec.output.artifact_name}",
            f"--save-format={spec.output.save_format}",
        ]

        if spec.base_model_ref:
            args.append(f"--base-model-ref={spec.base_model_ref}")

        if spec.use_gpu:
            args.append(f"--gpus={spec.resources.gpus}")
            if spec.resources.gpu_type:
                args.append(f"--gpu-type={spec.resources.gpu_type}")

        return args

