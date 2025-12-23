"""
Kubernetes client utility for managing Kubernetes API connections.

Provides a unified interface for:
- Kubernetes client initialization (kubeconfig/in-cluster)
- Token refresh handling (in-cluster SA token rotation)
- 401 error retry logic
- API client access
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

from kubernetes import client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from core.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class KubernetesClient:
    """Unified Kubernetes client for managing API connections and authentication."""

    def __init__(self, logger_prefix: str = ""):
        """
        Initialize Kubernetes client.

        Args:
            logger_prefix: Prefix for log messages (e.g., "KServeAdapter", "ServingDeployer")
        """
        self.logger_prefix = logger_prefix
        self.settings = get_settings()

        # Keep references to cfg and api_client so refresh can actually update them
        self.cfg: Optional[client.Configuration] = None
        self.api_client: Optional[client.ApiClient] = None

        # API handles (initialized in _rebuild_clients)
        self.apps_api: Optional[client.AppsV1Api] = None
        self.batch_api: Optional[client.BatchV1Api] = None
        self.core_api: Optional[client.CoreV1Api] = None
        self.autoscaling_api: Optional[client.AutoscalingV1Api] = None
        self.networking_api: Optional[client.NetworkingV1Api] = None
        self.custom_api: Optional[client.CustomObjectsApi] = None

        self._initialize_client()
        self._test_connection()

    # -------------------------
    # Internal helpers
    # -------------------------

    def _log(self, level: int, msg: str) -> None:
        prefix = f"{self.logger_prefix}: " if self.logger_prefix else ""
        logger.log(level, f"{prefix}{msg}")

    def _initialize_client(self) -> None:
        """Initialize Configuration + ApiClient and API wrappers."""
        self.cfg = client.Configuration()

        try:
            if getattr(self.settings, "kubeconfig_path", None):
                self._log(logging.INFO, f"Loading kubeconfig: {self.settings.kubeconfig_path}")
                k8s_config.load_kube_config(
                    config_file=self.settings.kubeconfig_path,
                    client_configuration=self.cfg,
                )
            else:
                self._log(logging.INFO, "Loading in-cluster config")
                k8s_config.load_incluster_config(client_configuration=self.cfg)
        except Exception as e:
            self._log(logging.ERROR, f"Failed to load kubernetes config: {e}")
            raise

        # Apply SSL options ONLY if explicitly configured
        # (do not override what kubeconfig / incluster loader sets by default)
        kubernetes_verify_ssl = getattr(self.settings, "kubernetes_verify_ssl", None)
        if kubernetes_verify_ssl is not None:
            self.cfg.verify_ssl = bool(kubernetes_verify_ssl)
            if not self.cfg.verify_ssl:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Guard against "localhost" or empty host (means config did not apply)
        self._log(logging.INFO, f"Kubernetes API host = {self.cfg.host!r}")
        if not self.cfg.host or "localhost" in self.cfg.host:
            raise RuntimeError(
                f"Kubernetes configuration host is invalid: {self.cfg.host!r} "
                f"(kubeconfig/in-cluster config not applied)"
            )

        # Token refresh hook for in-cluster SA token rotation
        self._attach_token_refresh_hook()

        # Build ApiClient and typed APIs
        self._rebuild_clients()

    def _rebuild_clients(self) -> None:
        """Rebuild ApiClient and API wrappers based on current self.cfg."""
        if self.cfg is None:
            raise RuntimeError("Configuration is not initialized")

        # Close old pool if any (best-effort)
        if self.api_client is not None:
            try:
                self.api_client.close()
            except Exception:
                pass

        self.api_client = client.ApiClient(configuration=self.cfg)

        # Inject ApiClient into each API (do NOT use global default)
        self.apps_api = client.AppsV1Api(self.api_client)
        self.batch_api = client.BatchV1Api(self.api_client)
        self.core_api = client.CoreV1Api(self.api_client)
        self.autoscaling_api = client.AutoscalingV1Api(self.api_client)
        self.networking_api = client.NetworkingV1Api(self.api_client)
        self.custom_api = client.CustomObjectsApi(self.api_client)

    def _attach_token_refresh_hook(self) -> None:
        """
        Attach a refresh hook so the SA token is re-read on demand.
        This helps when service account token is rotated.
        """
        if self.cfg is None:
            return

        # If kubeconfig is used, authentication is usually handled via kubeconfig;
        # no need to attach SA token hook.
        if getattr(self.settings, "kubeconfig_path", None):
            return

        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"

        def refresh_api_key_hook(cfg: client.Configuration) -> None:
            try:
                if os.path.exists(token_path):
                    with open(token_path, "r") as f:
                        token = f.read().strip()
                    if token:
                        # Kubernetes python client expects "authorization" key
                        cfg.api_key["authorization"] = token
            except Exception as e:
                self._log(logging.WARNING, f"token refresh hook failed: {e}")

        # Called by ApiClient when it needs api_key and finds it empty/expired
        self.cfg.refresh_api_key_hook = refresh_api_key_hook

    # -------------------------
    # Diagnostics / Validation
    # -------------------------

    def _validate_service_account(self) -> Dict[str, Any]:
        """
        Validate service account configuration and permissions.

        Returns:
            Dictionary with validation results including:
            - token_exists: bool
            - token_readable: bool
            - namespace: str (current namespace)
            - ca_cert_exists: bool
            - can_list_namespaces: bool
            - can_access_kserve: bool
        """
        results: Dict[str, Any] = {
            "token_exists": False,
            "token_readable": False,
            "namespace": None,
            "ca_cert_exists": False,
            "can_list_namespaces": False,
            "can_access_kserve": False,
        }

        # If kubeconfig_path is set, we're using external kubeconfig (not in-cluster)
        # Skip service account file validation in this case
        if getattr(self.settings, "kubeconfig_path", None):
            self._log(logging.DEBUG, "Using external kubeconfig, skipping in-cluster service account file validation")
        else:
            token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            ca_cert_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
            namespace_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"

            results["token_exists"] = os.path.exists(token_path)
            results["ca_cert_exists"] = os.path.exists(ca_cert_path)

            if results["token_exists"]:
                try:
                    with open(token_path, "r") as f:
                        token_content = f.read().strip()
                    if token_content:
                        results["token_readable"] = True
                        self._log(logging.DEBUG, f"Service account token length: {len(token_content)}")
                except Exception as e:
                    self._log(logging.WARNING, f"Could not read service account token: {e}")

            if os.path.exists(namespace_path):
                try:
                    with open(namespace_path, "r") as f:
                        results["namespace"] = f.read().strip()
                except Exception as e:
                    self._log(logging.WARNING, f"Could not read namespace: {e}")

        # Test API permissions (always perform, regardless of kubeconfig_path)
        try:
            assert self.core_api is not None
            self.core_api.list_namespace(limit=1, _request_timeout=5)
            results["can_list_namespaces"] = True
        except Exception as e:
            self._log(logging.DEBUG, f"Permission test (list_namespaces) failed: {e}")

        # Test KServe access (always perform, regardless of kubeconfig_path)
        try:
            assert self.custom_api is not None
            self.custom_api.list_cluster_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                plural="inferenceservices",
                limit=1,
                timeout_seconds=5,
            )
            results["can_access_kserve"] = True
        except Exception as e:
            self._log(logging.DEBUG, f"Permission test (KServe) failed: {e}")

        return results

    def _test_connection(self) -> None:
        """Test Kubernetes API connection and validate service account."""
        try:
            self._log(logging.INFO, "Testing Kubernetes API connection...")

            validation_results = self._validate_service_account()

            # Log service account status (only for in-cluster config)
            if not getattr(self.settings, "kubeconfig_path", None):
                if validation_results["token_exists"]:
                    self._log(logging.INFO, "Service account token found")
                    if validation_results["token_readable"]:
                        self._log(logging.INFO, "Service account token is readable")
                    else:
                        self._log(logging.WARNING, "Service account token exists but is not readable")
                else:
                    self._log(logging.ERROR, "Service account token NOT found - this will cause 401 errors in-cluster")
                    self._log(
                        logging.ERROR,
                        "Ensure Pod spec has 'automountServiceAccountToken: true' and serviceAccountName is set",
                    )

                if validation_results["ca_cert_exists"]:
                    self._log(logging.INFO, "Service account CA certificate found")
                else:
                    self._log(logging.WARNING, "Service account CA certificate NOT found")

                if validation_results["namespace"]:
                    self._log(logging.INFO, f"Current namespace: {validation_results['namespace']}")

            # Test connection by listing namespaces
            assert self.core_api is not None
            _ = self.core_api.list_namespace(limit=1, _request_timeout=10)

            self._log(logging.INFO, "Kubernetes API connection successful. Cluster accessible (tested via namespace list)")

            if validation_results["can_list_namespaces"]:
                self._log(logging.INFO, "RBAC permission verified: can list namespaces")
            else:
                self._log(logging.WARNING, "RBAC permission check failed: cannot list namespaces")

            if validation_results["can_access_kserve"]:
                self._log(logging.INFO, "RBAC permission verified: can access KServe InferenceServices")
            else:
                self._log(logging.WARNING, "RBAC permission check failed: cannot access KServe InferenceServices")

        except ApiException as e:
            if e.status == 401:
                self._handle_401_during_test(e)
            else:
                self._log(logging.WARNING, f"Failed to connect to Kubernetes API (status {e.status}): {e.reason}")

        except Exception as e:
            self._log(logging.WARNING, f"Failed to test Kubernetes API connection: {e}")

    def _handle_401_during_test(self, e: ApiException) -> None:
        """Detailed diagnostics for 401 during initialization test."""
        validation_results = self._validate_service_account()

        self._log(logging.ERROR, "Kubernetes API authentication failed (401 Unauthorized)")
        logger.error("=" * 80)
        logger.error(f"{self.logger_prefix}: DIAGNOSTIC INFORMATION FOR 401 ERROR" if self.logger_prefix else "DIAGNOSTIC INFORMATION FOR 401 ERROR")
        logger.error("=" * 80)

        if not getattr(self.settings, "kubeconfig_path", None):
            if validation_results["token_exists"]:
                logger.error("✓ Service account token file exists")
                if validation_results["token_readable"]:
                    logger.error("✓ Service account token is readable")
                else:
                    logger.error("✗ Service account token exists but is NOT readable - check file permissions")
            else:
                logger.error("✗ Service account token file NOT found at /var/run/secrets/kubernetes.io/serviceaccount/token")
                logger.error("  → This is the ROOT CAUSE of 401 errors in-cluster")
                logger.error("  → Solution: Ensure Pod spec has:")
                logger.error("     1. serviceAccountName: <service-account-name>")
                logger.error("     2. automountServiceAccountToken: true")

            if validation_results["ca_cert_exists"]:
                logger.error("✓ Service account CA certificate exists")
            else:
                logger.error("✗ Service account CA certificate NOT found")

            if validation_results["namespace"]:
                logger.error(f"✓ Current namespace: {validation_results['namespace']}")
            else:
                logger.error("✗ Could not determine current namespace")
        else:
            logger.error(f"Using external kubeconfig: {self.settings.kubeconfig_path}")
            logger.error("  → Check kubeconfig file permissions and authentication credentials")

        if validation_results["can_list_namespaces"]:
            logger.error("✓ RBAC: Can list namespaces")
        else:
            logger.error("✗ RBAC: Cannot list namespaces - check ClusterRoleBinding")

        if validation_results["can_access_kserve"]:
            logger.error("✓ RBAC: Can access KServe InferenceServices")
        else:
            logger.error("✗ RBAC: Cannot access KServe InferenceServices - check ClusterRole permissions")

        logger.error("=" * 80)

        # Attempt refresh and retry once
        self._log(logging.WARNING, "Attempting config/token refresh...")
        if self.refresh_token():
            self._log(logging.INFO, "Refresh succeeded, retrying connection test...")
            try:
                assert self.core_api is not None
                _ = self.core_api.list_namespace(limit=1, _request_timeout=10)
                self._log(logging.INFO, "Kubernetes API connection successful after refresh.")
                return
            except ApiException as retry_e:
                self._log(logging.ERROR, f"Connection test still failed after refresh: {retry_e}")
            except Exception as retry_e:
                self._log(logging.ERROR, f"Connection test still failed after refresh: {retry_e}")
        else:
            self._log(logging.ERROR, "Refresh failed during initialization")

        self._log(logging.ERROR, f"Final: 401 Unauthorized. Error: {e.reason}")

    # -------------------------
    # Public token refresh
    # -------------------------

    def refresh_token(self) -> bool:
        """
        Refresh Kubernetes authentication/config.
        IMPORTANT: refresh must update the SAME configuration/api_client used by this instance.
        """
        if self.cfg is None:
            self._log(logging.ERROR, "Cannot refresh: cfg is not initialized")
            return False

        try:
            self._log(logging.INFO, "Refreshing Kubernetes authentication/config...")

            if getattr(self.settings, "kubeconfig_path", None):
                k8s_config.load_kube_config(
                    config_file=self.settings.kubeconfig_path,
                    client_configuration=self.cfg,
                )
            else:
                k8s_config.load_incluster_config(client_configuration=self.cfg)

            # Re-attach hook because load_* may overwrite cfg fields
            self._attach_token_refresh_hook()

            # Rebuild api_client + APIs to ensure new cfg is used
            self._rebuild_clients()

            self._log(logging.INFO, "Refresh success")
            return True

        except Exception as e:
            self._log(logging.ERROR, f"Failed to refresh Kubernetes config/token: {e}")
            return False

    # -------------------------
    # 401 handling utilities
    # -------------------------

    @contextmanager
    def handle_401_retry(self, operation_name: str = "API call"):
        """
        Context manager for handling 401 errors with automatic retry.

        NOTE: This context manager does NOT auto-retry by itself.
        It refreshes token/config, then re-raises so caller can retry.
        """
        try:
            yield
        except ApiException as e:
            if e.status == 401:
                self._log(logging.WARNING, f"401 during {operation_name}. Attempting refresh...")
                if self.refresh_token():
                    self._log(logging.INFO, f"Refresh OK. Please retry {operation_name}.")
                else:
                    self._log(logging.ERROR, f"Refresh failed. Cannot retry {operation_name}.")
                raise
            raise

    def call_with_401_retry(
        self,
        api_call: Callable[[], T],
        operation_name: str = "API call",
        max_retries: int = 1,
    ) -> T:
        """
        Execute an API call with automatic 401 retry.

        Args:
            api_call: Callable that performs the API call
            operation_name: Name of the operation for logging purposes
            max_retries: Maximum number of retries (default: 1)
        """
        retries = 0
        while True:
            try:
                return api_call()
            except ApiException as e:
                if e.status == 401 and retries < max_retries:
                    self._log(logging.WARNING, f"401 during {operation_name}. Attempting refresh...")
                    if self.refresh_token():
                        retries += 1
                        self._log(logging.INFO, f"Retrying {operation_name} (attempt {retries}/{max_retries})...")
                        continue
                    self._log(logging.ERROR, f"Refresh failed. Cannot retry {operation_name}.")
                raise