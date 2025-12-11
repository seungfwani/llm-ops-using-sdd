"""Kubernetes scheduler client for training job orchestration."""
from __future__ import annotations

import logging
import time
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
                logger.info(f"KubernetesScheduler: Loading Kubernetes config from: {settings.kubeconfig_path}")
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                logger.info("KubernetesScheduler: Loading in-cluster Kubernetes config")
                config.load_incluster_config()
        except Exception as e:
            logger.warning(f"KubernetesScheduler: Failed to load kubeconfig: {e}, using default")
            try:
                logger.info("KubernetesScheduler: Trying default kubeconfig location")
                config.load_kube_config()
            except Exception:
                logger.error("KubernetesScheduler: Could not initialize Kubernetes client")
                raise

        # Configure SSL verification based on settings
        configuration = client.Configuration.get_default_copy()
        if not settings.kubernetes_verify_ssl:
            logger.warning("KubernetesScheduler: SSL verification is disabled for Kubernetes API client")
            configuration.verify_ssl = False
            # Also disable SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            # Update all API clients to use this configuration
            client.Configuration.set_default(configuration)

        self.batch_api = client.BatchV1Api()
        self.core_api = client.CoreV1Api()
        
        # Test Kubernetes connection (non-blocking - failure doesn't prevent initialization)
        # This allows the scheduler to be created even if cluster is temporarily unavailable
        self._connection_verified = False
        try:
            logger.info("KubernetesScheduler: Testing Kubernetes API connection...")
            # Test connection by listing namespaces (simple API call)
            namespaces = self.core_api.list_namespace(limit=1)
            self._connection_verified = True
            logger.info(f"KubernetesScheduler: Kubernetes API connection successful. Cluster accessible (tested via namespace list)")
        except ApiException as e:
            # Handle API errors (401, 403, etc.) gracefully
            if e.status == 401:
                logger.warning(
                    f"KubernetesScheduler: Kubernetes API authentication failed (401 Unauthorized). "
                    f"This is normal if running outside Kubernetes cluster or with invalid kubeconfig. "
                    f"Scheduler will be available but operations may fail until authentication is configured."
                )
            elif e.status == 403:
                logger.warning(
                    f"KubernetesScheduler: Kubernetes API permission denied (403 Forbidden). "
                    f"Scheduler will be available but operations may fail due to insufficient permissions."
                )
            else:
                logger.warning(
                    f"KubernetesScheduler: Failed to connect to Kubernetes API (status {e.status}): {e.reason}. "
                    f"Scheduler will be available but operations may fail until connection is established."
                )
        except Exception as e:
            # Handle other connection errors (network, config, etc.)
            logger.warning(
                f"KubernetesScheduler: Failed to verify Kubernetes API connection: {e}. "
                f"Scheduler will be available but operations may fail until connection is established."
            )

    def submit_job(
        self,
        job_name: str,
        image: str,
        gpu_count: int,
        gpu_type: str,
        command: list[str],
        env_vars: dict[str, str],
        namespace: str | None = None,
    ) -> str:
        """
        Submit a single-node training job to Kubernetes.

        Returns:
            Job UID from Kubernetes
        """
        if namespace is None:
            namespace = settings.training_namespace
        
        job_id = str(uuid4())
        container_name = f"{job_name}-trainer"

        # Build environment variables
        env = [
            client.V1EnvVar(name=k, value=str(v)) for k, v in env_vars.items()
        ]

        # GPU resource requests (from settings)
        resources = client.V1ResourceRequirements(
            requests={
                "nvidia.com/gpu": str(gpu_count),
                "memory": settings.training_gpu_memory_request,
                "cpu": settings.training_gpu_cpu_request,
            },
            limits={
                "nvidia.com/gpu": str(gpu_count),
                "memory": settings.training_gpu_memory_limit,
                "cpu": settings.training_gpu_cpu_limit,
            },
        )

        container = client.V1Container(
            name=container_name,
            image=image,
            command=command,
            env=env,
            resources=resources,
        )

        # Build node selector and tolerations for GPU nodes
        node_selector = settings.training_gpu_node_selector.copy() if settings.training_gpu_node_selector else {}
        tolerations = []
        if settings.training_gpu_tolerations:
            for tol in settings.training_gpu_tolerations:
                tolerations.append(client.V1Toleration(**tol))

        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": job_name, "job-id": job_id}),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                node_selector=node_selector if node_selector else None,
                tolerations=tolerations if tolerations else None,
            ),
        )

        job_spec = client.V1JobSpec(
            template=pod_template,
            backoff_limit=3,  # Retry up to 3 times
            completions=1,
            parallelism=1,
            ttl_seconds_after_finished=300,  # Delete pods 5 minutes after completion
        )

        # Check if job already exists
        try:
            existing_job = self.batch_api.read_namespaced_job(
                name=job_name,
                namespace=namespace
            )
            if existing_job:
                logger.warning(f"Job {job_name} already exists, deleting it first")
                # Delete existing job
                self.batch_api.delete_namespaced_job(
                    name=job_name,
                    namespace=namespace,
                    body=client.V1DeleteOptions(propagation_policy="Foreground")
                )
                # Wait a bit for deletion to complete
                time.sleep(2)
        except ApiException as e:
            if e.status != 404:  # 404 means job doesn't exist, which is fine
                logger.warning(f"Error checking for existing job {job_name}: {e}")

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
            if e.status == 409:  # Conflict - job already exists
                logger.warning(f"Job {job_name} already exists, attempting to delete and recreate")
                try:
                    self.batch_api.delete_namespaced_job(
                        name=job_name,
                        namespace=namespace,
                        body=client.V1DeleteOptions(propagation_policy="Foreground")
                    )
                    time.sleep(2)
                    # Retry creation
                    created_job = self.batch_api.create_namespaced_job(
                        namespace=namespace, body=job
                    )
                    logger.info(f"Submitted training job {job_name} with UID {created_job.metadata.uid} after cleanup")
                    return created_job.metadata.uid
                except Exception as retry_error:
                    logger.error(f"Failed to recreate job {job_name} after cleanup: {retry_error}")
                    raise
            logger.error(f"Failed to submit job {job_name}: {e}")
            raise

    def submit_distributed_job(
        self,
        job_name: str,
        image: str,
        gpu_count: int,
        num_nodes: int,
        gpu_type: str,
        command: list[str],
        env_vars: dict[str, str],
        namespace: str | None = None,
    ) -> str:
        """
        Submit a distributed training job to Kubernetes with multiple nodes/GPUs.

        Args:
            job_name: Unique name for the job
            image: Container image to use
            gpu_count: Number of GPUs per node
            num_nodes: Number of nodes (pods) in the distributed job
            gpu_type: GPU type (e.g., "nvidia-tesla-v100")
            command: Command to run in containers
            env_vars: Environment variables to set
            namespace: Kubernetes namespace

        Returns:
            Job UID from Kubernetes
        """
        if namespace is None:
            namespace = settings.training_namespace
        
        job_id = str(uuid4())
        container_name = f"{job_name}-trainer"

        # Build environment variables with distributed training configuration
        env = [
            client.V1EnvVar(name=k, value=str(v)) for k, v in env_vars.items()
        ]
        # Add distributed training environment variables
        env.extend([
            client.V1EnvVar(name="WORLD_SIZE", value=str(num_nodes * gpu_count)),
            client.V1EnvVar(name="RANK", value="0"),  # Will be set per pod via init container or env
            client.V1EnvVar(name="MASTER_ADDR", value=f"{job_name}-master"),
            client.V1EnvVar(name="MASTER_PORT", value="29500"),
            client.V1EnvVar(name="NPROC_PER_NODE", value=str(gpu_count)),
        ])

        # GPU resource requests per pod (from settings)
        resources = client.V1ResourceRequirements(
            requests={
                "nvidia.com/gpu": str(gpu_count),
                "memory": settings.training_gpu_distributed_memory_request,
                "cpu": settings.training_gpu_cpu_request,
            },
            limits={
                "nvidia.com/gpu": str(gpu_count),
                "memory": settings.training_gpu_distributed_memory_limit,
                "cpu": settings.training_gpu_cpu_limit,
            },
        )

        container = client.V1Container(
            name=container_name,
            image=image,
            command=command,
            env=env,
            resources=resources,
        )

        # Build node selector and tolerations for GPU nodes
        node_selector = settings.training_gpu_node_selector.copy() if settings.training_gpu_node_selector else {}
        tolerations = []
        if settings.training_gpu_tolerations:
            for tol in settings.training_gpu_tolerations:
                tolerations.append(client.V1Toleration(**tol))

        pod_template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(
                labels={
                    "app": job_name,
                    "job-id": job_id,
                    "job-type": "distributed",
                }
            ),
            spec=client.V1PodSpec(
                restart_policy="Never",
                containers=[container],
                node_selector=node_selector if node_selector else None,
                tolerations=tolerations if tolerations else None,
            ),
        )

        # For distributed training, create multiple pods (one per node)
        job_spec = client.V1JobSpec(
            template=pod_template,
            backoff_limit=3,
            completions=num_nodes,  # All nodes must complete
            parallelism=num_nodes,  # Run all nodes in parallel
            ttl_seconds_after_finished=300,  # Delete pods 5 minutes after completion
        )

        # Check if job already exists
        try:
            existing_job = self.batch_api.read_namespaced_job(
                name=job_name,
                namespace=namespace
            )
            if existing_job:
                logger.warning(f"Distributed job {job_name} already exists, deleting it first")
                self.batch_api.delete_namespaced_job(
                    name=job_name,
                    namespace=namespace,
                    body=client.V1DeleteOptions(propagation_policy="Foreground")
                )
                time.sleep(2)
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Error checking for existing distributed job {job_name}: {e}")

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=namespace,
                labels={
                    "job-id": job_id,
                    "managed-by": "llm-ops-platform",
                    "job-type": "distributed",
                    "num-nodes": str(num_nodes),
                    "gpu-per-node": str(gpu_count),
                },
            ),
            spec=job_spec,
        )

        try:
            created_job = self.batch_api.create_namespaced_job(
                namespace=namespace, body=job
            )
            logger.info(
                f"Submitted distributed training job {job_name} with {num_nodes} nodes, "
                f"{gpu_count} GPUs per node, UID {created_job.metadata.uid}"
            )
            return created_job.metadata.uid
        except ApiException as e:
            if e.status == 409:  # Conflict
                logger.warning(f"Distributed job {job_name} already exists, attempting to delete and recreate")
                try:
                    self.batch_api.delete_namespaced_job(
                        name=job_name,
                        namespace=namespace,
                        body=client.V1DeleteOptions(propagation_policy="Foreground")
                    )
                    import time
                    time.sleep(2)
                    created_job = self.batch_api.create_namespaced_job(
                        namespace=namespace, body=job
                    )
                    logger.info(
                        f"Submitted distributed training job {job_name} with {num_nodes} nodes after cleanup, "
                        f"UID {created_job.metadata.uid}"
                    )
                    return created_job.metadata.uid
                except Exception as retry_error:
                    logger.error(f"Failed to recreate distributed job {job_name} after cleanup: {retry_error}")
                    raise
            logger.error(f"Failed to submit distributed job {job_name}: {e}")
            raise

    def get_job_status(
        self, job_name: str, namespace: str | None = None
    ) -> Optional[dict]:
        """Retrieve job status from Kubernetes."""
        if namespace is None:
            namespace = settings.training_namespace
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

    def delete_job(self, job_name: str, namespace: str | None = None) -> bool:
        """Delete a training job from Kubernetes."""
        if namespace is None:
            namespace = settings.training_namespace
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

    def submit_cpu_only_job(
        self,
        job_name: str,
        image: str,
        cpu_cores: int,
        memory: str,
        command: list[str],
        env_vars: dict[str, str],
        namespace: str | None = None,
    ) -> str:
        """
        Submit a CPU-only training job to Kubernetes (no GPU requirements).

        Args:
            job_name: Unique name for the job
            image: Container image to use
            cpu_cores: Number of CPU cores to allocate
            memory: Memory allocation (e.g., "8Gi", "16Gi")
            command: Command to run in containers
            env_vars: Environment variables to set
            namespace: Kubernetes namespace

        Returns:
            Job UID from Kubernetes
        """
        if namespace is None:
            namespace = settings.training_namespace
        
        job_id = str(uuid4())
        container_name = f"{job_name}-trainer"

        # Build environment variables
        env = [
            client.V1EnvVar(name=k, value=str(v)) for k, v in env_vars.items()
        ]

        # CPU-only resource requests (no GPU)
        resources = client.V1ResourceRequirements(
            requests={
                "memory": memory,
                "cpu": str(cpu_cores),
            },
            limits={
                "memory": memory,
                "cpu": str(cpu_cores * 2),  # Allow burst up to 2x requested CPU
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
            metadata=client.V1ObjectMeta(
                labels={
                    "app": job_name,
                    "job-id": job_id,
                    "job-type": "cpu-only",
                }
            ),
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
            ttl_seconds_after_finished=300,  # Delete pods 5 minutes after completion
        )

        # Check if job already exists
        try:
            existing_job = self.batch_api.read_namespaced_job(
                name=job_name,
                namespace=namespace
            )
            if existing_job:
                logger.warning(f"CPU-only job {job_name} already exists, deleting it first")
                self.batch_api.delete_namespaced_job(
                    name=job_name,
                    namespace=namespace,
                    body=client.V1DeleteOptions(propagation_policy="Foreground")
                )
                time.sleep(2)
        except ApiException as e:
            if e.status != 404:
                logger.warning(f"Error checking for existing CPU-only job {job_name}: {e}")

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=namespace,
                labels={
                    "job-id": job_id,
                    "managed-by": "llm-ops-platform",
                    "job-type": "cpu-only",
                },
            ),
            spec=job_spec,
        )

        try:
            created_job = self.batch_api.create_namespaced_job(
                namespace=namespace, body=job
            )
            logger.info(
                f"Submitted CPU-only training job {job_name} with {cpu_cores} CPU cores, "
                f"{memory} memory, UID {created_job.metadata.uid}"
            )
            return created_job.metadata.uid
        except ApiException as e:
            if e.status == 409:  # Conflict
                logger.warning(f"CPU-only job {job_name} already exists, attempting to delete and recreate")
                try:
                    self.batch_api.delete_namespaced_job(
                        name=job_name,
                        namespace=namespace,
                        body=client.V1DeleteOptions(propagation_policy="Foreground")
                    )
                    import time
                    time.sleep(2)
                    created_job = self.batch_api.create_namespaced_job(
                        namespace=namespace, body=job
                    )
                    logger.info(
                        f"Submitted CPU-only training job {job_name} with {cpu_cores} CPU cores after cleanup, "
                        f"UID {created_job.metadata.uid}"
                    )
                    return created_job.metadata.uid
                except Exception as retry_error:
                    logger.error(f"Failed to recreate CPU-only job {job_name} after cleanup: {retry_error}")
                    raise
            logger.error(f"Failed to submit CPU-only job {job_name}: {e}")
            raise

    def get_pod_status(self, job_name: str, namespace: str | None = None) -> Optional[dict]:
        """Get pod status and events for debugging pending pods."""
        if namespace is None:
            namespace = settings.training_namespace
        try:
            # List pods for this job
            label_selector = f"app={job_name}"
            pods = self.core_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )
            
            if not pods.items:
                return None
            
            pod_info = []
            for pod in pods.items:
                pod_status = {
                    "name": pod.metadata.name,
                    "phase": pod.status.phase,
                    "conditions": [],
                    "events": [],
                }
                
                # Get pod conditions
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        pod_status["conditions"].append({
                            "type": condition.type,
                            "status": condition.status,
                            "reason": condition.reason,
                            "message": condition.message,
                        })
                
                # Get pod events
                try:
                    events = self.core_api.list_namespaced_event(
                        namespace=namespace,
                        field_selector=f"involvedObject.name={pod.metadata.name}"
                    )
                    for event in events.items[:5]:  # Last 5 events
                        pod_status["events"].append({
                            "reason": event.reason,
                            "message": event.message,
                            "timestamp": event.first_timestamp.isoformat() if event.first_timestamp else None,
                        })
                except Exception as e:
                    logger.warning(f"Failed to get events for pod {pod.metadata.name}: {e}")
                
                pod_info.append(pod_status)
            
            return {"pods": pod_info}
        except ApiException as e:
            logger.error(f"Failed to get pod status for {job_name}: {e}")
            return None

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

