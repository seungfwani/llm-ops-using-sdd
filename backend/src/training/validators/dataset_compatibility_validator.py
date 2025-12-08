"""Dataset type compatibility validator based on training-serving-spec.md."""

from typing import Dict, List


class DatasetCompatibilityValidator:
    """
    Validates dataset type compatibility with job_type.
    
    Compatibility rules:
    - PRETRAIN → pretrain_corpus
    - SFT → sft_pair
    - RAG_TUNING → rag_qa
    - RLHF → rlhf_pair
    - EMBEDDING → pretrain_corpus or sft_pair (flexible)
    """

    # Job type to dataset type mapping
    JOB_TYPE_TO_DATASET_TYPE: Dict[str, List[str]] = {
        "PRETRAIN": ["pretrain_corpus"],
        "SFT": ["sft_pair"],
        "RAG_TUNING": ["rag_qa"],
        "RLHF": ["rlhf_pair"],
        "EMBEDDING": ["pretrain_corpus", "sft_pair"],  # Flexible for embedding models
    }

    @classmethod
    def validate(cls, job_type: str, dataset_type: str) -> None:
        """
        Validate dataset type compatibility with job_type.
        
        Args:
            job_type: Job type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING)
            dataset_type: Dataset type (pretrain_corpus, sft_pair, rag_qa, rlhf_pair)
            
        Raises:
            ValueError: If dataset_type is not compatible with job_type
        """
        if job_type not in cls.JOB_TYPE_TO_DATASET_TYPE:
            raise ValueError(f"Unknown job_type: {job_type}")

        allowed_types = cls.JOB_TYPE_TO_DATASET_TYPE[job_type]
        if dataset_type not in allowed_types:
            raise ValueError(
                f"Dataset type '{dataset_type}' is not compatible with job_type '{job_type}'. "
                f"Allowed types: {', '.join(allowed_types)}"
            )

    @classmethod
    def get_compatible_types(cls, job_type: str) -> List[str]:
        """Get list of compatible dataset types for a job_type."""
        return cls.JOB_TYPE_TO_DATASET_TYPE.get(job_type, [])

