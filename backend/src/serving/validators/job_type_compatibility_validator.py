"""Job type and serve_target compatibility validator."""

from typing import Dict, List


class JobTypeCompatibilityValidator:
    """
    Validates job_type and serve_target compatibility.
    
    Compatibility rules:
    - RAG_TUNING → RAG serve_target
    - SFT/RLHF → GENERATION serve_target
    - PRETRAIN → GENERATION serve_target (usually not deployed directly, but allowed)
    - EMBEDDING → GENERATION serve_target (or custom embedding endpoint)
    """

    # Job type to serve_target mapping
    JOB_TYPE_TO_SERVE_TARGET: Dict[str, List[str]] = {
        "RAG_TUNING": ["RAG"],
        "SFT": ["GENERATION"],
        "RLHF": ["GENERATION"],
        "PRETRAIN": ["GENERATION"],  # Usually not deployed, but allowed
        "EMBEDDING": ["GENERATION"],  # Or custom embedding endpoint
    }

    @classmethod
    def validate(cls, job_type: str, serve_target: str) -> None:
        """
        Validate serve_target compatibility with job_type.
        
        Args:
            job_type: Job type (SFT, RAG_TUNING, RLHF, PRETRAIN, EMBEDDING)
            serve_target: Serve target type (GENERATION, RAG)
            
        Raises:
            ValueError: If serve_target is not compatible with job_type
        """
        if job_type not in cls.JOB_TYPE_TO_SERVE_TARGET:
            raise ValueError(f"Unknown job_type: {job_type}")

        allowed_targets = cls.JOB_TYPE_TO_SERVE_TARGET[job_type]
        if serve_target not in allowed_targets:
            raise ValueError(
                f"Serve target '{serve_target}' is not compatible with job_type '{job_type}'. "
                f"Allowed targets: {', '.join(allowed_targets)}"
            )

    @classmethod
    def get_compatible_targets(cls, job_type: str) -> List[str]:
        """Get list of compatible serve_target types for a job_type."""
        return cls.JOB_TYPE_TO_SERVE_TARGET.get(job_type, [])

