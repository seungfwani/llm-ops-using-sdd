"""Training job orchestration services."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from catalog.services.catalog import CatalogService
from core.image_config import get_image_config
from core.settings import get_settings
from services.experiment_tracking_service import ExperimentTrackingService
from services.integration_config import IntegrationConfigService
from training.converters.mlflow_converter import MLflowConverter
from training.repositories import ExperimentMetricRepository, TrainingJobRepository
from training.scheduler import KubernetesScheduler
from training.schemas import TrainJobSpec
from training.validators.train_job_spec_validator import TrainJobSpecValidator

logger = logging.getLogger(__name__)

settings = get_settings()


class TrainingJobService:
    """Service for managing training jobs and experiment tracking."""

    def __init__(self, session: Session):
        self.job_repo = TrainingJobRepository(session)
        self.metric_repo = ExperimentMetricRepository(session)
        self.scheduler = KubernetesScheduler()
        self.session = session
        self.experiment_tracking = ExperimentTrackingService(session)
        self.integration_config = IntegrationConfigService(session)
    
    @staticmethod
    def _extract_gpu_type(resource_profile: dict) -> Optional[str]:
        """Extract gpuType/gpu_type from resource profile."""
        if not isinstance(resource_profile, dict):
            return None
        gpu_type = resource_profile.get("gpuType", resource_profile.get("gpu_type"))
        if gpu_type:
            return str(gpu_type).strip()
        return None

    def _validate_gpu_type(
        self,
        resource_profile: dict,
        use_gpu: bool,
        environment: str,
    ) -> Optional[str]:
        """
        Validate gpu_type when GPU is requested.
        
        Returns canonical gpu_type or None for CPU-only.
        """
        if not use_gpu:
            return None
        
        gpu_type = self._extract_gpu_type(resource_profile)
        if not gpu_type:
            raise ValueError("gpu_type is required when useGpu=true")
        
        allowed_types = {
            item["id"].lower()
            for item in self.integration_config.get_gpu_types(environment=environment)
            if item.get("enabled", True) and item.get("id")
        }
        if allowed_types and gpu_type.lower() not in allowed_types:
            raise ValueError(f"gpu_type '{gpu_type}' is not allowed in environment '{environment}'")
        
        # Normalize keys for downstream components
        resource_profile["gpuType"] = gpu_type
        resource_profile["gpu_type"] = gpu_type
        return gpu_type

    @staticmethod
    def _detect_local_api_url() -> str:
        """
        Detect local development API URL for training pods to access.
        Tries common local development hostnames that work from Kubernetes pods.
        
        Returns:
            API URL string or empty string if not detected
        """
        import subprocess
        
        # Try minikube first (most common for local dev)
        try:
            result = subprocess.run(
                ["minikube", "status"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # Minikube is running, use host.minikube.internal
                api_url = "http://host.minikube.internal:8000/llm-ops/v1"
                logger.info(f"Detected minikube - using {api_url} for local API access")
                return api_url
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass
        
        # Try Docker Desktop (host.docker.internal works in some Kubernetes setups)
        # Note: This is less reliable, so we'll log but not auto-use
        logger.debug("Could not detect minikube - consider setting TRAINING_API_BASE_URL manually")
        
        # Return empty string - user should configure manually
        return ""

    def submit_job(
        self,
        model_entry_id: Optional[str],
        dataset_id: str,
        job_type: str,
        resource_profile: dict,
        hyperparameters: Optional[dict] = None,
        retry_policy: Optional[dict] = None,
        submitted_by: str = "system",
        use_gpu: bool = True,
        api_base_url: Optional[str] = None,
        output_model_name: Optional[str] = None,
        output_model_version: Optional[str] = None,
        auto_register_output_model: bool = True,
        train_job_spec: Optional[TrainJobSpec] = None,
    ) -> catalog_models.TrainingJob:
        """
        Submit a training job to the scheduler.

        Args:
            model_entry_id: Catalog model entry ID (required for finetune, optional for from_scratch/pretrain)
            dataset_id: Dataset record ID
            job_type: 'finetune', 'from_scratch', 'pretrain', or 'distributed'
            resource_profile: GPU count, GPU type, max duration (when use_gpu=True) or CPU cores, memory, max duration (when use_gpu=False)
            hyperparameters: Training hyperparameters (required for from_scratch/pretrain with architecture config)
            retry_policy: Retry configuration
            submitted_by: User ID who submitted the job
            use_gpu: Whether to use GPU resources (default: True). Set to False for CPU-only training.
            api_base_url: API base URL for training pod to record metrics. If None, uses settings.training_api_base_url.
                         If empty string, disables metric recording.

        Returns:
            Created TrainingJob entity
        """
        # Validate model entry (required for finetune, optional for from_scratch/pretrain)
        if job_type == "finetune":
            if not model_entry_id:
                raise ValueError("Fine-tuning job requires a model entry ID")
            model_entry = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
            if not model_entry:
                raise ValueError(f"Model entry {model_entry_id} not found")
            if model_entry.status != "approved":
                raise ValueError(f"Model entry {model_entry_id} is not approved")
        elif job_type in ("from_scratch", "pretrain"):
            # For from-scratch and pre-training, architecture must be in hyperparameters
            if not hyperparameters or "architecture" not in hyperparameters:
                raise ValueError(f"{job_type} job requires architecture configuration in hyperparameters")
            # Model entry is optional for from-scratch/pretrain
            if model_entry_id:
                model_entry = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
                if model_entry and model_entry.status != "approved":
                    raise ValueError(f"Model entry {model_entry_id} is not approved")

        # Validate dataset exists and is approved
        dataset = self.session.get(catalog_models.DatasetRecord, dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")
        if not dataset.approved_at:
            raise ValueError(f"Dataset {dataset_id} is not approved")

        # Validate GPU type against configured options per environment
        environment = settings.environment
        self._validate_gpu_type(resource_profile, use_gpu, environment)

        # If TrainJobSpec is provided, validate it
        image_config = get_image_config()
        container_image = None
        if train_job_spec:
            # Validate TrainJobSpec
            base_model_max_seq_len = None
            if train_job_spec.base_model_ref and model_entry_id:
                model_entry = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
                if model_entry and model_entry.model_metadata:
                    base_model_max_seq_len = model_entry.model_metadata.get("max_position_embeddings")
            
            TrainJobSpecValidator.validate(train_job_spec, base_model_max_seq_len)
            
            # Select container image based on job_type and GPU availability
            container_image = image_config.get_train_image_with_fallback(
                train_job_spec.job_type,
                train_job_spec.use_gpu
            )
            
            logger.info(f"Using container image {container_image} for job_type {train_job_spec.job_type} (use_gpu={train_job_spec.use_gpu})")

        # Store output model configuration in resource_profile for later use
        enhanced_resource_profile = resource_profile.copy()
        if "outputModelConfig" not in enhanced_resource_profile:
            enhanced_resource_profile["outputModelConfig"] = {}
        enhanced_resource_profile["outputModelConfig"]["outputModelName"] = output_model_name
        enhanced_resource_profile["outputModelConfig"]["outputModelVersion"] = output_model_version
        enhanced_resource_profile["outputModelConfig"]["autoRegisterOutputModel"] = auto_register_output_model

        # Create job entity
        job = catalog_models.TrainingJob(
            id=uuid4(),
            model_entry_id=model_entry_id,
            dataset_id=dataset_id,
            job_type=job_type,
            resource_profile=enhanced_resource_profile,
            retry_policy=retry_policy or {"maxRetries": 3, "backoffSeconds": 60},
            status="queued",
            submitted_by=submitted_by,
            submitted_at=datetime.utcnow(),
        )

        # Store TrainJobSpec if provided
        if train_job_spec:
            job.train_job_spec = train_job_spec.model_dump()

        job = self.job_repo.create(job)

        # Determine API base URL: use provided value, or fall back to settings, or try to detect local dev
        # If api_base_url is provided, use it as-is (should include full path like /llm-ops/v1)
        # If None, use settings value
        # If empty, try to detect local development environment and use appropriate host
        if api_base_url is not None:
            api_url = api_base_url.strip() if api_base_url.strip() else ""
        else:
            api_url = settings.training_api_base_url.strip() if settings.training_api_base_url.strip() else ""
        
        # If still empty, try to detect local development environment
        if not api_url:
            api_url = self._detect_local_api_url()
        
        # Log API URL configuration
        if api_url:
            logger.info(f"Configuring API_BASE_URL for training job {job.id}: {api_url}")
        else:
            logger.warning(
                f"API_BASE_URL not configured for training job {job.id} - metric recording will be disabled. "
                f"To enable metrics, either: "
                f"1) Set TRAINING_API_BASE_URL in backend settings (e.g., http://host.minikube.internal:8000/llm-ops/v1), or "
                f"2) Provide apiBaseUrl in training job request. "
                f"For local development with minikube, use: http://host.minikube.internal:8000/llm-ops/v1"
            )

        # Submit to Kubernetes scheduler
        try:
            job_name = f"training-{job.id}"
            
            # Generate storage URI for output model (if auto-register is enabled)
            storage_uri = None
            if auto_register_output_model:
                # Generate output model name and version if not provided
                if not output_model_name:
                    output_model_name = self._generate_model_name(job)
                if not output_model_version:
                    output_model_version = self._generate_model_version(job)
                storage_uri = self._generate_storage_uri(output_model_name, output_model_version, str(job.id))
                # Store storage URI in job for later use in register_output_model
                job.output_model_storage_uri = storage_uri
                self.job_repo.update(job)
                logger.info(f"Stored storage URI for job {job.id}: {storage_uri}")
            
            # Build base environment variables
            base_env_vars = {
                "MODEL_ENTRY_ID": str(model_entry_id) if model_entry_id else "",
                "DATASET_ID": str(dataset_id),
                "JOB_ID": str(job.id),
                "JOB_TYPE": job_type,
                "HYPERPARAMETERS": str(hyperparameters or {}),
            }
            
            # Only add API_BASE_URL if it's configured (not empty)
            # If empty, metric recording will be disabled in training pod
            if api_url:
                base_env_vars["API_BASE_URL"] = api_url
            
            # Add model registration configuration for API-based upload
            if storage_uri and auto_register_output_model:
                base_env_vars["MODEL_STORAGE_URI"] = storage_uri
                base_env_vars["OUTPUT_MODEL_NAME"] = output_model_name
                base_env_vars["OUTPUT_MODEL_VERSION"] = output_model_version
                base_env_vars["OWNER_TEAM"] = submitted_by  # Use submitted_by as owner_team
                base_env_vars["AUTO_UPLOAD_MODEL"] = "true"
                
                # Get model_family and huggingface_model_id from base model for finetune jobs
                model_family = None
                huggingface_model_id = None
                if job_type == "finetune" and model_entry_id:
                    base_model = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
                    if base_model:
                        model_family = base_model.model_family
                        base_env_vars["BASE_MODEL_FAMILY"] = model_family
                        logger.info(f"Set BASE_MODEL_FAMILY={model_family} from base model {model_entry_id}")
                        
                        # Get huggingface_model_id from metadata if available
                        if base_model.model_metadata and isinstance(base_model.model_metadata, dict):
                            huggingface_model_id = base_model.model_metadata.get("huggingface_model_id")
                            if huggingface_model_id:
                                base_env_vars["HF_MODEL_ID"] = huggingface_model_id
                                logger.info(f"Set HF_MODEL_ID={huggingface_model_id} from base model metadata")
                
                # Also pass base model ID for reference
                if model_entry_id:
                    base_env_vars["BASE_MODEL_ID"] = str(model_entry_id)
                
                logger.info(f"Configured API-based model upload for job {job.id} to {storage_uri}")
            else:
                base_env_vars["AUTO_UPLOAD_MODEL"] = "false"
                logger.info(f"Model file auto-upload disabled for job {job.id}")
            
            # Use container image from TrainJobSpec if available, otherwise use resource_profile
            effective_image = container_image or resource_profile.get("image", "pytorch/pytorch:latest")
            
            if use_gpu:
                gpu_count = resource_profile.get("gpuCount", resource_profile.get("gpu_count", 1))
                if train_job_spec:
                    gpu_count = train_job_spec.resources.gpus
                num_nodes = resource_profile.get("numNodes", resource_profile.get("num_nodes", 1))
                if train_job_spec:
                    num_nodes = train_job_spec.resources.nodes
                
                # For distributed training, use multi-node configuration
                if job_type == "distributed" or gpu_count > 1 or num_nodes > 1:
                    k8s_uid = self.scheduler.submit_distributed_job(
                        job_name=job_name,
                        image=effective_image,
                        gpu_count=gpu_count,
                        num_nodes=num_nodes,
                        gpu_type=resource_profile.get("gpuType", resource_profile.get("gpu_type", "nvidia-tesla-v100")),
                        command=self._build_command(job_type, hyperparameters or {}),
                        env_vars=base_env_vars,
                    )
                else:
                    k8s_uid = self.scheduler.submit_job(
                        job_name=job_name,
                        image=effective_image,
                        gpu_count=gpu_count,
                        gpu_type=resource_profile.get("gpuType", resource_profile.get("gpu_type", "nvidia-tesla-v100")),
                        command=self._build_command(job_type, hyperparameters or {}),
                        env_vars=base_env_vars,
                    )
            else:
                # CPU-only training
                # For CPU-only training, always use settings defaults to ensure compatibility with local dev environments
                # Ignore resource_profile values to prevent requesting too much memory (e.g., 8Gi on minikube)
                cpu_cores = int(settings.training_cpu_only_cpu_request)
                memory = settings.training_cpu_only_memory_request
                
                logger.info(
                    f"CPU-only training: Using settings defaults - cpu={cpu_cores}, memory={memory} "
                    f"(ignoring resource_profile to ensure local dev compatibility)"
                )
                
                cpu_env_vars = base_env_vars.copy()
                cpu_env_vars["USE_GPU"] = "false"
                k8s_uid = self.scheduler.submit_cpu_only_job(
                    job_name=job_name,
                    image=effective_image,
                    cpu_cores=cpu_cores,
                    memory=memory,
                    command=self._build_command(job_type, hyperparameters or {}),
                    env_vars=cpu_env_vars,
                )
            job.scheduler_id = k8s_uid
            job.status = "running"
            job.started_at = datetime.utcnow()
            job = self.job_repo.update(job)
            logger.info(f"Training job {job.id} submitted to Kubernetes with UID {k8s_uid}")
            
            # Create experiment run in MLflow
            try:
                experiment_name = None
                if model_entry_id:
                    model_entry = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
                    if model_entry:
                        experiment_name = f"{model_entry.name}-{model_entry.version}"
                
                # Use TrainJobSpec if available, otherwise use hyperparameters
                mlflow_params = hyperparameters or {}
                mlflow_tags = {}
                
                # If train_job_spec is stored in job, use it for MLflow conversion
                if hasattr(job, 'train_job_spec') and job.train_job_spec:
                    try:
                        spec = TrainJobSpec(**job.train_job_spec)
                        mlflow_params = MLflowConverter.to_mlflow_params(spec)
                        mlflow_tags = MLflowConverter.to_mlflow_tags(spec)
                        experiment_name = MLflowConverter.get_experiment_name(spec)
                        run_name = MLflowConverter.get_run_name(spec)
                    except Exception as e:
                        logger.warning(f"Failed to convert TrainJobSpec to MLflow format: {e}, using hyperparameters")
                        run_name = f"run-{job.id}"
                else:
                    run_name = f"run-{job.id}"
                
                self.experiment_tracking.create_experiment_run(
                    training_job_id=job.id,
                    experiment_name=experiment_name,
                    run_name=run_name,
                    parameters=mlflow_params,
                )
            except Exception as e:
                logger.warning(f"Failed to create experiment run for job {job.id}: {e}")
                # Graceful degradation - continue without experiment tracking
        except Exception as e:
            logger.error(f"Failed to submit job {job.id} to scheduler: {e}")
            job.status = "failed"
            job = self.job_repo.update(job)
            raise

        return job

    def sync_job_status(self, job: catalog_models.TrainingJob) -> bool:
        """
        Sync a single job's status with Kubernetes.
        
        Returns:
            True if status was updated, False otherwise
        """
        if not job.scheduler_id or job.status not in ("queued", "running"):
            return False
        
        try:
            job_name = f"training-{job.id}"
            k8s_status = self.scheduler.get_job_status(job_name)
            
            if not k8s_status:
                # Job not found in Kubernetes - might have been deleted
                if job.status == "running":
                    logger.warning(f"Job {job.id} not found in Kubernetes, marking as failed")
                    job.status = "failed"
                    job.completed_at = datetime.utcnow()
                    self.job_repo.update(job)
                    return True
                return False
            
            k8s_status_str = k8s_status.get("status")
            k8s_succeeded = k8s_status.get("succeeded", 0) or 0
            k8s_failed = k8s_status.get("failed", 0) or 0
            completion_time = k8s_status.get("completion_time")
            
            updated = False
            
            # Update job status based on Kubernetes status
            if k8s_status_str == "succeeded" or k8s_succeeded > 0:
                if job.status != "succeeded":
                    job.status = "succeeded"
                    if completion_time:
                        job.completed_at = datetime.fromisoformat(completion_time.replace('Z', '+00:00'))
                    else:
                        job.completed_at = datetime.utcnow()
                    self.job_repo.update(job)
                    logger.info(f"Updated job {job.id} status to succeeded")
                    
                    # Update experiment run status
                    try:
                        self.experiment_tracking.update_run_status(
                            training_job_id=job.id,
                            status="completed",
                            end_time=job.completed_at,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update experiment run status: {e}")
                    
                    updated = True
                    
                    # Auto-register output model if enabled
                    try:
                        output_model_config = job.resource_profile.get("outputModelConfig", {})
                        auto_register = output_model_config.get("autoRegisterOutputModel", True)
                        
                        if auto_register and not job.output_model_entry_id:
                            # Get output model name and version from config or generate defaults
                            output_model_name = output_model_config.get("outputModelName")
                            output_model_version = output_model_config.get("outputModelVersion")
                            
                            if not output_model_name:
                                output_model_name = self._generate_model_name(job)
                            if not output_model_version:
                                output_model_version = self._generate_model_version(job)
                            
                            logger.info(
                                f"Auto-registering output model for job {job.id}: "
                                f"name={output_model_name}, version={output_model_version}"
                            )
                            
                            try:
                                # Use storage URI from job if available (to match training pod upload path)
                                storage_uri_for_registration = job.output_model_storage_uri if job.output_model_storage_uri else None
                                self.register_output_model(
                                    job_id=str(job.id),
                                    model_name=output_model_name,
                                    model_version=output_model_version,
                                    storage_uri=storage_uri_for_registration,  # Use same URI as training pod
                                    owner_team=job.submitted_by,
                                    metadata=None,
                                )
                                logger.info(f"Successfully auto-registered output model for job {job.id}")
                            except Exception as e:
                                # Log error but don't fail the status update
                                logger.error(
                                    f"Failed to auto-register output model for job {job.id}: {e}",
                                    exc_info=True
                                )
                    except Exception as e:
                        # Log error but don't fail the status update
                        logger.warning(
                            f"Error during auto-registration check for job {job.id}: {e}",
                            exc_info=True
                        )
            elif k8s_status_str == "failed" or k8s_failed > 0:
                if job.status != "failed":
                    job.status = "failed"
                    if completion_time:
                        job.completed_at = datetime.fromisoformat(completion_time.replace('Z', '+00:00'))
                    else:
                        job.completed_at = datetime.utcnow()
                    self.job_repo.update(job)
                    logger.info(f"Updated job {job.id} status to failed")
                    
                    # Update experiment run status
                    try:
                        self.experiment_tracking.update_run_status(
                            training_job_id=job.id,
                            status="failed",
                            end_time=job.completed_at,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update experiment run status: {e}")
                    
                    updated = True
            elif k8s_status_str == "running" and job.status == "queued":
                job.status = "running"
                start_time = k8s_status.get("start_time")
                if start_time:
                    job.started_at = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                else:
                    job.started_at = datetime.utcnow()
                self.job_repo.update(job)
                logger.info(f"Updated job {job.id} status to running")
                updated = True
            
            return updated
        except Exception as e:
            logger.warning(f"Failed to sync job {job.id} status with Kubernetes: {e}")
            return False

    def sync_all_active_jobs(self) -> int:
        """
        Sync status of all queued/running jobs with Kubernetes.
        
        Returns:
            Number of jobs that were updated
        """
        active_jobs = self.list_jobs(status="queued") + self.list_jobs(status="running")
        updated_count = 0
        
        for job in active_jobs:
            try:
                if self.sync_job_status(job):
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error syncing job {job.id}: {e}")
        
        if updated_count > 0:
            logger.info(f"Synced {updated_count} training job(s) with Kubernetes")
        
        return updated_count

    def get_job(self, job_id: str) -> Optional[catalog_models.TrainingJob]:
        """Retrieve a training job by ID and sync status with Kubernetes."""
        job = self.job_repo.get(job_id)
        if not job:
            return None
        
        # Sync status with Kubernetes if job has been submitted
        self.sync_job_status(job)
        
        # Refresh job from database to get updated status
        job = self.job_repo.get(job_id)
        
        # Check if job is succeeded but output model not registered yet
        if job and job.status == "succeeded" and not job.output_model_entry_id:
            try:
                output_model_config = job.resource_profile.get("outputModelConfig", {})
                auto_register = output_model_config.get("autoRegisterOutputModel", True)
                
                if auto_register:
                    # Get output model name and version from config or generate defaults
                    output_model_name = output_model_config.get("outputModelName")
                    output_model_version = output_model_config.get("outputModelVersion")
                    
                    if not output_model_name:
                        output_model_name = self._generate_model_name(job)
                    if not output_model_version:
                        output_model_version = self._generate_model_version(job)
                    
                    logger.info(
                        f"Attempting to auto-register output model for succeeded job {job.id}: "
                        f"name={output_model_name}, version={output_model_version}"
                    )
                    
                    try:
                        # Use storage URI from job if available (to match training pod upload path)
                        storage_uri_for_registration = job.output_model_storage_uri if job.output_model_storage_uri else None
                        self.register_output_model(
                            job_id=str(job.id),
                            model_name=output_model_name,
                            model_version=output_model_version,
                            storage_uri=storage_uri_for_registration,  # Use same URI as training pod
                            owner_team=job.submitted_by,
                            metadata=None,
                        )
                        logger.info(f"Successfully auto-registered output model for job {job.id}")
                        # Refresh job to get updated output_model_entry_id
                        job = self.job_repo.get(job_id)
                    except Exception as e:
                        # Log error but don't fail
                        logger.warning(
                            f"Failed to auto-register output model for succeeded job {job.id}: {e}",
                            exc_info=True
                        )
            except Exception as e:
                # Log error but don't fail
                logger.warning(
                    f"Error during auto-registration check for succeeded job {job.id}: {e}",
                    exc_info=True
                )
        
        return job

    def list_jobs(
        self,
        model_entry_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[catalog_models.TrainingJob]:
        """List training jobs with optional filters."""
        return list(self.job_repo.list(model_entry_id=model_entry_id, status=status))

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running training job."""
        job = self.job_repo.get(job_id)
        if not job:
            return False

        if job.status in ("succeeded", "failed", "cancelled"):
            return False

        try:
            if job.scheduler_id:
                job_name = f"training-{job.id}"
                self.scheduler.delete_job(job_name)
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            self.job_repo.update(job)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def record_metric(
        self,
        job_id: str,
        name: str,
        value: float,
        unit: Optional[str] = None,
    ) -> catalog_models.ExperimentMetric:
        """Record an experiment metric for a training job."""
        from uuid import UUID
        
        # Validate and convert job_id to UUID
        try:
            job_uuid = UUID(job_id) if isinstance(job_id, str) else job_id
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid job_id format: {job_id}") from e
        
        job = self.job_repo.get(job_uuid)
        if not job:
            raise ValueError(f"Training job {job_id} not found")

        metric = catalog_models.ExperimentMetric(
            id=uuid4(),
            training_job_id=job_uuid,  # Use UUID instead of string
            name=name,
            value=value,
            unit=unit,
            recorded_at=datetime.utcnow(),
        )
        try:
            metric = self.metric_repo.create(metric)
            
            # Forward metric to MLflow
            try:
                self.experiment_tracking.log_metrics(
                    training_job_id=job_uuid,
                    metrics={name: value},
                )
            except Exception as e:
                logger.warning(f"Failed to log metric to MLflow: {e}")
                # Graceful degradation - continue without MLflow
            
            return metric
        except Exception as e:
            logger.error(f"Failed to save metric {name} for job {job_id}: {e}")
            raise

    def get_job_metrics(self, job_id: str) -> list[catalog_models.ExperimentMetric]:
        """Retrieve all metrics for a training job."""
        return list(self.metric_repo.list_by_job(job_id))

    def _generate_model_name(self, job: catalog_models.TrainingJob) -> str:
        """
        Generate default model name for output model.
        
        Args:
            job: Training job
            
        Returns:
            Generated model name
        """
        if job.job_type == "finetune" and job.model_entry_id:
            # For fine-tuning, use base model name + finetuned suffix
            base_model = self.session.get(catalog_models.ModelCatalogEntry, job.model_entry_id)
            if base_model:
                base_name = base_model.name
                # Extract base name without version
                if "-v" in base_name or " v" in base_name:
                    base_name = base_name.split("-v")[0].split(" v")[0]
                return f"{base_name}-finetuned"
        
        # For from_scratch/pretrain, use job type + timestamp
        return f"{job.job_type}-model"
    
    def _generate_model_version(self, job: catalog_models.TrainingJob) -> str:
        """
        Generate default model version for output model.
        
        Args:
            job: Training job
            
        Returns:
            Generated model version
        """
        # Use timestamp-based version: YYYYMMDD-HHMMSS
        from datetime import datetime
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"1.0.0-{timestamp}"
    
    def _generate_storage_uri(self, model_name: str, model_version: str, job_id: str) -> str:
        """
        Generate storage URI for trained model artifacts.
        
        Args:
            model_name: Model name (will be sanitized)
            model_version: Model version
            job_id: Training job ID
            
        Returns:
            Storage URI in format: s3://{bucket}/models/{sanitized_name}/{version}/
        """
        # Sanitize model name for use in storage path
        sanitized_name = model_name.lower().replace(" ", "-").replace("_", "-")
        # Remove any special characters except hyphens
        import re
        sanitized_name = re.sub(r'[^a-z0-9-]', '', sanitized_name)
        
        bucket_name = settings.object_store_bucket or settings.training_namespace
        # Folder structure: models/{sanitized_name}/{version}/
        # This is for model catalog entries created by training jobs
        storage_path = f"models/{sanitized_name}/{model_version}/"
        storage_uri = f"s3://{bucket_name}/{storage_path}"
        
        logger.info(f"Generated storage URI: {storage_uri} for model {model_name} v{model_version}")
        return storage_uri

    def register_output_model(
        self,
        job_id: str,
        model_name: str,
        model_version: str,
        storage_uri: Optional[str] = None,
        owner_team: str = "ml-platform",
        metadata: Optional[dict] = None,
    ) -> catalog_models.ModelCatalogEntry:
        """
        Register the output model from a completed training job to the catalog.
        
        Args:
            job_id: Training job ID
            model_name: Name for the output model
            model_version: Version for the output model
            storage_uri: Storage URI where the trained model artifacts are stored (optional, auto-generated if not provided)
            owner_team: Owner team for the model
            metadata: Additional metadata for the model
            
        Returns:
            Created ModelCatalogEntry
        """
        job = self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"Training job {job_id} not found")
        
        if job.status != "succeeded":
            raise ValueError(f"Training job {job_id} must be succeeded to register output model")
        
        if job.output_model_entry_id:
            # Model already registered
            existing_model = self.session.get(catalog_models.ModelCatalogEntry, job.output_model_entry_id)
            if existing_model:
                logger.info(f"Model already registered for job {job_id}: {existing_model.id}")
                return existing_model
        
        # Check if model was already registered by training pod (by name, version, type)
        # This can happen if training pod registered the model via API
        from sqlalchemy import select
        model_type = "fine-tuned" if job.job_type == "finetune" else "base"
        stmt = select(catalog_models.ModelCatalogEntry).where(
            catalog_models.ModelCatalogEntry.name == model_name,
            catalog_models.ModelCatalogEntry.version == model_version,
            catalog_models.ModelCatalogEntry.type == model_type
        )
        existing_model = self.session.execute(stmt).scalar_one_or_none()
        if existing_model:
            logger.info(f"Found existing model registered by training pod for job {job_id}: {existing_model.id}")
            # Link the existing model to the job
            job.output_model_entry_id = existing_model.id
            if job.output_model_storage_uri:
                existing_model.storage_uri = job.output_model_storage_uri
                self.session.commit()
            self.job_repo.update(job)
            logger.info(f"Linked existing model {existing_model.id} to training job {job_id}")
            return existing_model
        
        # Use storage URI from job if available (to match the path used by training pod)
        if not storage_uri:
            if job.output_model_storage_uri:
                # Use the storage URI that was used by training pod for file upload
                storage_uri = job.output_model_storage_uri
                logger.info(f"Using storage URI from job {job_id}: {storage_uri}")
            else:
                # Generate new storage URI if not set in job
                storage_uri = self._generate_storage_uri(model_name, model_version, job_id)
                logger.info(f"Generated new storage URI for job {job_id}: {storage_uri}")
        
        # Build metadata
        model_metadata = metadata or {}
        model_metadata.update({
            "training_job_id": str(job.id),
            "job_type": job.job_type,
            "base_model_id": str(job.model_entry_id) if job.model_entry_id else None,
            "dataset_id": str(job.dataset_id),
            "submitted_by": job.submitted_by,
            "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        })
        
        # Get model_family from base model for finetune jobs, or from metadata
        model_family = None
        if job.job_type == "finetune" and job.model_entry_id:
            # For finetune jobs, inherit model_family from base model
            base_model = self.session.get(catalog_models.ModelCatalogEntry, job.model_entry_id)
            if base_model:
                model_family = base_model.model_family
                logger.info(f"Using model_family '{model_family}' from base model {job.model_entry_id}")
        
        # Fallback: try to get from metadata or use default
        if not model_family:
            model_family = model_metadata.get("model_family") or model_metadata.get("architecture")
            if model_family:
                logger.info(f"Using model_family '{model_family}' from metadata")
        
        # Final fallback: use a default based on model name or use "unknown"
        if not model_family:
            # Try to infer from model name (e.g., "llama-7b" -> "llama")
            model_name_lower = model_name.lower()
            known_families = ["llama", "mistral", "gemma", "bert", "gpt", "t5", "roberta"]
            for family in known_families:
                if family in model_name_lower:
                    model_family = family
                    logger.info(f"Inferred model_family '{model_family}' from model name")
                    break
        
        if not model_family:
            # Last resort: use "unknown" but log a warning
            model_family = "unknown"
            logger.warning(
                f"Could not determine model_family for job {job_id}. "
                f"Using 'unknown'. Please update the model after registration."
            )
        
        # Get training metrics for evaluation summary
        metrics = self.get_job_metrics(job_id)
        if metrics:
            evaluation_summary = {
                "training_metrics": {
                    metric.name: {
                        "value": metric.value,
                        "unit": metric.unit,
                        "recorded_at": metric.recorded_at.isoformat() if metric.recorded_at else None,
                    }
                    for metric in metrics
                }
            }
        else:
            evaluation_summary = None
        
        # Create catalog entry (fallback if training pod didn't register it)
        try:
            catalog_service = CatalogService(self.session)
            payload = {
                "name": model_name,
                "version": model_version,
                "type": model_type,
                "owner_team": owner_team,
                "metadata": model_metadata,
                "storage_uri": storage_uri,
                "lineage_dataset_ids": [str(job.dataset_id)],
                "status": "draft",  # Start as draft, user can approve later
                "evaluation_summary": evaluation_summary,
                "model_family": model_family,  # Required field
            }
            
            logger.info(f"Creating catalog entry for training job {job_id} with payload: {payload}")
            model_entry = catalog_service.create_entry(payload)
            logger.info(f"Created catalog entry {model_entry.id} for training job {job_id}")
            
            # Update training job with output model info
            job.output_model_storage_uri = storage_uri
            job.output_model_entry_id = model_entry.id
            self.job_repo.update(job)
            logger.info(f"Updated training job {job_id} with output model info")
            
            logger.info(f"Registered output model {model_entry.id} for training job {job_id}")
            return model_entry
        except Exception as e:
            logger.error(f"Failed to register output model for training job {job_id}: {e}", exc_info=True)
            raise

    def resubmit_job(
        self,
        job_id: str,
        resource_profile: dict,
        use_gpu: bool | None = None,
        submitted_by: str = "system",
    ) -> catalog_models.TrainingJob:
        """
        Resubmit a training job with updated resource profile.
        
        Args:
            job_id: Original job ID to resubmit
            resource_profile: Updated resource profile (GPU/CPU configuration)
            use_gpu: Whether to use GPU (if None, inferred from resource_profile)
            submitted_by: User ID who resubmitted the job
            
        Returns:
            New TrainingJob entity
        """
        # Get original job
        original_job = self.job_repo.get(job_id)
        if not original_job:
            raise ValueError(f"Training job {job_id} not found")
        
        # Determine use_gpu if not provided
        if use_gpu is None:
            # Infer from resource_profile - if it has gpuCount/gpu_count, assume GPU
            use_gpu = "gpuCount" in resource_profile or "gpu_count" in resource_profile
        
        # Validate GPU type if GPU is requested
        environment = settings.environment
        self._validate_gpu_type(resource_profile, use_gpu, environment)
        
        # Extract hyperparameters from original job's resource_profile if stored there
        # Otherwise, we'll need to get it from the original submission context
        # For now, try to get from resource_profile dict
        hyperparameters = None
        if isinstance(original_job.resource_profile, dict):
            hyperparameters = original_job.resource_profile.get("hyperparameters")
        
        # Resubmit with same parameters but updated resource profile
        return self.submit_job(
            model_entry_id=str(original_job.model_entry_id) if original_job.model_entry_id else None,
            dataset_id=str(original_job.dataset_id),
            job_type=original_job.job_type,
            resource_profile=resource_profile,
            hyperparameters=hyperparameters,
            retry_policy=original_job.retry_policy,
            submitted_by=submitted_by,
            use_gpu=use_gpu,
            train_job_spec=TrainJobSpec(**original_job.train_job_spec)
            if hasattr(original_job, "train_job_spec") and original_job.train_job_spec
            else None,
        )

    @staticmethod
    def _build_command(job_type: str, hyperparameters: dict) -> list[str]:
        """Build the command to run in the training container."""
        import json
        
        # Build inline Python script that simulates training
        # This avoids needing the training module in the container
        hyperparameters_json = json.dumps(hyperparameters or {})
        
        # Use triple quotes and escape properly for inline Python execution
        script = f'''import os
import time
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "")
JOB_ID = os.getenv("JOB_ID")
JOB_TYPE = os.getenv("JOB_TYPE", "{job_type}")

# Track if metric recording is available (disable if API_BASE_URL is not set or after first failure)
_metrics_enabled = bool(API_BASE_URL and API_BASE_URL.strip())

# Log API_BASE_URL status at startup
if not API_BASE_URL or not API_BASE_URL.strip():
    logger.info("API_BASE_URL not set - metric recording will be disabled")
else:
    logger.info(f"API_BASE_URL configured: {{API_BASE_URL}} - metric recording enabled")

def record_metric(name, value, unit=None):
    global _metrics_enabled
    # Skip metric recording if disabled or API_BASE_URL is not set
    if not _metrics_enabled or not API_BASE_URL or API_BASE_URL == "":
        return
    try:
        url = f"{{API_BASE_URL}}/training/jobs/{{JOB_ID}}/metrics"
        logger.info(f"Recording metric {{name}}={{value}} {{unit or ''}} to {{url}}")
        response = requests.post(
            url,
            json={{"name": name, "value": value, "unit": unit}},
            headers={{
                "Content-Type": "application/json",
                "X-User-Id": os.getenv("USER_ID", "system"),
                "X-User-Roles": os.getenv("USER_ROLES", "llm-ops-user"),
            }},
            timeout=3,  # Short timeout to fail fast
        )
        if response.status_code == 200:
            # Check response body to ensure metric was actually recorded
            try:
                response_data = response.json()
                if response_data.get("status") == "success":
                    logger.info(f"Recorded metric: {{name}}={{value}} {{unit or ''}}")
                else:
                    # API returned 200 but status is "fail"
                    error_msg = response_data.get("message", "Unknown error")
                    logger.warning(f"Failed to record metric {{name}}: API returned fail status - {{error_msg}}")
            except (ValueError, KeyError) as e:
                # Response is not valid JSON or missing expected fields
                logger.warning(f"Failed to parse metric recording response: {{e}} - {{response.text[:200]}}")
        else:
            # Log non-200 status codes
            logger.warning(f"Failed to record metric {{name}}: HTTP {{response.status_code}} - {{response.text[:200]}}")
    except requests.exceptions.RequestException as e:
        # Log connection errors with details
        logger.warning(f"Failed to record metric {{name}}: {{type(e).__name__}} - {{str(e)}} (URL: {{url}})")
        # Disable metric recording after first failure to avoid spam
        _metrics_enabled = False
        logger.info("Metric recording disabled: API service unavailable (training will continue)")
    except Exception as e:
        # Log other unexpected errors
        logger.warning(f"Unexpected error recording metric {{name}}: {{type(e).__name__}} - {{str(e)}}")
        _metrics_enabled = False
        logger.info("Metric recording disabled due to unexpected error (training will continue)")

if not JOB_ID:
    logger.error("JOB_ID environment variable is required")
    exit(1)

logger.info(f"Starting {{JOB_TYPE}} training job: {{JOB_ID}}")

# Parse hyperparameters
try:
    hyperparameters = json.loads('{hyperparameters_json}')
except:
    hyperparameters = {{}}

# Simulate training
epochs = hyperparameters.get("epochs", 10)
learning_rate = hyperparameters.get("learning_rate", 0.001)
batch_size = hyperparameters.get("batch_size", 32)

logger.info(f"Training config: epochs={{epochs}}, lr={{learning_rate}}, batch_size={{batch_size}}")

for epoch in range(epochs):
    logger.info(f"Epoch {{epoch + 1}}/{{epochs}}")
    time.sleep(2)  # Simulate training time
    
    # Record metrics (optional - failures are logged but don't stop training)
    try:
        loss = 1.0 - (epoch + 1) * 0.08 + (epoch % 3) * 0.02
        accuracy = 0.5 + (epoch + 1) * 0.04 - (epoch % 3) * 0.01
        
        record_metric("loss", max(0.1, loss))
        record_metric("accuracy", min(0.95, accuracy), "percentage")
        
        if (epoch + 1) % 5 == 0:
            record_metric("training_time", (epoch + 1) * 2, "seconds")
    except Exception as e:
        # Log metric recording errors but continue training
        logger.warning(f"Error recording metrics at epoch {{epoch + 1}}: {{e}}")

logger.info("Training completed successfully")

# Upload model files via API if configured
AUTO_UPLOAD_MODEL = os.getenv("AUTO_UPLOAD_MODEL", "false").lower() == "true"
if AUTO_UPLOAD_MODEL:
    try:
        MODEL_STORAGE_URI = os.getenv("MODEL_STORAGE_URI", "")
        OUTPUT_MODEL_NAME = os.getenv("OUTPUT_MODEL_NAME", "")
        OUTPUT_MODEL_VERSION = os.getenv("OUTPUT_MODEL_VERSION", "")
        OWNER_TEAM = os.getenv("OWNER_TEAM", "ml-platform")
        DATASET_ID = os.getenv("DATASET_ID", "")
        
        if not MODEL_STORAGE_URI or not OUTPUT_MODEL_NAME or not OUTPUT_MODEL_VERSION:
            logger.warning("MODEL_STORAGE_URI, OUTPUT_MODEL_NAME, or OUTPUT_MODEL_VERSION not set - skipping model file upload")
        elif not API_BASE_URL or not API_BASE_URL.strip():
            logger.warning("API_BASE_URL not set - cannot upload model files via API")
        else:
            logger.info(f"Starting model file upload via API: {{MODEL_STORAGE_URI}}")
            
            # Find model output directory (common locations)
            model_output_paths = [
                "/workspace/output",
                "/output",
                "./output",
                os.path.join(os.getcwd(), "output"),
            ]
            
            model_path = None
            for path in model_output_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    model_path = path
                    logger.info(f"Found model output directory: {{model_path}}")
                    break
            
            # If no explicit output directory exists, prepare a minimal Hugging Face model directory
            # so that TGI/vLLM can load it. In a real training pipeline, this would be replaced by
            # actual fine-tuned model artifacts saved via model.save_pretrained().
            if not model_path:
                logger.info("No model output directory found - preparing Hugging Face model artifacts")
                model_path = "/tmp/model_output"
                os.makedirs(model_path, exist_ok=True)
                
                try:
                    # Use HF_MODEL_ID from environment (set from base model metadata) or fallback to default
                    hf_model_id = os.getenv("HF_MODEL_ID", "gpt2")
                    logger.info(f"Downloading Hugging Face model {{hf_model_id}} to {{model_path}}")
                    try:
                        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
                    except ImportError as e:
                        logger.warning(f"transformers library is not available in training image: {{e}} - attempting to install...")
                        try:
                            import subprocess
                            import sys
                            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "transformers"])
                            logger.info("Successfully installed transformers")
                            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
                        except Exception as install_error:
                            logger.error(f"Failed to install transformers: {{install_error}}")
                            logger.warning("Cannot prepare Hugging Face model artifacts - skipping model upload")
                            model_path = None
                        else:
                            tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
                            model = AutoModelForCausalLM.from_pretrained(hf_model_id)
                            tokenizer.save_pretrained(model_path)
                            model.save_pretrained(model_path)
                            logger.info(f"Saved Hugging Face model {{hf_model_id}} to {{model_path}}")
                    else:
                        tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
                        model = AutoModelForCausalLM.from_pretrained(hf_model_id)
                        tokenizer.save_pretrained(model_path)
                        model.save_pretrained(model_path)
                        logger.info(f"Saved Hugging Face model {{hf_model_id}} to {{model_path}}")
                except Exception as e:
                    logger.error(f"Failed to prepare Hugging Face model artifacts: {{type(e).__name__}} - {{str(e)}}")
                    logger.warning("Skipping model upload because model artifacts could not be prepared")
                    model_path = None

            # ------------------------------------------------------------
            # Inject chat_template into tokenizer_config.json from chat_template.jinja
            # ------------------------------------------------------------
            target_model_path = model_path or "/tmp/model_output"
            os.makedirs(target_model_path, exist_ok=True)
            template_path = os.path.join(target_model_path, "chat_template.jinja")
            chat_template = ""
            try:
                if os.path.exists(template_path):
                    with open(template_path, "r", encoding="utf-8") as f:
                        chat_template = f.read().strip()
            except Exception as e:
                logger.warning(f"Failed to read chat_template.jinja: {{e}}")
            
            if chat_template:
                tokenizer_config_path = os.path.join(target_model_path, "tokenizer_config.json")
                try:
                    if os.path.exists(tokenizer_config_path):
                        with open(tokenizer_config_path, "r", encoding="utf-8") as f:
                            tokenizer_config = json.load(f)
                    else:
                        tokenizer_config = {{}}
                    tokenizer_config["chat_template"] = chat_template
                    with open(tokenizer_config_path, "w", encoding="utf-8") as f:
                        json.dump(tokenizer_config, f, ensure_ascii=False, indent=2)
                    logger.info(f"Injected chat_template into tokenizer_config.json at {{tokenizer_config_path}}")
                except Exception as e:
                    logger.warning(f"Failed to write chat_template to tokenizer_config.json: {{e}}")
            
            # Collect all model files (only if model_path is valid)
            model_files = []
            if model_path:
                for root, dirs, files in os.walk(model_path):
                    for filename in files:
                        local_filepath = os.path.join(root, filename)
                        rel_path = os.path.relpath(local_filepath, model_path)
                        model_files.append((local_filepath, rel_path))
            else:
                logger.warning("model_path is None - cannot collect model files for upload")
            
            if not model_files:
                logger.warning("No model files found to upload")
            else:
                logger.info(f"Found {{len(model_files)}} model file(s) to upload")
                
                # Step 1: Register model in catalog
                model_type = "fine-tuned" if JOB_TYPE == "finetune" else "base"
                model_metadata = {{
                    "training_job_id": JOB_ID,
                    "job_type": JOB_TYPE,
                }}
                if DATASET_ID:
                    model_metadata["dataset_id"] = DATASET_ID
                
                lineage_dataset_ids = [DATASET_ID] if DATASET_ID else []
                
                # Get model_family from environment variable (set from base model for finetune)
                model_family = os.getenv("BASE_MODEL_FAMILY", "")
                
                # If not set, try to get from base model via API
                if not model_family and JOB_TYPE == "finetune":
                    BASE_MODEL_ID = os.getenv("BASE_MODEL_ID", "")
                    if BASE_MODEL_ID and API_BASE_URL:
                        try:
                            logger.info(f"Fetching model_family from base model {{BASE_MODEL_ID}}")
                            base_model_response = requests.get(
                                f"{{API_BASE_URL}}/catalog/models/{{BASE_MODEL_ID}}",
                                headers={{
                                    "X-User-Id": os.getenv("USER_ID", "system"),
                                    "X-User-Roles": os.getenv("USER_ROLES", "llm-ops-user"),
                                }},
                                timeout=10,
                            )
                            if base_model_response.status_code == 200:
                                base_model_data = base_model_response.json()
                                if base_model_data.get("status") == "success" and base_model_data.get("data"):
                                    model_family = base_model_data["data"].get("model_family", "")
                                    logger.info(f"Retrieved model_family '{{model_family}}' from base model")
                        except Exception as e:
                            logger.warning(f"Failed to fetch base model family: {{e}}")
                
                # Fallback: try to infer from model name
                if not model_family:
                    model_name_lower = OUTPUT_MODEL_NAME.lower()
                    known_families = ["llama", "mistral", "gemma", "bert", "gpt", "t5", "roberta"]
                    for family in known_families:
                        if family in model_name_lower:
                            model_family = family
                            logger.info(f"Inferred model_family '{{model_family}}' from model name")
                            break
                
                # Final fallback
                if not model_family:
                    model_family = "unknown"
                    logger.warning(f"Could not determine model_family, using 'unknown'")
                
                create_payload = {{
                    "name": OUTPUT_MODEL_NAME,
                    "version": OUTPUT_MODEL_VERSION,
                    "type": model_type,
                    "owner_team": OWNER_TEAM,
                    "metadata": model_metadata,
                    "storage_uri": MODEL_STORAGE_URI,
                    "lineage_dataset_ids": lineage_dataset_ids,
                    "status": "draft",
                    "model_family": model_family,  # Required field
                }}
                
                logger.info(f"Registering model in catalog: {{OUTPUT_MODEL_NAME}} v{{OUTPUT_MODEL_VERSION}}")
                create_response = requests.post(
                    f"{{API_BASE_URL}}/catalog/models",
                    json=create_payload,
                    headers={{
                        "Content-Type": "application/json",
                        "X-User-Id": os.getenv("USER_ID", "system"),
                        "X-User-Roles": os.getenv("USER_ROLES", "llm-ops-user"),
                    }},
                    timeout=30,
                )
                
                if create_response.status_code != 201:
                    error_msg = create_response.text[:500] if create_response.text else "Unknown error"
                    logger.error(f"Failed to register model: HTTP {{create_response.status_code}} - {{error_msg}}")
                    raise Exception(f"Model registration failed: {{error_msg}}")
                
                create_result = create_response.json()
                if create_result.get("status") != "success":
                    error_msg = create_result.get("message", "Unknown error")
                    logger.error(f"Failed to register model: {{error_msg}}")
                    raise Exception(f"Model registration failed: {{error_msg}}")
                
                model_id = create_result["data"]["id"]
                logger.info(f"Successfully registered model: {{model_id}}")
                
                # Step 2: Upload model files via API
                logger.info(f"Uploading {{len(model_files)}} file(s) to model {{model_id}}")
                
                # Prepare multipart form data
                files_to_upload = []
                for local_filepath, rel_path in model_files:
                    # Use relative path as filename to preserve directory structure
                    filename = rel_path.replace(os.sep, "/")  # Normalize path separators
                    files_to_upload.append(("files", (filename, open(local_filepath, "rb"), "application/octet-stream")))
                
                upload_response = requests.post(
                    f"{{API_BASE_URL}}/catalog/models/{{model_id}}/upload",
                    files=files_to_upload,
                    headers={{
                        "X-User-Id": os.getenv("USER_ID", "system"),
                        "X-User-Roles": os.getenv("USER_ROLES", "llm-ops-user"),
                    }},
                    timeout=300,  # 5 minutes timeout for large files
                )
                
                # Close file handles
                for _, file_tuple in files_to_upload:
                    file_tuple[1].close()
                
                if upload_response.status_code != 200:
                    error_msg = upload_response.text[:500] if upload_response.text else "Unknown error"
                    logger.error(f"Failed to upload model files: HTTP {{upload_response.status_code}} - {{error_msg}}")
                    raise Exception(f"Model file upload failed: {{error_msg}}")
                
                upload_result = upload_response.json()
                if upload_result.get("status") != "success":
                    error_msg = upload_result.get("message", "Unknown error")
                    logger.error(f"Failed to upload model files: {{error_msg}}")
                    raise Exception(f"Model file upload failed: {{error_msg}}")
                
                uploaded_files = upload_result.get("data", {{}}).get("uploaded_files", [])
                logger.info(f"Successfully uploaded {{len(uploaded_files)}} model file(s) via API")
                logger.info(f"Model registered and uploaded: {{model_id}}")
    except Exception as e:
        logger.error(f"Error during model file upload: {{type(e).__name__}} - {{str(e)}}", exc_info=True)
        # Don't fail training if upload fails
        logger.info("Training completed - model file upload failed but job succeeded")
else:
    logger.info("Auto-upload model files disabled - skipping model upload")
'''
        
        # Return command to execute inline Python script
        return [
            "python",
            "-c",
            script
        ]

