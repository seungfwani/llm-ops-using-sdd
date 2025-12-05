"""Re-validation script for existing training jobs.

This script validates existing training jobs against TrainJobSpec requirements
from training-serving-spec.md. Jobs that don't comply are marked and reported.
"""

from __future__ import annotations

import logging
import sys
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.database import get_session
from training.schemas import TrainJobSpec
from training.validators.train_job_spec_validator import TrainJobSpecValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_training_job(job: catalog_models.TrainingJob, session: Session) -> Dict[str, Any]:
    """
    Validate a single training job against TrainJobSpec requirements.
    
    Args:
        job: TrainingJob entity to validate
        session: Database session
        
    Returns:
        Dictionary with validation results
    """
    result = {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "valid": False,
        "errors": [],
        "warnings": [],
    }
    
    # If job has train_job_spec, validate it directly
    if hasattr(job, 'train_job_spec') and job.train_job_spec:
        try:
            spec = TrainJobSpec(**job.train_job_spec)
            
            # Get base model max_seq_len if available
            base_model_max_seq_len = None
            if spec.base_model_ref and job.model_entry_id:
                model_entry = session.get(catalog_models.ModelCatalogEntry, job.model_entry_id)
                if model_entry and model_entry.model_metadata:
                    base_model_max_seq_len = model_entry.model_metadata.get("max_position_embeddings")
            
            # Validate the spec
            TrainJobSpecValidator.validate(spec, base_model_max_seq_len)
            result["valid"] = True
            logger.info(f"Job {job.id}: Valid TrainJobSpec")
        except Exception as e:
            result["errors"].append(f"TrainJobSpec validation failed: {str(e)}")
            logger.error(f"Job {job.id}: TrainJobSpec validation failed: {e}")
    else:
        # Job doesn't have TrainJobSpec - check if it can be migrated
        result["warnings"].append("Job does not have TrainJobSpec - needs migration")
        
        # Try to infer TrainJobSpec from existing fields
        try:
            # Map old job_type to new format
            job_type_map = {
                "finetune": "SFT",
                "from_scratch": "PRETRAIN",
                "pretrain": "PRETRAIN",
                "distributed": "SFT",  # Default to SFT for distributed
            }
            
            new_job_type = job_type_map.get(job.job_type)
            if not new_job_type:
                result["errors"].append(f"Unknown job_type: {job.job_type}")
                return result
            
            # Get dataset info
            dataset = session.get(catalog_models.DatasetRecord, job.dataset_id)
            if not dataset:
                result["errors"].append(f"Dataset {job.dataset_id} not found")
                return result
            
            # Try to construct a minimal TrainJobSpec for validation
            # Note: This is a best-effort attempt - some fields may be missing
            result["warnings"].append("Cannot fully validate without TrainJobSpec - manual review required")
            result["errors"].append("Job needs to be updated with TrainJobSpec structure")
            
        except Exception as e:
            result["errors"].append(f"Failed to infer TrainJobSpec: {str(e)}")
    
    return result


def validate_all_training_jobs(session: Session, limit: int | None = None) -> List[Dict[str, Any]]:
    """
    Validate all training jobs in the database.
    
    Args:
        session: Database session
        limit: Optional limit on number of jobs to validate
        
    Returns:
        List of validation results
    """
    query = session.query(catalog_models.TrainingJob)
    if limit:
        query = query.limit(limit)
    
    jobs = query.all()
    logger.info(f"Validating {len(jobs)} training jobs...")
    
    results = []
    for job in jobs:
        result = validate_training_job(job, session)
        results.append(result)
    
    return results


def print_validation_report(results: List[Dict[str, Any]]) -> None:
    """Print validation report summary."""
    total = len(results)
    valid = sum(1 for r in results if r["valid"])
    invalid = sum(1 for r in results if r["errors"])
    warnings_only = sum(1 for r in results if r["warnings"] and not r["errors"])
    
    print("\n" + "=" * 80)
    print("Training Jobs Validation Report")
    print("=" * 80)
    print(f"Total jobs validated: {total}")
    print(f"Valid jobs: {valid}")
    print(f"Invalid jobs: {invalid}")
    print(f"Jobs with warnings only: {warnings_only}")
    print("=" * 80)
    
    if invalid > 0:
        print("\nInvalid Jobs:")
        print("-" * 80)
        for result in results:
            if result["errors"]:
                print(f"\nJob ID: {result['job_id']}")
                print(f"  Job Type: {result['job_type']}")
                print(f"  Status: {result['status']}")
                print("  Errors:")
                for error in result["errors"]:
                    print(f"    - {error}")
                if result["warnings"]:
                    print("  Warnings:")
                    for warning in result["warnings"]:
                        print(f"    - {warning}")
    
    if warnings_only > 0:
        print("\nJobs with Warnings (but no errors):")
        print("-" * 80)
        for result in results:
            if result["warnings"] and not result["errors"]:
                print(f"\nJob ID: {result['job_id']}")
                print(f"  Job Type: {result['job_type']}")
                print(f"  Status: {result['status']}")
                print("  Warnings:")
                for warning in result["warnings"]:
                    print(f"    - {warning}")


def main():
    """Main entry point for validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate existing training jobs against TrainJobSpec")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of jobs to validate (for testing)"
    )
    parser.add_argument(
        "--job-id",
        type=str,
        default=None,
        help="Validate specific job by ID"
    )
    
    args = parser.parse_args()
    
    session = next(get_session())
    try:
        if args.job_id:
            # Validate single job
            job = session.get(catalog_models.TrainingJob, args.job_id)
            if not job:
                logger.error(f"Job {args.job_id} not found")
                sys.exit(1)
            
            result = validate_training_job(job, session)
            print_validation_report([result])
        else:
            # Validate all jobs
            results = validate_all_training_jobs(session, limit=args.limit)
            print_validation_report(results)
            
            # Exit with error code if any invalid jobs found
            if any(r["errors"] for r in results):
                sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

