"""TrainJobSpec to MLflow format converter."""

from typing import Dict, Any
from training.schemas import TrainJobSpec


class MLflowConverter:
    """
    Converts TrainJobSpec to MLflow run parameters and tags.
    
    Conversion mapping:
    - TrainJobSpec fields → MLflow run parameters (params dict)
    - Job metadata → MLflow tags
    - Experiment name → MLflow experiment name
    """

    @staticmethod
    def to_mlflow_params(spec: TrainJobSpec) -> Dict[str, Any]:
        """
        Convert TrainJobSpec to MLflow run parameters.
        
        Args:
            spec: TrainJobSpec to convert
            
        Returns:
            Dictionary of MLflow parameters
        """
        params = {
            "job_type": spec.job_type,
            "model_family": spec.model_family,
            "dataset_name": spec.dataset_ref.name,
            "dataset_version": spec.dataset_ref.version,
            "dataset_type": spec.dataset_ref.type,
            "lr": str(spec.hyperparams.lr),
            "batch_size": str(spec.hyperparams.batch_size),
            "num_epochs": str(spec.hyperparams.num_epochs),
            "max_seq_len": str(spec.hyperparams.max_seq_len),
            "precision": spec.hyperparams.precision,
            "method": spec.method,
            "gpus": str(spec.resources.gpus),
            "nodes": str(spec.resources.nodes),
            "artifact_name": spec.output.artifact_name,
            "save_format": spec.output.save_format,
        }

        if spec.base_model_ref:
            params["base_model_ref"] = spec.base_model_ref

        if spec.resources.gpu_type:
            params["gpu_type"] = spec.resources.gpu_type

        return params

    @staticmethod
    def to_mlflow_tags(spec: TrainJobSpec) -> Dict[str, str]:
        """
        Convert TrainJobSpec to MLflow tags.
        
        Args:
            spec: TrainJobSpec to convert
            
        Returns:
            Dictionary of MLflow tags
        """
        tags = {
            "job_type": spec.job_type,
            "model_family": spec.model_family,
            "method": spec.method,
            "use_gpu": str(spec.use_gpu),
        }

        if spec.base_model_ref:
            tags["base_model_ref"] = spec.base_model_ref

        return tags

    @staticmethod
    def get_experiment_name(spec: TrainJobSpec) -> str:
        """
        Generate MLflow experiment name from TrainJobSpec.
        
        Args:
            spec: TrainJobSpec to convert
            
        Returns:
            Experiment name string
        """
        # Format: {model_family}-{job_type}
        return f"{spec.model_family}-{spec.job_type.lower()}"

    @staticmethod
    def get_run_name(spec: TrainJobSpec) -> str:
        """
        Generate MLflow run name from TrainJobSpec.
        
        Args:
            spec: TrainJobSpec to convert
            
        Returns:
            Run name string
        """
        # Format: {artifact_name}-{method}
        return f"{spec.output.artifact_name}-{spec.method}"

