#!/usr/bin/env python
"""Pre-training script."""
import argparse
import json
import logging
import os
import time

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE_URL = os.getenv("API_BASE_URL", "http://llm-ops-api:8000/llm-ops/v1")


def record_metric(job_id: str, name: str, value: float, unit: str = None):
    """Record a metric for the training job."""
    try:
        url = f"{API_BASE_URL}/training/jobs/{job_id}/metrics"
        response = requests.post(
            url,
            json={"name": name, "value": value, "unit": unit},
            headers={
                "Content-Type": "application/json",
                "X-User-Id": os.getenv("USER_ID", "system"),
                "X-User-Roles": os.getenv("USER_ROLES", "llm-ops-user"),
            },
            timeout=10,
        )
        if response.status_code == 200:
            logger.info(f"Recorded metric: {name}={value} {unit or ''}")
        else:
            logger.warning(f"Failed to record metric: {response.status_code} - {response.text}")
    except Exception as e:
        logger.warning(f"Failed to record metric {name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Pre-training script")
    parser.add_argument("--architecture", type=str, help="Architecture configuration as JSON string")
    parser.add_argument("--hyperparameters", type=str, help="Hyperparameters as JSON string")
    args = parser.parse_args()

    job_id = os.getenv("JOB_ID")
    dataset_id = os.getenv("DATASET_ID")

    if not job_id:
        logger.error("JOB_ID environment variable is required")
        return 1

    logger.info(f"Starting pre-training job: {job_id}")
    logger.info(f"Dataset ID: {dataset_id}")

    # Parse architecture and hyperparameters
    architecture = {}
    hyperparameters = {}
    
    if args.architecture:
        try:
            architecture = json.loads(args.architecture)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse architecture: {args.architecture}")
    
    if args.hyperparameters:
        try:
            hyperparameters = json.loads(args.hyperparameters)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse hyperparameters: {args.hyperparameters}")

    epochs = hyperparameters.get("epochs", 15)
    
    for epoch in range(epochs):
        logger.info(f"Epoch {epoch + 1}/{epochs}")
        time.sleep(2)
        
        loss = 3.0 - (epoch + 1) * 0.15
        record_metric(job_id, "loss", max(0.2, loss))
        record_metric(job_id, "mlm_accuracy", min(0.85, 0.3 + (epoch + 1) * 0.035), "percentage")

    logger.info("Pre-training completed successfully")
    return 0


if __name__ == "__main__":
    exit(main())

