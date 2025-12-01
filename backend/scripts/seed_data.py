#!/usr/bin/env python3
"""Seed script to populate the database with sample data for development and testing."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.database import SessionLocal
from governance.repositories import (
    AuditLogRepository,
    CostProfileRepository,
    GovernancePolicyRepository,
)
from serving.repositories import ServingEndpointRepository
from training.repositories import ExperimentMetricRepository, TrainingJobRepository


def seed_datasets(session: Session) -> list[catalog_models.DatasetRecord]:
    """Create sample datasets."""
    print("Creating sample datasets...")
    
    # Check if datasets already exist
    existing = session.query(catalog_models.DatasetRecord).count()
    if existing > 0:
        print(f"  ⚠ {existing} datasets already exist, skipping...")
        return list(session.query(catalog_models.DatasetRecord).all())
    
    datasets = [
        catalog_models.DatasetRecord(
            id=uuid4(),
            name="customer-support-dataset",
            version="v1.0",
            storage_uri="s3://llm-ops/datasets/customer-support/v1.0",
            owner_team="ml-platform",
            pii_scan_status="clean",
            quality_score=95,
            change_log="Initial version with 10K customer support conversations",
            approved_at=datetime.utcnow() - timedelta(days=30),
            created_at=datetime.utcnow() - timedelta(days=30),
            updated_at=datetime.utcnow() - timedelta(days=30),
        ),
        catalog_models.DatasetRecord(
            id=uuid4(),
            name="code-generation-dataset",
            version="v2.1",
            storage_uri="s3://llm-ops/datasets/code-generation/v2.1",
            owner_team="ml-platform",
            pii_scan_status="clean",
            quality_score=88,
            change_log="Updated with Python 3.11 examples",
            approved_at=datetime.utcnow() - timedelta(days=15),
            created_at=datetime.utcnow() - timedelta(days=20),
            updated_at=datetime.utcnow() - timedelta(days=15),
        ),
        catalog_models.DatasetRecord(
            id=uuid4(),
            name="translation-dataset",
            version="v1.5",
            storage_uri="s3://llm-ops/datasets/translation/v1.5",
            owner_team="nlp-team",
            pii_scan_status="clean",
            quality_score=92,
            change_log="Added Korean-English pairs",
            approved_at=datetime.utcnow() - timedelta(days=7),
            created_at=datetime.utcnow() - timedelta(days=10),
            updated_at=datetime.utcnow() - timedelta(days=7),
        ),
        catalog_models.DatasetRecord(
            id=uuid4(),
            name="qa-dataset",
            version="v1.0",
            storage_uri="s3://llm-ops/datasets/qa/v1.0",
            owner_team="ml-platform",
            pii_scan_status="pending",
            quality_score=None,
            change_log="Initial version - pending approval",
            created_at=datetime.utcnow() - timedelta(days=2),
            updated_at=datetime.utcnow() - timedelta(days=2),
        ),
    ]
    
    for dataset in datasets:
        session.add(dataset)
    session.commit()
    
    print(f"  ✓ Created {len(datasets)} datasets")
    return datasets


def seed_models(session: Session, datasets: list[catalog_models.DatasetRecord]) -> list[catalog_models.ModelCatalogEntry]:
    """Create sample model catalog entries."""
    print("Creating sample models...")
    
    # Check if models already exist
    existing = session.query(catalog_models.ModelCatalogEntry).count()
    if existing > 0:
        print(f"  ⚠ {existing} models already exist, skipping...")
        return list(session.query(catalog_models.ModelCatalogEntry).all())
    
    models = [
        catalog_models.ModelCatalogEntry(
            id=uuid4(),
            name="gpt-4-base",
            version="1.0",
            type="base",
            status="approved",
            owner_team="ml-platform",
            model_metadata={
                "architecture": "transformer",
                "parameters": "175B",
                "framework": "pytorch",
                "license": "proprietary",
            },
            lineage_dataset_ids=[],
            evaluation_summary={
                "accuracy": 0.92,
                "latency_ms": 150,
            },
            created_at=datetime.utcnow() - timedelta(days=60),
            updated_at=datetime.utcnow() - timedelta(days=60),
        ),
        catalog_models.ModelCatalogEntry(
            id=uuid4(),
            name="customer-support-finetuned",
            version="2.0",
            type="fine-tuned",
            status="approved",
            owner_team="ml-platform",
            model_metadata={
                "base_model": "gpt-4-base",
                "base_version": "1.0",
                "training_epochs": 5,
                "learning_rate": 0.0001,
            },
            lineage_dataset_ids=[datasets[0].id],
            evaluation_summary={
                "accuracy": 0.96,
                "latency_ms": 180,
                "f1_score": 0.94,
            },
            created_at=datetime.utcnow() - timedelta(days=25),
            updated_at=datetime.utcnow() - timedelta(days=25),
        ),
        catalog_models.ModelCatalogEntry(
            id=uuid4(),
            name="code-assistant",
            version="1.5",
            type="fine-tuned",
            status="approved",
            owner_team="ml-platform",
            model_metadata={
                "base_model": "gpt-4-base",
                "base_version": "1.0",
                "training_epochs": 3,
                "learning_rate": 0.0002,
            },
            lineage_dataset_ids=[datasets[1].id],
            evaluation_summary={
                "code_accuracy": 0.89,
                "latency_ms": 200,
            },
            created_at=datetime.utcnow() - timedelta(days=20),
            updated_at=datetime.utcnow() - timedelta(days=20),
        ),
        catalog_models.ModelCatalogEntry(
            id=uuid4(),
            name="translation-model",
            version="1.0",
            type="fine-tuned",
            status="under_review",
            owner_team="nlp-team",
            model_metadata={
                "base_model": "gpt-4-base",
                "base_version": "1.0",
                "training_epochs": 4,
            },
            lineage_dataset_ids=[datasets[2].id],
            evaluation_summary=None,
            created_at=datetime.utcnow() - timedelta(days=5),
            updated_at=datetime.utcnow() - timedelta(days=5),
        ),
        catalog_models.ModelCatalogEntry(
            id=uuid4(),
            name="claude-3-opus",
            version="1.0",
            type="external",
            status="approved",
            owner_team="ml-platform",
            model_metadata={
                "provider": "anthropic",
                "api_endpoint": "https://api.anthropic.com/v1/messages",
            },
            lineage_dataset_ids=[],
            evaluation_summary=None,
            created_at=datetime.utcnow() - timedelta(days=40),
            updated_at=datetime.utcnow() - timedelta(days=40),
        ),
    ]
    
    # Link datasets to models
    models[1].datasets.append(datasets[0])
    models[2].datasets.append(datasets[1])
    models[3].datasets.append(datasets[2])
    
    for model in models:
        session.add(model)
    session.commit()
    
    print(f"  ✓ Created {len(models)} models")
    return models


def seed_prompt_templates(session: Session) -> list[catalog_models.PromptTemplate]:
    """Create sample prompt templates."""
    print("Creating sample prompt templates...")
    
    # Check if templates already exist
    existing = session.query(catalog_models.PromptTemplate).count()
    if existing > 0:
        print(f"  ⚠ {existing} prompt templates already exist, skipping...")
        return list(session.query(catalog_models.PromptTemplate).all())
    
    templates = [
        catalog_models.PromptTemplate(
            id=uuid4(),
            name="customer-support-prompt",
            version="v1.0",
            language="en",
            content="You are a helpful customer support assistant. Please respond to the following customer inquiry:\n\n{user_message}",
            context_tags=["customer-support", "help-desk"],
            status="live",
            created_at=datetime.utcnow() - timedelta(days=30),
            updated_at=datetime.utcnow() - timedelta(days=30),
        ),
        catalog_models.PromptTemplate(
            id=uuid4(),
            name="customer-support-prompt-v2",
            version="v2.0",
            language="en",
            content="You are an expert customer support assistant with 10 years of experience. Please provide a detailed and empathetic response to:\n\n{user_message}\n\nRemember to be professional and solution-oriented.",
            context_tags=["customer-support", "help-desk"],
            status="live",
            created_at=datetime.utcnow() - timedelta(days=10),
            updated_at=datetime.utcnow() - timedelta(days=10),
        ),
        catalog_models.PromptTemplate(
            id=uuid4(),
            name="code-generation-prompt",
            version="v1.0",
            language="en",
            content="Generate Python code for the following task:\n\n{task_description}\n\nProvide clean, well-documented code with error handling.",
            context_tags=["code-generation", "python"],
            status="live",
            created_at=datetime.utcnow() - timedelta(days=20),
            updated_at=datetime.utcnow() - timedelta(days=20),
        ),
    ]
    
    for template in templates:
        session.add(template)
    session.commit()
    
    print(f"  ✓ Created {len(templates)} prompt templates")
    return templates


def seed_training_jobs(
    session: Session,
    models: list[catalog_models.ModelCatalogEntry],
    datasets: list[catalog_models.DatasetRecord],
) -> list[catalog_models.TrainingJob]:
    """Create sample training jobs."""
    print("Creating sample training jobs...")
    
    # Check if training jobs already exist
    existing = session.query(catalog_models.TrainingJob).count()
    if existing > 0:
        print(f"  ⚠ {existing} training jobs already exist, skipping...")
        return list(session.query(catalog_models.TrainingJob).all())
    
    # Only use approved models and datasets
    approved_models = [m for m in models if m.status == "approved"]
    approved_datasets = [d for d in datasets if d.approved_at is not None]
    
    if not approved_models or not approved_datasets:
        print("  ⚠ Skipping training jobs - need approved models and datasets")
        return []
    
    jobs = [
        catalog_models.TrainingJob(
            id=uuid4(),
            model_entry_id=approved_models[1].id,  # customer-support-finetuned
            dataset_id=approved_datasets[0].id,
            job_type="finetune",
            resource_profile={
                "gpuCount": 4,
                "gpuType": "nvidia-tesla-v100",
                "maxDurationMinutes": 120,
            },
            retry_policy={"maxRetries": 3, "backoffSeconds": 60},
            status="succeeded",
            submitted_by="user@example.com",
            submitted_at=datetime.utcnow() - timedelta(days=25),
            started_at=datetime.utcnow() - timedelta(days=25, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=25, hours=2),
        ),
        catalog_models.TrainingJob(
            id=uuid4(),
            model_entry_id=approved_models[2].id,  # code-assistant
            dataset_id=approved_datasets[1].id,
            job_type="finetune",
            resource_profile={
                "gpuCount": 8,
                "gpuType": "nvidia-a100",
                "maxDurationMinutes": 180,
            },
            retry_policy={"maxRetries": 2, "backoffSeconds": 120},
            status="succeeded",
            submitted_by="user@example.com",
            submitted_at=datetime.utcnow() - timedelta(days=20),
            started_at=datetime.utcnow() - timedelta(days=20, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=20, hours=3),
        ),
        catalog_models.TrainingJob(
            id=uuid4(),
            model_entry_id=approved_models[0].id,  # gpt-4-base
            dataset_id=approved_datasets[0].id,
            job_type="distributed",
            resource_profile={
                "gpuCount": 16,
                "gpuType": "nvidia-a100",
                "maxDurationMinutes": 240,
            },
            retry_policy={"maxRetries": 1, "backoffSeconds": 300},
            status="running",
            submitted_by="admin@example.com",
            submitted_at=datetime.utcnow() - timedelta(hours=2),
            started_at=datetime.utcnow() - timedelta(hours=2),
            completed_at=None,
        ),
        catalog_models.TrainingJob(
            id=uuid4(),
            model_entry_id=approved_models[1].id,
            dataset_id=approved_datasets[0].id,
            job_type="finetune",
            resource_profile={
                "gpuCount": 2,
                "gpuType": "nvidia-tesla-v100",
                "maxDurationMinutes": 60,
            },
            status="failed",
            submitted_by="user@example.com",
            submitted_at=datetime.utcnow() - timedelta(days=1),
            started_at=datetime.utcnow() - timedelta(days=1, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=1, hours=1, minutes=30),
        ),
    ]
    
    for job in jobs:
        session.add(job)
    session.commit()
    
    # Add metrics for succeeded jobs
    metric_repo = ExperimentMetricRepository(session)
    for job in jobs[:2]:  # First two succeeded jobs
        metrics = [
            catalog_models.ExperimentMetric(
                id=uuid4(),
                training_job_id=job.id,
                name="loss",
                value=0.15,
                unit=None,
                recorded_at=job.completed_at,
            ),
            catalog_models.ExperimentMetric(
                id=uuid4(),
                training_job_id=job.id,
                name="accuracy",
                value=0.94,
                unit="percentage",
                recorded_at=job.completed_at,
            ),
            catalog_models.ExperimentMetric(
                id=uuid4(),
                training_job_id=job.id,
                name="training_time",
                value=job.completed_at.timestamp() - job.started_at.timestamp(),
                unit="seconds",
                recorded_at=job.completed_at,
            ),
        ]
        for metric in metrics:
            metric_repo.create(metric)
    
    print(f"  ✓ Created {len(jobs)} training jobs")
    return jobs


def seed_serving_endpoints(
    session: Session,
    models: list[catalog_models.ModelCatalogEntry],
    templates: list[catalog_models.PromptTemplate],
) -> list[catalog_models.ServingEndpoint]:
    """Create sample serving endpoints."""
    print("Creating sample serving endpoints...")
    
    # Check if endpoints already exist
    existing = session.query(catalog_models.ServingEndpoint).count()
    if existing > 0:
        print(f"  ⚠ {existing} serving endpoints already exist, skipping...")
        return list(session.query(catalog_models.ServingEndpoint).all())
    
    # Only use approved models
    approved_models = [m for m in models if m.status == "approved"]
    
    if not approved_models:
        print("  ⚠ Skipping serving endpoints - need approved models")
        return []
    
    endpoints = [
        catalog_models.ServingEndpoint(
            id=uuid4(),
            model_entry_id=approved_models[1].id,  # customer-support-finetuned
            environment="prod",
            route="/llm-ops/v1/serve/customer-support",
            status="healthy",
            min_replicas=2,
            max_replicas=10,
            autoscale_policy={
                "targetCPU": 70,
                "targetMemory": 80,
            },
            prompt_policy_id=templates[0].id if templates else None,
            last_health_check=datetime.utcnow() - timedelta(minutes=5),
            created_at=datetime.utcnow() - timedelta(days=20),
        ),
        catalog_models.ServingEndpoint(
            id=uuid4(),
            model_entry_id=approved_models[2].id,  # code-assistant
            environment="stg",
            route="/llm-ops/v1/serve/code-assistant",
            status="healthy",
            min_replicas=1,
            max_replicas=5,
            autoscale_policy={
                "targetCPU": 60,
            },
            prompt_policy_id=templates[2].id if len(templates) > 2 else None,
            last_health_check=datetime.utcnow() - timedelta(minutes=2),
            created_at=datetime.utcnow() - timedelta(days=15),
        ),
        catalog_models.ServingEndpoint(
            id=uuid4(),
            model_entry_id=approved_models[0].id,  # gpt-4-base
            environment="dev",
            route="/llm-ops/v1/serve/gpt4-base",
            status="deploying",
            min_replicas=1,
            max_replicas=3,
            last_health_check=None,
            created_at=datetime.utcnow() - timedelta(hours=1),
        ),
    ]
    
    for endpoint in endpoints:
        session.add(endpoint)
    session.commit()
    
    # Add observability snapshots for healthy endpoints
    for endpoint in endpoints[:2]:
        for i in range(5):
            snapshot = catalog_models.ObservabilitySnapshot(
                id=uuid4(),
                serving_endpoint_id=endpoint.id,
                time_bucket=datetime.utcnow() - timedelta(hours=5-i),
                latency_p50=150.0 + (i * 10),
                latency_p95=250.0 + (i * 15),
                error_rate=0.01 + (i * 0.001),
                token_per_request=500.0 + (i * 50),
                notes=f"Snapshot {i+1}",
            )
            session.add(snapshot)
    session.commit()
    
    print(f"  ✓ Created {len(endpoints)} serving endpoints")
    return endpoints


def seed_governance_policies(session: Session) -> list[catalog_models.GovernancePolicy]:
    """Create sample governance policies."""
    print("Creating sample governance policies...")
    
    # Check if policies already exist
    existing = session.query(catalog_models.GovernancePolicy).count()
    if existing > 0:
        print(f"  ⚠ {existing} governance policies already exist, skipping...")
        return list(session.query(catalog_models.GovernancePolicy).all())
    
    policies = [
        catalog_models.GovernancePolicy(
            id=uuid4(),
            name="Model Approval Policy",
            scope="model",
            rules={
                "allowed_actions": ["create", "update"],
                "required_roles": ["llm-ops-admin", "ml-platform-lead"],
                "conditions": [
                    {
                        "type": "resource_limit",
                        "limit": 100,
                    }
                ],
            },
            status="active",
            last_reviewed_at=datetime.utcnow() - timedelta(days=30),
            created_at=datetime.utcnow() - timedelta(days=60),
        ),
        catalog_models.GovernancePolicy(
            id=uuid4(),
            name="Training Cost Limit",
            scope="project",
            rules={
                "allowed_actions": ["submit"],
                "required_roles": ["llm-ops-user"],
                "conditions": [
                    {
                        "type": "cost_limit",
                        "limit": 1000.0,
                    }
                ],
            },
            status="active",
            last_reviewed_at=datetime.utcnow() - timedelta(days=15),
            created_at=datetime.utcnow() - timedelta(days=45),
        ),
        catalog_models.GovernancePolicy(
            id=uuid4(),
            name="Production Deployment Policy",
            scope="model",
            rules={
                "allowed_actions": ["deploy"],
                "required_roles": ["llm-ops-admin"],
                "allowed_resource_types": ["serving_endpoint"],
            },
            status="active",
            last_reviewed_at=datetime.utcnow() - timedelta(days=7),
            created_at=datetime.utcnow() - timedelta(days=30),
        ),
        catalog_models.GovernancePolicy(
            id=uuid4(),
            name="Dataset PII Scan Policy",
            scope="dataset",
            rules={
                "allowed_actions": ["approve"],
                "required_roles": ["llm-ops-admin"],
                "conditions": [
                    {
                        "type": "custom",
                        "field": "pii_scan_status",
                        "value": "clean",
                    }
                ],
            },
            status="draft",
            created_at=datetime.utcnow() - timedelta(days=10),
        ),
    ]
    
    for policy in policies:
        session.add(policy)
    session.commit()
    
    print(f"  ✓ Created {len(policies)} governance policies")
    return policies


def seed_audit_logs(session: Session) -> list[catalog_models.AuditLog]:
    """Create sample audit logs."""
    print("Creating sample audit logs...")
    
    # Check if audit logs already exist (only skip if there are many)
    existing = session.query(catalog_models.AuditLog).count()
    if existing > 10:
        print(f"  ⚠ {existing} audit logs already exist, skipping...")
        return list(session.query(catalog_models.AuditLog).limit(5).all())
    
    logs = [
        catalog_models.AuditLog(
            id=uuid4(),
            actor_id="user@example.com",
            action="create",
            resource_type="model",
            resource_id=None,
            result="allowed",
            log_metadata={"ip": "192.168.1.100"},
            occurred_at=datetime.utcnow() - timedelta(days=25),
        ),
        catalog_models.AuditLog(
            id=uuid4(),
            actor_id="admin@example.com",
            action="approve",
            resource_type="model",
            resource_id=None,
            result="allowed",
            log_metadata={"policy_id": "policy-123"},
            occurred_at=datetime.utcnow() - timedelta(days=24),
        ),
        catalog_models.AuditLog(
            id=uuid4(),
            actor_id="user@example.com",
            action="deploy",
            resource_type="serving_endpoint",
            resource_id=None,
            result="denied",
            log_metadata={
                "reason": "Insufficient roles",
                "policy_id": "policy-456",
            },
            occurred_at=datetime.utcnow() - timedelta(days=20),
        ),
        catalog_models.AuditLog(
            id=uuid4(),
            actor_id="admin@example.com",
            action="deploy",
            resource_type="serving_endpoint",
            resource_id=None,
            result="allowed",
            log_metadata={"environment": "prod"},
            occurred_at=datetime.utcnow() - timedelta(days=19),
        ),
        catalog_models.AuditLog(
            id=uuid4(),
            actor_id="user@example.com",
            action="submit",
            resource_type="training_job",
            resource_id=None,
            result="allowed",
            log_metadata={"job_type": "finetune"},
            occurred_at=datetime.utcnow() - timedelta(days=15),
        ),
    ]
    
    for log in logs:
        session.add(log)
    session.commit()
    
    print(f"  ✓ Created {len(logs)} audit logs")
    return logs


def seed_cost_profiles(
    session: Session,
    models: list[catalog_models.ModelCatalogEntry],
    endpoints: list[catalog_models.ServingEndpoint],
) -> list[catalog_models.CostProfile]:
    """Create sample cost profiles."""
    print("Creating sample cost profiles...")
    
    # Check if cost profiles already exist
    existing = session.query(catalog_models.CostProfile).count()
    if existing > 0:
        print(f"  ⚠ {existing} cost profiles already exist, skipping...")
        return list(session.query(catalog_models.CostProfile).all())
    
    profiles = []
    
    # Cost profiles for training jobs (models)
    for model in models[:3]:  # First 3 models
        profiles.append(
            catalog_models.CostProfile(
                id=uuid4(),
                resource_type="training",
                resource_id=model.id,
                time_window="2024-01",
                gpu_hours=120.5,
                token_count=5000000,
                cost_currency="USD",
                cost_amount=850.50,
                budget_variance=50.50,
                created_at=datetime.utcnow() - timedelta(days=30),
            )
        )
    
    # Cost profiles for serving endpoints
    for endpoint in endpoints:
        profiles.append(
            catalog_models.CostProfile(
                id=uuid4(),
                resource_type="serving",
                resource_id=endpoint.id,
                time_window="2024-01",
                gpu_hours=720.0,
                token_count=10000000,
                cost_currency="USD",
                cost_amount=1200.00,
                budget_variance=-200.00,
                created_at=datetime.utcnow() - timedelta(days=30),
            )
        )
    
    for profile in profiles:
        session.add(profile)
    session.commit()
    
    print(f"  ✓ Created {len(profiles)} cost profiles")
    return profiles


def seed_prompt_experiments(
    session: Session,
    templates: list[catalog_models.PromptTemplate],
) -> list[catalog_models.PromptExperiment]:
    """Create sample prompt experiments."""
    print("Creating sample prompt experiments...")
    
    # Check if experiments already exist
    existing = session.query(catalog_models.PromptExperiment).count()
    if existing > 0:
        print(f"  ⚠ {existing} prompt experiments already exist, skipping...")
        return list(session.query(catalog_models.PromptExperiment).all())
    
    if len(templates) < 2:
        print("  ⚠ Skipping prompt experiments - need at least 2 templates")
        return []
    
    experiments = [
        catalog_models.PromptExperiment(
            id=uuid4(),
            template_a_id=templates[0].id,
            template_b_id=templates[1].id,
            allocation=50,
            metric="user_satisfaction",
            start_at=datetime.utcnow() - timedelta(days=5),
            end_at=None,
            winner_template_id=None,
            created_at=datetime.utcnow() - timedelta(days=5),
        ),
    ]
    
    for experiment in experiments:
        session.add(experiment)
    session.commit()
    
    print(f"  ✓ Created {len(experiments)} prompt experiments")
    return experiments


def main():
    """Main function to seed all data."""
    print("=" * 60)
    print("Seeding database with sample data...")
    print("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Seed in order (respecting foreign key constraints)
        datasets = seed_datasets(session)
        models = seed_models(session, datasets)
        templates = seed_prompt_templates(session)
        training_jobs = seed_training_jobs(session, models, datasets)
        endpoints = seed_serving_endpoints(session, models, templates)
        policies = seed_governance_policies(session)
        audit_logs = seed_audit_logs(session)
        cost_profiles = seed_cost_profiles(session, models, endpoints)
        experiments = seed_prompt_experiments(session, templates)
        
        print("=" * 60)
        print("✓ Database seeding completed successfully!")
        print("=" * 60)
        print(f"\nSummary:")
        print(f"  - Datasets: {len(datasets)}")
        print(f"  - Models: {len(models)}")
        print(f"  - Prompt Templates: {len(templates)}")
        print(f"  - Training Jobs: {len(training_jobs)}")
        print(f"  - Serving Endpoints: {len(endpoints)}")
        print(f"  - Governance Policies: {len(policies)}")
        print(f"  - Audit Logs: {len(audit_logs)}")
        print(f"  - Cost Profiles: {len(cost_profiles)}")
        print(f"  - Prompt Experiments: {len(experiments)}")
        
    except Exception as e:
        session.rollback()
        print(f"\n✗ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

