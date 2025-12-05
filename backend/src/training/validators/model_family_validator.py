"""Model family whitelist validator based on training-serving-spec.md."""

from typing import List, Set


class ModelFamilyValidator:
    """
    Validates model_family against whitelist defined in training-serving-spec.md.
    
    Supported model families:
    - llama: LlamaForCausalLM (min_version: 3.0)
    - mistral: MistralForCausalLM
    - gemma: GemmaForCausalLM
    - bert: BertModel (usage: EMBEDDING, ENCODER_ONLY)
    """

    # Whitelist of supported model families
    SUPPORTED_FAMILIES: Set[str] = {
        "llama",
        "mistral",
        "gemma",
        "bert",
    }

    # Model families with specific usage constraints
    FAMILY_USAGE: dict[str, List[str]] = {
        "bert": ["EMBEDDING", "ENCODER_ONLY"],
    }

    # Model families with version constraints
    FAMILY_MIN_VERSION: dict[str, str] = {
        "llama": "3.0",
    }

    @classmethod
    def validate(cls, model_family: str, job_type: str) -> None:
        """
        Validate model_family against whitelist and constraints.
        
        Args:
            model_family: Model family identifier
            job_type: Job type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING)
            
        Raises:
            ValueError: If model_family is not in whitelist or violates constraints
        """
        if model_family not in cls.SUPPORTED_FAMILIES:
            raise ValueError(
                f"Model family '{model_family}' is not supported. "
                f"Supported families: {', '.join(sorted(cls.SUPPORTED_FAMILIES))}"
            )

        # Check usage constraints
        if model_family in cls.FAMILY_USAGE:
            allowed_usage = cls.FAMILY_USAGE[model_family]
            if job_type not in allowed_usage:
                raise ValueError(
                    f"Model family '{model_family}' can only be used with job types: {', '.join(allowed_usage)}. "
                    f"Got: {job_type}"
                )

    @classmethod
    def is_supported(cls, model_family: str) -> bool:
        """Check if model_family is in whitelist."""
        return model_family in cls.SUPPORTED_FAMILIES

    @classmethod
    def get_supported_families(cls) -> List[str]:
        """Get list of supported model families."""
        return sorted(cls.SUPPORTED_FAMILIES)

