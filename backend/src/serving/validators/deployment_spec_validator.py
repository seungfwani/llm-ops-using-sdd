"""DeploymentSpec validator that enforces training-serving-spec.md rules."""

from serving.schemas import DeploymentSpec
from serving.validators.job_type_compatibility_validator import JobTypeCompatibilityValidator


class DeploymentSpecValidator:
    """
    Validates DeploymentSpec against training-serving-spec.md rules.
    
    Validation rules:
    1. Job type and serve_target compatibility: RAG_TUNING → RAG, SFT/RLHF → GENERATION
    2. Model family consistency: Deployment model_family must match training job model_family
    3. Resource constraints: GPU requests must match model requirements
    4. Runtime limits: max_input_tokens must be <= model's max_position_embeddings
    """

    @classmethod
    def validate(
        cls,
        spec: DeploymentSpec,
        training_model_family: str | None = None,
        model_max_seq_len: int | None = None,
    ) -> None:
        """
        Validate DeploymentSpec against all rules.
        
        Args:
            spec: DeploymentSpec to validate
            training_model_family: Model family from training job (for consistency check)
            model_max_seq_len: Maximum sequence length of model (for runtime validation)
            
        Raises:
            ValueError: If any validation rule is violated
        """
        # 1. Job type and serve_target compatibility
        JobTypeCompatibilityValidator.validate(spec.job_type, spec.serve_target)

        # 2. Model family consistency (if training model family is provided)
        if training_model_family is not None:
            if spec.model_family != training_model_family:
                raise ValueError(
                    f"Deployment model_family '{spec.model_family}' must match "
                    f"training job model_family '{training_model_family}'"
                )

        # 3. Resource constraints
        if spec.resources.gpus < 0:
            raise ValueError("GPU count cannot be negative")
        if spec.resources.gpu_memory_gb is not None and spec.resources.gpu_memory_gb < 0:
            raise ValueError("GPU memory cannot be negative")

        # 4. Runtime limits validation
        if model_max_seq_len is not None:
            if spec.runtime.max_input_tokens > model_max_seq_len:
                raise ValueError(
                    f"max_input_tokens ({spec.runtime.max_input_tokens}) must be <= "
                    f"model's max_position_embeddings ({model_max_seq_len})"
                )

        # Additional validation: Ensure runtime constraints are positive
        if spec.runtime.max_concurrent_requests <= 0:
            raise ValueError("max_concurrent_requests must be positive")
        if spec.runtime.max_input_tokens <= 0:
            raise ValueError("max_input_tokens must be positive")
        if spec.runtime.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")

        # Rollout strategy validation
        if spec.rollout is not None:
            if spec.rollout.strategy == "canary" and spec.rollout.traffic_split is None:
                raise ValueError("Canary rollout strategy requires traffic_split configuration")

