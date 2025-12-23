#!/usr/bin/env python
"""Fine-tuning training script."""
import argparse
import json
import logging
import os
import time
from datetime import datetime

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get API base URL from environment or use default
from core.settings import get_settings

API_BASE_URL = get_settings().training_api_base_url
if not API_BASE_URL:
    raise RuntimeError(
        "Training API base url (training_api_base_url) is NOT set. "
        "환경변수 TRAINING_API_HOSTPORT, TRAINING_API_BASE_PATH 또는 백엔드 .env/helm에 올바로 반영 필요."
    )


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
    parser = argparse.ArgumentParser(description="Fine-tuning training script")
    parser.add_argument("--hyperparameters", type=str, help="Hyperparameters as JSON string")
    args = parser.parse_args()

    # Get job information from environment variables
    job_id = os.getenv("JOB_ID")
    model_entry_id = os.getenv("MODEL_ENTRY_ID")
    dataset_id = os.getenv("DATASET_ID")
    job_type = os.getenv("JOB_TYPE", "finetune")

    if not job_id:
        logger.error("JOB_ID environment variable is required")
        return 1

    logger.info(f"Starting fine-tuning job: {job_id}")
    logger.info(f"Model Entry ID: {model_entry_id}")
    logger.info(f"Dataset ID: {dataset_id}")
    logger.info(f"Hyperparameters: {args.hyperparameters}")

    # Parse hyperparameters
    hyperparameters = {}
    if args.hyperparameters:
        try:
            hyperparameters = json.loads(args.hyperparameters)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse hyperparameters: {args.hyperparameters}")

    # Simulate training process
    epochs = hyperparameters.get("epochs", 10)
    learning_rate = hyperparameters.get("learning_rate", 0.001)
    batch_size = hyperparameters.get("batch_size", 32)

    logger.info(f"Training configuration: epochs={epochs}, lr={learning_rate}, batch_size={batch_size}")

    # Simulate training loop
    for epoch in range(epochs):
        logger.info(f"Epoch {epoch + 1}/{epochs}")
        
        # Simulate training step
        time.sleep(2)  # Simulate training time
        
        # Record metrics
        loss = 1.0 - (epoch + 1) * 0.08 + (epoch % 3) * 0.02  # Simulated loss decreasing
        accuracy = 0.5 + (epoch + 1) * 0.04 - (epoch % 3) * 0.01  # Simulated accuracy increasing
        
        record_metric(job_id, "loss", max(0.1, loss))
        record_metric(job_id, "accuracy", min(0.95, accuracy), "percentage")
        
        if (epoch + 1) % 5 == 0:
            record_metric(job_id, "training_time", (epoch + 1) * 2, "seconds")

    logger.info("Training completed successfully")
    return 0


if __name__ == "__main__":
    exit(main())

