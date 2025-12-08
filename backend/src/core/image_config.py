"""Container image version management based on training-serving-spec.md."""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class ImageConfig:
    """
    Manages container image versions based on training-serving-spec.md.
    
    Image mappings:
    - train: PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING → gpu/cpu variants
    - serve: GENERATION, RAG → gpu/cpu variants
    
    Configuration source: ConfigMap, environment variables, or default values
    """

    # Default image mappings (from training-serving-spec.md)
    # These are placeholder values - override with environment variables in .env file
    # See env.example for configuration examples
    # 
    # Environment variable format:
    #   TRAIN_IMAGE_{JOB_TYPE}_{GPU|CPU}=<image:tag>
    #   SERVE_IMAGE_{SERVE_TARGET}_{GPU|CPU}=<image:tag>
    #
    # Example training images:
    #   - PyTorch base: pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime (GPU)
    #   - PyTorch CPU: pytorch/pytorch:2.1.0-cpu (CPU)
    #   - Custom registry: registry.example.com/llm-train-sft:pytorch2.1-cuda12.1-v1
    #
    # Example serving images:
    #   - TGI (HuggingFace): ghcr.io/huggingface/text-generation-inference:latest (GPU/CPU)
    #   - vLLM: ghcr.io/vllm/vllm:latest (GPU, CPU support limited)
    #   - Custom registry: Override via SERVE_IMAGE_{SERVE_TARGET}_{GPU|CPU} env vars
    DEFAULT_TRAIN_IMAGES: Dict[str, Dict[str, str]] = {
        "PRETRAIN": {
            # GPU: PyTorch official image with CUDA 12.1
            "gpu": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
            # CPU: PyTorch official CPU image
            "cpu": "pytorch/pytorch:2.1.0-cpu",
        },
        "SFT": {
            # GPU: PyTorch official image with CUDA 12.1
            "gpu": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
            # CPU: PyTorch official CPU image
            "cpu": "pytorch/pytorch:2.1.0-cpu",
        },
        "RAG_TUNING": {
            # GPU: PyTorch official image with CUDA 12.1
            "gpu": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
            # CPU: PyTorch official CPU image
            "cpu": "pytorch/pytorch:2.1.0-cpu",
        },
        "RLHF": {
            # GPU: PyTorch official image with CUDA 12.1
            "gpu": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
            # CPU: PyTorch official CPU image
            "cpu": "pytorch/pytorch:2.1.0-cpu",
        },
        "EMBEDDING": {
            # GPU: PyTorch official image with CUDA 12.1
            "gpu": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
            # CPU: PyTorch official CPU image
            "cpu": "pytorch/pytorch:2.1.0-cpu",
        },
    }

    DEFAULT_SERVE_IMAGES: Dict[str, Dict[str, str]] = {
        "GENERATION": {
            # GPU: TGI (Text Generation Inference) for HuggingFace models
            "gpu": "ghcr.io/huggingface/text-generation-inference:latest",
            # CPU: TGI also supports CPU (though GPU is recommended)
            "cpu": "ghcr.io/huggingface/text-generation-inference:latest",
        },
        "RAG": {
            # RAG: vLLM for RAG workloads
            "gpu": "ghcr.io/vllm/vllm:latest",
            # CPU: vLLM CPU support (limited, GPU recommended)
            "cpu": "ghcr.io/vllm/vllm:latest",
        },
    }
    
    def __init__(self):
        """Initialize image configuration from environment variables or defaults."""
        self.train_images = self._load_train_images()
        self.serve_images = self._load_serve_images()

    def _load_train_images(self) -> Dict[str, Dict[str, str]]:
        """Load training images from environment or use defaults."""
        images = {}
        for job_type in self.DEFAULT_TRAIN_IMAGES:
            gpu_key = f"TRAIN_IMAGE_{job_type}_GPU"
            cpu_key = f"TRAIN_IMAGE_{job_type}_CPU"
            images[job_type] = {
                "gpu": os.getenv(gpu_key, self.DEFAULT_TRAIN_IMAGES[job_type]["gpu"]),
                "cpu": os.getenv(cpu_key, self.DEFAULT_TRAIN_IMAGES[job_type]["cpu"]),
            }
        return images

    def _load_serve_images(self) -> Dict[str, Dict[str, str]]:
        """Load serving images from environment or use defaults."""
        images = {}
        for serve_target in self.DEFAULT_SERVE_IMAGES:
            gpu_key = f"SERVE_IMAGE_{serve_target}_GPU"
            cpu_key = f"SERVE_IMAGE_{serve_target}_CPU"
            images[serve_target] = {
                "gpu": os.getenv(gpu_key, self.DEFAULT_SERVE_IMAGES[serve_target]["gpu"]),
                "cpu": os.getenv(cpu_key, self.DEFAULT_SERVE_IMAGES[serve_target]["cpu"]),
            }
        return images

    def get_train_image(self, job_type: str, use_gpu: bool = True) -> str:
        """
        Get training container image for job_type and GPU/CPU variant.
        
        Args:
            job_type: Job type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING)
            use_gpu: Whether to use GPU variant (True) or CPU variant (False)
            
        Returns:
            Container image string
            
        Raises:
            ValueError: If job_type is not supported
        """
        if job_type not in self.train_images:
            raise ValueError(
                f"Unsupported job_type: {job_type}. "
                f"Supported types: {', '.join(self.train_images.keys())}"
            )

        variant = "gpu" if use_gpu else "cpu"
        return self.train_images[job_type][variant]

    def get_serve_image(self, serve_target: str, use_gpu: bool = True) -> str:
        """
        Get serving container image for serve_target and GPU/CPU variant.
        
        Args:
            serve_target: Serve target type (GENERATION, RAG)
            use_gpu: Whether to use GPU variant (True) or CPU variant (False)
            
        Returns:
            Container image string
            
        Raises:
            ValueError: If serve_target is not supported
        """
        if serve_target not in self.serve_images:
            raise ValueError(
                f"Unsupported serve_target: {serve_target}. "
                f"Supported targets: {', '.join(self.serve_images.keys())}"
            )

        variant = "gpu" if use_gpu else "cpu"
        return self.serve_images[serve_target][variant]

    def is_gpu_available(self) -> bool:
        """
        Detect GPU availability in the environment.
        
        Returns:
            True if GPU is available, False otherwise
        """
        # Check for NVIDIA GPU
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass

        # Check for CUDA environment variable
        if os.getenv("CUDA_VISIBLE_DEVICES") is not None:
            return True

        # Check for GPU in Kubernetes (if running in pod)
        if os.getenv("NVIDIA_VISIBLE_DEVICES") is not None:
            return True

        return False

    def get_train_image_with_fallback(self, job_type: str, use_gpu: bool = True) -> str:
        """
        Get training image with automatic CPU fallback if GPU unavailable.
        
        Args:
            job_type: Job type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING)
            use_gpu: Whether to prefer GPU variant
            
        Returns:
            Container image string (CPU variant if GPU requested but unavailable)
        """
        if use_gpu and not self.is_gpu_available():
            logger.warning(
                f"GPU requested for {job_type} but GPU not available. "
                "Falling back to CPU image."
            )
            return self.get_train_image(job_type, use_gpu=False)
        return self.get_train_image(job_type, use_gpu=use_gpu)

    def get_serve_image_with_fallback(self, serve_target: str, use_gpu: bool = True) -> str:
        """
        Get serving image with automatic CPU fallback if GPU unavailable.
        
        Args:
            serve_target: Serve target type (GENERATION, RAG)
            use_gpu: Whether to prefer GPU variant
            
        Returns:
            Container image string (CPU variant if GPU requested but unavailable)
        """
        if use_gpu and not self.is_gpu_available():
            logger.warning(
                f"GPU requested for {serve_target} but GPU not available. "
                "Falling back to CPU image."
            )
            return self.get_serve_image(serve_target, use_gpu=False)
        return self.get_serve_image(serve_target, use_gpu=use_gpu)


@lru_cache()
def get_image_config() -> ImageConfig:
    """Get cached ImageConfig instance."""
    return ImageConfig()

