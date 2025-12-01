"""Kubernetes scheduler client for training job orchestration."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class KubernetesScheduler:
    """Client for submitting and managing training jobs on Kubernetes."""

    def __init__(self):
        """Initialize Kubernetes client from kubeconfig or in-cluster config."""
        try:
            if settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                config.load_incluster_config()
        except Exception as e:
            logger.warning(f"Failed to load kubeconfig: {e}, using default")
            try:
                config.load_kube_config()
            except Exception:
                logger.error("Could not initialize Kubernetes client")
                raise

        self.batch_api = client.BatchV1Api()
        self.core_api = client.CoreV1Api()

    def submit_job(
        self,
        job_name: str,
        image: str,
        gpu_count: int,
        gpu_type: str,
        command: list[str],
        env_vars: dict[str, str],
        namespace: str = "default",
    ) -> str:
        """
        Submit a training job to Kubernetes.

        Returns:
            Job UID from Kubernetes
        """
        job_id = str(uuid4())
        container_name = f"{job_name}-trainer"

        # Build environment variables
        env = [
            client.V1EnvVar(name=k, value=str(v)) for k, v in env_vars.items()
        ]

        # GPU resource requests
        resources = client.V1ResourceRequirements(
            requests={
                "nvidia.com/gpu": str(gpu_count),
                "memory": "16Gi",
                "cpu": "4",
            },
            limits={
                "nvidia.com/gpu": str(gpu_count),
                "memory": "32Gi",
                "cpu": "8",
            },
        )

        container = client.V1Container(
            name=container_name,
            image=image,
            command=command,
            env=env,
            resources=resources,
        )

        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": job_name, "job-id": job_id}),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
            ),
        )

        job_spec = client.V1JobSpec(
            template=pod_template,
            backoff_limit=3,  # Retry up to 3 times
            completions=1,
            parallelism=1,
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=namespace,
                labels={"job-id": job_id, "managed-by": "llm-ops-platform"},
            ),
            spec=job_spec,
        )

        try:
            created_job = self.batch_api.create_namespaced_job(
                namespace=namespace, body=job
            )
            logger.info(f"Submitted training job {job_name} with UID {created_job.metadata.uid}")
            return created_job.metadata.uid
        except ApiException as e:
            logger.error(f"Failed to submit job {job_name}: {e}")
            raise

    def get_job_status(
        self, job_name: str, namespace: str = "default"
    ) -> Optional[dict]:
        """Retrieve job status from Kubernetes."""
        try:
            job = self.batch_api.read_namespaced_job(name=job_name, namespace=namespace)
            return {
                "uid": job.metadata.uid,
                "status": self._map_k8s_status(job.status),
                "start_time": job.status.start_time.isoformat() if job.status.start_time else None,
                "completion_time": job.status.completion_time.isoformat() if job.status.completion_time else None,
                "succeeded": job.status.succeeded,
                "failed": job.status.failed,
            }
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Failed to get job status for {job_name}: {e}")
            raise

    def delete_job(self, job_name: str, namespace: str = "default") -> bool:
        """Delete a training job from Kubernetes."""
        try:
            self.batch_api.delete_namespaced_job(
                name=job_name,
                namespace=namespace,
                propagation_policy="Foreground",
            )
            logger.info(f"Deleted training job {job_name}")
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            logger.error(f"Failed to delete job {job_name}: {e}")
            raise

    @staticmethod
    def _map_k8s_status(status) -> str:
        """Map Kubernetes job status to our status enum."""
        if status.succeeded:
            return "succeeded"
        if status.failed:
            return "failed"
        if status.active:
            return "running"
        return "queued"

