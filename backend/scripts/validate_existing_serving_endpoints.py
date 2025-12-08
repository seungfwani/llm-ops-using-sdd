"""Re-validation script for existing serving endpoints.

This script validates existing serving endpoints against DeploymentSpec requirements
from training-serving-spec.md. Endpoints that don't comply are marked and reported.
"""

from __future__ import annotations

import logging
import sys
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.database import get_session
from serving.schemas import DeploymentSpec
from serving.validators.deployment_spec_validator import DeploymentSpecValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_serving_endpoint(endpoint: catalog_models.ServingEndpoint, session: Session) -> Dict[str, Any]:
    """
    Validate a single serving endpoint against DeploymentSpec requirements.
    
    Args:
        endpoint: ServingEndpoint entity to validate
        session: Database session
        
    Returns:
        Dictionary with validation results
    """
    result = {
        "endpoint_id": str(endpoint.id),
        "environment": endpoint.environment,
        "route": endpoint.route,
        "status": endpoint.status,
        "valid": False,
        "errors": [],
        "warnings": [],
    }
    
    # If endpoint has deployment_spec, validate it directly
    if hasattr(endpoint, 'deployment_spec') and endpoint.deployment_spec:
        try:
            spec = DeploymentSpec(**endpoint.deployment_spec)
            
            # Get training model family and max_seq_len if available
            training_model_family = None
            model_max_seq_len = None
            if endpoint.model_entry_id:
                model_entry = session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
                if model_entry and model_entry.model_metadata:
                    training_model_family = model_entry.model_metadata.get("model_family")
                    model_max_seq_len = model_entry.model_metadata.get("max_position_embeddings")
            
            # Validate the spec
            DeploymentSpecValidator.validate(
                spec,
                training_model_family,
                model_max_seq_len
            )
            result["valid"] = True
            logger.info(f"Endpoint {endpoint.id}: Valid DeploymentSpec")
        except Exception as e:
            result["errors"].append(f"DeploymentSpec validation failed: {str(e)}")
            logger.error(f"Endpoint {endpoint.id}: DeploymentSpec validation failed: {e}")
    else:
        # Endpoint doesn't have DeploymentSpec - check if it can be migrated
        result["warnings"].append("Endpoint does not have DeploymentSpec - needs migration")
        
        # Try to infer DeploymentSpec from existing fields
        try:
            # Get model entry to infer job_type and model_family
            if endpoint.model_entry_id:
                model_entry = session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
                if model_entry:
                    # Try to infer serve_target from model metadata or runtime image
                    serve_target = "GENERATION"  # Default
                    if endpoint.runtime_image:
                        if "rag" in endpoint.runtime_image.lower():
                            serve_target = "RAG"
                    
                    result["warnings"].append(
                        f"Inferred serve_target: {serve_target} (from runtime_image)"
                    )
                else:
                    result["errors"].append(f"Model entry {endpoint.model_entry_id} not found")
            else:
                result["errors"].append("Endpoint has no model_entry_id")
            
            result["errors"].append("Endpoint needs to be updated with DeploymentSpec structure")
            
        except Exception as e:
            result["errors"].append(f"Failed to infer DeploymentSpec: {str(e)}")
    
    return result


def validate_all_serving_endpoints(session: Session, limit: int | None = None) -> List[Dict[str, Any]]:
    """
    Validate all serving endpoints in the database.
    
    Args:
        session: Database session
        limit: Optional limit on number of endpoints to validate
        
    Returns:
        List of validation results
    """
    query = session.query(catalog_models.ServingEndpoint)
    if limit:
        query = query.limit(limit)
    
    endpoints = query.all()
    logger.info(f"Validating {len(endpoints)} serving endpoints...")
    
    results = []
    for endpoint in endpoints:
        result = validate_serving_endpoint(endpoint, session)
        results.append(result)
    
    return results


def print_validation_report(results: List[Dict[str, Any]]) -> None:
    """Print validation report summary."""
    total = len(results)
    valid = sum(1 for r in results if r["valid"])
    invalid = sum(1 for r in results if r["errors"])
    warnings_only = sum(1 for r in results if r["warnings"] and not r["errors"])
    
    print("\n" + "=" * 80)
    print("Serving Endpoints Validation Report")
    print("=" * 80)
    print(f"Total endpoints validated: {total}")
    print(f"Valid endpoints: {valid}")
    print(f"Invalid endpoints: {invalid}")
    print(f"Endpoints with warnings only: {warnings_only}")
    print("=" * 80)
    
    if invalid > 0:
        print("\nInvalid Endpoints:")
        print("-" * 80)
        for result in results:
            if result["errors"]:
                print(f"\nEndpoint ID: {result['endpoint_id']}")
                print(f"  Environment: {result['environment']}")
                print(f"  Route: {result['route']}")
                print(f"  Status: {result['status']}")
                print("  Errors:")
                for error in result["errors"]:
                    print(f"    - {error}")
                if result["warnings"]:
                    print("  Warnings:")
                    for warning in result["warnings"]:
                        print(f"    - {warning}")
    
    if warnings_only > 0:
        print("\nEndpoints with Warnings (but no errors):")
        print("-" * 80)
        for result in results:
            if result["warnings"] and not result["errors"]:
                print(f"\nEndpoint ID: {result['endpoint_id']}")
                print(f"  Environment: {result['environment']}")
                print(f"  Route: {result['route']}")
                print(f"  Status: {result['status']}")
                print("  Warnings:")
                for warning in result["warnings"]:
                    print(f"    - {warning}")


def main():
    """Main entry point for validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate existing serving endpoints against DeploymentSpec")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of endpoints to validate (for testing)"
    )
    parser.add_argument(
        "--endpoint-id",
        type=str,
        default=None,
        help="Validate specific endpoint by ID"
    )
    
    args = parser.parse_args()
    
    session = next(get_session())
    try:
        if args.endpoint_id:
            # Validate single endpoint
            endpoint = session.get(catalog_models.ServingEndpoint, args.endpoint_id)
            if not endpoint:
                logger.error(f"Endpoint {args.endpoint_id} not found")
                sys.exit(1)
            
            result = validate_serving_endpoint(endpoint, session)
            print_validation_report([result])
        else:
            # Validate all endpoints
            results = validate_all_serving_endpoints(session, limit=args.limit)
            print_validation_report(results)
            
            # Exit with error code if any invalid endpoints found
            if any(r["errors"] for r in results):
                sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

