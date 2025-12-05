"""TrainJobSpec validator that enforces training-serving-spec.md rules."""

from training.schemas import TrainJobSpec
from training.validators.model_family_validator import ModelFamilyValidator
from training.validators.dataset_compatibility_validator import DatasetCompatibilityValidator


class TrainJobSpecValidator:
    """
    Validates TrainJobSpec against training-serving-spec.md rules.
    
    Validation rules:
    1. ModelFamily whitelist: Only families defined in training-serving-spec.md allowed
    2. Dataset type compatibility: PRETRAIN → pretrain_corpus, SFT → sft_pair, etc.
    3. Base model requirements: PRETRAIN allows null, others require valid base_model_ref
    4. Method constraints: PRETRAIN defaults to "full", others allow lora/qlora/full
    5. Max sequence length: SFT max_seq_len must be <= base_model.max_position_embeddings
    """

    @classmethod
    def validate(cls, spec: TrainJobSpec, base_model_max_seq_len: int | None = None) -> None:
        """
        Validate TrainJobSpec against all rules.
        
        Args:
            spec: TrainJobSpec to validate
            base_model_max_seq_len: Maximum sequence length of base model (for SFT validation)
            
        Raises:
            ValueError: If any validation rule is violated
        """
        # 1. ModelFamily whitelist validation
        ModelFamilyValidator.validate(spec.model_family, spec.job_type)

        # 2. Dataset type compatibility validation
        DatasetCompatibilityValidator.validate(spec.job_type, spec.dataset_ref.type)

        # 3. Base model requirements
        if spec.job_type == "PRETRAIN":
            if spec.base_model_ref is not None:
                raise ValueError(
                    "PRETRAIN job_type must have base_model_ref set to null "
                    "(pretraining starts from scratch)"
                )
        else:
            if spec.base_model_ref is None:
                raise ValueError(
                    f"{spec.job_type} job_type requires a valid base_model_ref "
                    "(must reference a pretrained or fine-tuned model)"
                )

        # 4. Method constraints
        if spec.job_type == "PRETRAIN":
            if spec.method != "full":
                raise ValueError(
                    "PRETRAIN job_type must use method='full' "
                    "(pretraining requires full parameter training)"
                )
        else:
            if spec.method not in ["full", "lora", "qlora"]:
                raise ValueError(
                    f"Method '{spec.method}' is not allowed for {spec.job_type}. "
                    "Allowed methods: full, lora, qlora"
                )

        # 5. Max sequence length validation (for SFT)
        if spec.job_type == "SFT" and base_model_max_seq_len is not None:
            if spec.hyperparams.max_seq_len > base_model_max_seq_len:
                raise ValueError(
                    f"SFT max_seq_len ({spec.hyperparams.max_seq_len}) must be <= "
                    f"base_model.max_position_embeddings ({base_model_max_seq_len})"
                )

        # Additional validation: Ensure hyperparams are positive
        if spec.hyperparams.lr <= 0:
            raise ValueError("Learning rate must be positive")
        if spec.hyperparams.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        if spec.hyperparams.num_epochs <= 0:
            raise ValueError("Number of epochs must be positive")
        if spec.hyperparams.max_seq_len <= 0:
            raise ValueError("Max sequence length must be positive")

        # Resource validation
        if spec.resources.gpus < 0:
            raise ValueError("GPU count cannot be negative")
        if spec.resources.nodes < 1:
            raise ValueError("Number of nodes must be at least 1")

