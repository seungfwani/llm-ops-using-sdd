from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


class ModelCatalogRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> Sequence[models.ModelCatalogEntry]:
        return self.session.execute(select(models.ModelCatalogEntry)).scalars().all()

    def get(self, entry_id: str | UUID) -> models.ModelCatalogEntry | None:
        try:
            uuid_id = UUID(entry_id) if isinstance(entry_id, str) else entry_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.ModelCatalogEntry, uuid_id)

    def save(self, entry: models.ModelCatalogEntry) -> models.ModelCatalogEntry:
        self.session.add(entry)
        return entry

    def delete(self, entry_id: str | UUID) -> bool:
        """Delete a model catalog entry by ID. Returns True if deleted, False if not found."""
        entry = self.get(entry_id)
        if not entry:
            return False
        self.session.delete(entry)
        return True

    def get_by_name_type_version(
        self, name: str, model_type: str, version: str
    ) -> models.ModelCatalogEntry | None:
        """Get a model catalog entry by name, type, and version combination."""
        stmt = select(models.ModelCatalogEntry).where(
            models.ModelCatalogEntry.name == name,
            models.ModelCatalogEntry.type == model_type,
            models.ModelCatalogEntry.version == version,
        )
        return self.session.execute(stmt).scalar_one_or_none()


class ExperimentRunRepository:
    """Repository for ExperimentRun entities."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, experiment_run: models.ExperimentRun) -> models.ExperimentRun:
        """Create a new experiment run."""
        self.session.add(experiment_run)
        self.session.commit()
        self.session.refresh(experiment_run)
        return experiment_run
    
    def get(self, run_id: str | UUID) -> models.ExperimentRun | None:
        """Get experiment run by ID."""
        try:
            uuid_id = UUID(run_id) if isinstance(run_id, str) else run_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.ExperimentRun, uuid_id)
    
    def get_by_training_job_id(self, training_job_id: str | UUID) -> models.ExperimentRun | None:
        """Get experiment run by training job ID."""
        try:
            uuid_id = UUID(training_job_id) if isinstance(training_job_id, str) else training_job_id
        except (ValueError, TypeError):
            return None
        stmt = select(models.ExperimentRun).where(
            models.ExperimentRun.training_job_id == uuid_id
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def update(self, experiment_run: models.ExperimentRun) -> models.ExperimentRun:
        """Update an existing experiment run."""
        self.session.commit()
        self.session.refresh(experiment_run)
        return experiment_run
    
    def list(
        self,
        training_job_id: str | UUID | None = None,
        experiment_name: str | None = None,
        status: str | None = None,
    ) -> Sequence[models.ExperimentRun]:
        """List experiment runs with optional filters."""
        stmt = select(models.ExperimentRun)
        
        if training_job_id:
            try:
                uuid_id = UUID(training_job_id) if isinstance(training_job_id, str) else training_job_id
                stmt = stmt.where(models.ExperimentRun.training_job_id == uuid_id)
            except (ValueError, TypeError):
                pass
        
        if experiment_name:
            stmt = stmt.where(models.ExperimentRun.experiment_name == experiment_name)
        
        if status:
            stmt = stmt.where(models.ExperimentRun.status == status)
        
        return self.session.execute(stmt).scalars().all()


class DatasetRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> Sequence[models.DatasetRecord]:
        return self.session.execute(select(models.DatasetRecord)).scalars().all()

    def get(self, dataset_id: str | UUID) -> models.DatasetRecord | None:
        try:
            uuid_id = UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.DatasetRecord, uuid_id)

    def save(self, dataset: models.DatasetRecord) -> models.DatasetRecord:
        self.session.add(dataset)
        return dataset

    def fetch_by_ids(self, dataset_ids: Sequence[str]) -> Sequence[models.DatasetRecord]:
        stmt = select(models.DatasetRecord).where(models.DatasetRecord.id.in_(dataset_ids))
        return self.session.execute(stmt).scalars().all()

    def get_by_name_version(self, name: str, version: str) -> models.DatasetRecord | None:
        """Get a dataset by name and version combination."""
        stmt = select(models.DatasetRecord).where(
            models.DatasetRecord.name == name,
            models.DatasetRecord.version == version
        )
        return self.session.execute(stmt).scalar_one_or_none()


class ServingDeploymentRepository:
    """Repository for ServingDeployment entities."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, deployment: models.ServingDeployment) -> models.ServingDeployment:
        """Create a new serving deployment."""
        self.session.add(deployment)
        self.session.commit()
        self.session.refresh(deployment)
        return deployment
    
    def get(self, deployment_id: str | UUID) -> models.ServingDeployment | None:
        """Get deployment by ID."""
        try:
            uuid_id = UUID(deployment_id) if isinstance(deployment_id, str) else deployment_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.ServingDeployment, uuid_id)
    
    def get_by_endpoint_id(self, endpoint_id: str | UUID) -> models.ServingDeployment | None:
        """Get deployment by serving endpoint ID."""
        try:
            uuid_id = UUID(endpoint_id) if isinstance(endpoint_id, str) else endpoint_id
        except (ValueError, TypeError):
            return None
        stmt = select(models.ServingDeployment).where(
            models.ServingDeployment.serving_endpoint_id == uuid_id
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def update(self, deployment: models.ServingDeployment) -> models.ServingDeployment:
        """Update an existing deployment."""
        self.session.commit()
        self.session.refresh(deployment)
        return deployment
    
    def delete(self, deployment_id: str | UUID) -> bool:
        """Delete a deployment by ID."""
        deployment = self.get(deployment_id)
        if not deployment:
            return False
        self.session.delete(deployment)
        self.session.commit()
        return True


class WorkflowPipelineRepository:
    """Repository for WorkflowPipeline entities."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, pipeline: models.WorkflowPipeline) -> models.WorkflowPipeline:
        """Create a new workflow pipeline."""
        self.session.add(pipeline)
        self.session.commit()
        self.session.refresh(pipeline)
        return pipeline
    
    def get(self, pipeline_id: str | UUID) -> models.WorkflowPipeline | None:
        """Get pipeline by ID."""
        try:
            uuid_id = UUID(pipeline_id) if isinstance(pipeline_id, str) else pipeline_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.WorkflowPipeline, uuid_id)
    
    def get_by_workflow_id(
        self,
        workflow_id: str,
        orchestration_system: str,
        workflow_namespace: str,
    ) -> models.WorkflowPipeline | None:
        """Get pipeline by workflow ID, orchestration system, and namespace."""
        stmt = select(models.WorkflowPipeline).where(
            models.WorkflowPipeline.workflow_id == workflow_id,
            models.WorkflowPipeline.orchestration_system == orchestration_system,
            models.WorkflowPipeline.workflow_namespace == workflow_namespace,
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def update(self, pipeline: models.WorkflowPipeline) -> models.WorkflowPipeline:
        """Update an existing pipeline."""
        self.session.commit()
        self.session.refresh(pipeline)
        return pipeline
    
    def delete(self, pipeline_id: str | UUID) -> bool:
        """Delete a pipeline by ID."""
        pipeline = self.get(pipeline_id)
        if not pipeline:
            return False
        self.session.delete(pipeline)
        self.session.commit()
        return True
    
    def list(
        self,
        status: str | None = None,
        orchestration_system: str | None = None,
        workflow_namespace: str | None = None,
    ) -> Sequence[models.WorkflowPipeline]:
        """List pipelines with optional filters."""
        stmt = select(models.WorkflowPipeline)
        
        if status:
            stmt = stmt.where(models.WorkflowPipeline.status == status)
        
        if orchestration_system:
            stmt = stmt.where(models.WorkflowPipeline.orchestration_system == orchestration_system)
        
        if workflow_namespace:
            stmt = stmt.where(models.WorkflowPipeline.workflow_namespace == workflow_namespace)
        
        return self.session.execute(stmt.order_by(models.WorkflowPipeline.created_at.desc())).scalars().all()


class RegistryModelRepository:
    """Repository for RegistryModel entities."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, registry_model: models.RegistryModel) -> models.RegistryModel:
        """Create a new registry model link."""
        self.session.add(registry_model)
        self.session.commit()
        self.session.refresh(registry_model)
        return registry_model
    
    def get(self, registry_model_id: str | UUID) -> models.RegistryModel | None:
        """Get registry model by ID."""
        try:
            uuid_id = UUID(registry_model_id) if isinstance(registry_model_id, str) else registry_model_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.RegistryModel, uuid_id)
    
    def list_by_model_catalog_id(
        self,
        model_catalog_id: str | UUID,
    ) -> Sequence[models.RegistryModel]:
        """List all registry links for a given catalog model."""
        try:
            uuid_id = UUID(model_catalog_id) if isinstance(model_catalog_id, str) else model_catalog_id
        except (ValueError, TypeError):
            return []
        stmt = select(models.RegistryModel).where(
            models.RegistryModel.model_catalog_id == uuid_id
        )
        return self.session.execute(stmt).scalars().all()
    
    def get_by_model_and_registry(
        self,
        model_catalog_id: str | UUID,
        registry_type: str,
        registry_model_id: str,
    ) -> models.RegistryModel | None:
        """Get a registry link for a given catalog model and registry identifier."""
        try:
            uuid_id = UUID(model_catalog_id) if isinstance(model_catalog_id, str) else model_catalog_id
        except (ValueError, TypeError):
            return None
        stmt = select(models.RegistryModel).where(
            models.RegistryModel.model_catalog_id == uuid_id,
            models.RegistryModel.registry_type == registry_type,
            models.RegistryModel.registry_model_id == registry_model_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def delete(self, registry_model_id: str | UUID) -> bool:
        """Delete a registry model link by ID."""
        registry_model = self.get(registry_model_id)
        if not registry_model:
            return False
        self.session.delete(registry_model)
        self.session.commit()
        return True


class DatasetVersionRepository:
    """Repository for DatasetVersion entities."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, version: models.DatasetVersion) -> models.DatasetVersion:
        """Create a new dataset version."""
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)
        return version
    
    def get(self, version_id: str | UUID) -> models.DatasetVersion | None:
        """Get dataset version by ID."""
        try:
            uuid_id = UUID(version_id) if isinstance(version_id, str) else version_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.DatasetVersion, uuid_id)
    
    def get_by_version_id(
        self,
        version_id: str,
        dataset_record_id: str | UUID,
    ) -> models.DatasetVersion | None:
        """Get dataset version by versioning system version ID."""
        try:
            uuid_id = UUID(dataset_record_id) if isinstance(dataset_record_id, str) else dataset_record_id
        except (ValueError, TypeError):
            return None
        stmt = select(models.DatasetVersion).where(
            models.DatasetVersion.version_id == version_id,
            models.DatasetVersion.dataset_record_id == uuid_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_by_dataset_id(
        self,
        dataset_record_id: str | UUID,
        limit: int = 100,
    ) -> Sequence[models.DatasetVersion]:
        """List all versions for a dataset."""
        try:
            uuid_id = UUID(dataset_record_id) if isinstance(dataset_record_id, str) else dataset_record_id
        except (ValueError, TypeError):
            return []
        stmt = select(models.DatasetVersion).where(
            models.DatasetVersion.dataset_record_id == uuid_id
        ).order_by(
            models.DatasetVersion.created_at.desc()
        ).limit(limit)
        return self.session.execute(stmt).scalars().all()
    
    def update(self, version: models.DatasetVersion) -> models.DatasetVersion:
        """Update an existing dataset version."""
        self.session.commit()
        self.session.refresh(version)
        return version
    
    def delete(self, version_id: str | UUID) -> bool:
        """Delete a dataset version by ID."""
        version = self.get(version_id)
        if not version:
            return False
        self.session.delete(version)
        self.session.commit()
        return True

