"""MLflow client wrapper for experiment tracking.

Provides a wrapper around MLflow REST API for creating runs, logging metrics,
and managing experiments.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class MLflowClient:
    """Client for interacting with MLflow Tracking Server via REST API."""
    
    def __init__(self, tracking_uri: str, timeout: int = 30):
        """Initialize MLflow client.
        
        Args:
            tracking_uri: MLflow Tracking Server URI (e.g., http://mlflow-service:5000)
            timeout: Request timeout in seconds
        """
        self.tracking_uri = tracking_uri.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
    
    async def create_run(
        self,
        experiment_id: str,
        run_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a new MLflow run.
        
        Args:
            experiment_id: Experiment ID (can be experiment name or ID)
            run_name: Optional run name
            tags: Optional tags dictionary
        
        Returns:
            Dictionary with run information:
            {
                "run_id": str,
                "experiment_id": str,
                "status": str
            }
        """
        # First, get or create experiment
        experiment = await self._get_or_create_experiment(experiment_id)
        experiment_id_str = str(experiment["experiment_id"])
        
        # Create run
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/create"
        payload = {
            "experiment_id": experiment_id_str,
            "start_time": int(datetime.utcnow().timestamp() * 1000),
            "tags": [{"key": k, "value": v} for k, v in (tags or {}).items()],
        }
        if run_name:
            payload["tags"].append({"key": "mlflow.runName", "value": run_name})
        
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return {
                "run_id": data["run"]["info"]["run_id"],
                "experiment_id": experiment_id_str,
                "status": data["run"]["info"]["status"],
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to create MLflow run: {e}")
            raise
    
    async def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics for a run.
        
        Args:
            run_id: Run ID
            metrics: Dictionary of metric names to values
            step: Optional step number
        """
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/log-metric"
        
        for metric_name, metric_value in metrics.items():
            payload = {
                "run_id": run_id,
                "key": metric_name,
                "value": float(metric_value),
            }
            if step is not None:
                payload["step"] = int(step)
            
            try:
                response = await self._client.post(url, json=payload)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Failed to log metric {metric_name}: {e}")
                raise
    
    async def log_params(
        self,
        run_id: str,
        params: Dict[str, Any],
    ) -> None:
        """Log parameters for a run.
        
        Args:
            run_id: Run ID
            params: Dictionary of parameter names to values
        """
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/log-parameter"
        
        for param_name, param_value in params.items():
            payload = {
                "run_id": run_id,
                "key": param_name,
                "value": str(param_value),  # MLflow requires string values
            }
            
            try:
                response = await self._client.post(url, json=payload)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Failed to log parameter {param_name}: {e}")
                raise
    
    async def log_artifact_uri(
        self,
        run_id: str,
        artifact_path: str,
        artifact_uri: str,
    ) -> None:
        """Log artifact URI for a run.
        
        Args:
            run_id: Run ID
            artifact_path: Logical path/name for the artifact
            artifact_uri: Storage URI of the artifact
        """
        # MLflow doesn't have a direct API for logging artifact URIs
        # Instead, we log it as a tag
        await self.set_tag(run_id, f"artifact.{artifact_path}", artifact_uri)
    
    async def set_tag(self, run_id: str, key: str, value: str) -> None:
        """Set a tag on a run.
        
        Args:
            run_id: Run ID
            key: Tag key
            value: Tag value
        """
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/set-tag"
        payload = {
            "run_id": run_id,
            "key": key,
            "value": value,
        }
        
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to set tag {key}: {e}")
            raise
    
    async def update_run_status(
        self,
        run_id: str,
        status: str,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Update run status.
        
        Args:
            run_id: Run ID
            status: New status ("RUNNING", "FINISHED", "FAILED", "KILLED")
            end_time: Optional end time
        """
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/update"
        payload = {
            "run_id": run_id,
            "status": status.upper(),
        }
        if end_time:
            payload["end_time"] = int(end_time.timestamp() * 1000)
        
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to update run status: {e}")
            raise
    
    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """Get run information.
        
        Args:
            run_id: Run ID
        
        Returns:
            Dictionary with run details
        """
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/get"
        params = {"run_id": run_id}
        
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            run_info = data["run"]["info"]
            run_data = data["run"]["data"]
            
            return {
                "run_id": run_info["run_id"],
                "experiment_id": run_info["experiment_id"],
                "status": run_info["status"],
                "parameters": {p["key"]: p["value"] for p in run_data.get("params", [])},
                "metrics": {m["key"]: m["value"] for m in run_data.get("metrics", [])},
                "artifact_uris": [tag["value"] for tag in run_data.get("tags", []) if tag["key"].startswith("artifact.")],
                "start_time": datetime.fromtimestamp(run_info["start_time"] / 1000),
                "end_time": datetime.fromtimestamp(run_info["end_time"] / 1000) if run_info.get("end_time") else None,
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to get run: {e}")
            raise
    
    async def search_runs(
        self,
        experiment_ids: Optional[List[str]] = None,
        filter_string: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for experiment runs.
        
        Args:
            experiment_ids: Optional list of experiment IDs to search
            filter_string: Optional filter expression (MLflow filter syntax)
            max_results: Maximum number of results
        
        Returns:
            List of run dictionaries
        """
        url = f"{self.tracking_uri}/api/2.0/mlflow/runs/search"
        payload = {
            "experiment_ids": experiment_ids or [],
            "max_results": max_results,
        }
        if filter_string:
            payload["filter"] = filter_string
        
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            runs = []
            for run in data.get("runs", []):
                run_info = run["info"]
                run_data = run["data"]
                runs.append({
                    "run_id": run_info["run_id"],
                    "experiment_id": run_info["experiment_id"],
                    "status": run_info["status"],
                    "parameters": {p["key"]: p["value"] for p in run_data.get("params", [])},
                    "metrics": {m["key"]: m["value"] for m in run_data.get("metrics", [])},
                    "start_time": datetime.fromtimestamp(run_info["start_time"] / 1000),
                    "end_time": datetime.fromtimestamp(run_info["end_time"] / 1000) if run_info.get("end_time") else None,
                })
            
            return runs
        except httpx.HTTPError as e:
            logger.error(f"Failed to search runs: {e}")
            raise
    
    async def _get_or_create_experiment(self, experiment_name: str) -> Dict[str, Any]:
        """Get or create an experiment.
        
        Args:
            experiment_name: Experiment name
        
        Returns:
            Dictionary with experiment information
        """
        # Try to get experiment by name
        url = f"{self.tracking_uri}/api/2.0/mlflow/experiments/get-by-name"
        params = {"experiment_name": experiment_name}
        
        try:
            response = await self._client.get(url, params=params)
            if response.status_code == 200:
                return response.json()["experiment"]
        except httpx.HTTPError:
            pass
        
        # Create experiment if it doesn't exist
        url = f"{self.tracking_uri}/api/2.0/mlflow/experiments/create"
        payload = {"name": experiment_name}
        
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            return response.json()["experiment"]
        except httpx.HTTPError as e:
            logger.error(f"Failed to create experiment: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MLflow service health.
        
        Returns:
            Dictionary with health status
        """
        try:
            url = f"{self.tracking_uri}/health"
            response = await self._client.get(url, timeout=5)
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "MLflow service is available",
                    "details": {},
                }
            else:
                return {
                    "status": "degraded",
                    "message": f"MLflow service returned status {response.status_code}",
                    "details": {},
                }
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"MLflow service is unavailable: {str(e)}",
                "details": {"error": str(e)},
            }
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

