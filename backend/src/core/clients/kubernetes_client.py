"""Kubernetes client utility for managing Kubernetes API connections.

Provides a unified interface for:
- Kubernetes client initialization (kubeconfig/in-cluster)
- Token refresh handling
- 401 error retry logic
- API client access
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from functools import wraps
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
        self._initialize_client()
        self._test_connection()

    def _initialize_client(self) -> None:
        cfg = client.Configuration()

        try:
            if self.settings.kubeconfig_path:
                logger.info(f"{self.logger_prefix}: Loading kubeconfig: {self.settings.kubeconfig_path}")
                k8s_config.load_kube_config(
                    config_file=self.settings.kubeconfig_path,
                    client_configuration=cfg,
                )
            else:
                logger.info(f"{self.logger_prefix}: Loading in-cluster config")
                k8s_config.load_incluster_config(client_configuration=cfg)
        except Exception as e:
            logger.error(f"{self.logger_prefix}: Failed to load kubernetes config: {e}")
            raise

        # SSL 옵션 적용 (cfg에 직접)
        if self.settings.kubeconfig_path and not self.settings.kubernetes_verify_ssl:
            cfg.verify_ssl = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        else:
            cfg.verify_ssl = True

        # “localhost” 방지 가드 + 로그
        logger.info(f"{self.logger_prefix}: Kubernetes API host = {cfg.host!r}")
        if not cfg.host or "localhost" in cfg.host:
            raise RuntimeError(
                f"Kubernetes configuration host is invalid: {cfg.host!r} "
                f"(kubeconfig/in-cluster config not applied)"
            )

        # ApiClient를 cfg로 고정
        self.api_client = client.ApiClient(configuration=cfg)

        # 각 API에 주입 (전역 default 사용 X)
        self.apps_api = client.AppsV1Api(self.api_client)
        self.batch_api = client.BatchV1Api(self.api_client)
        self.core_api = client.CoreV1Api(self.api_client)
        self.autoscaling_api = client.AutoscalingV1Api(self.api_client)
        self.networking_api = client.NetworkingV1Api(self.api_client)
        self.custom_api = client.CustomObjectsApi(self.api_client)

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
        results = {
            "token_exists": False,
            "token_readable": False,
            "namespace": None,
            "ca_cert_exists": False,
            "can_list_namespaces": False,
            "can_access_kserve": False,
        }
        
        # If kubeconfig_path is set, we're using external kubeconfig (not in-cluster)
        # Skip service account file validation in this case
        if self.settings.kubeconfig_path:
            logger.debug(f"{self.logger_prefix}: Using external kubeconfig, skipping in-cluster service account validation")
        else:
            # Only validate service account files when using in-cluster config
            token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            ca_cert_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
            namespace_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
            
            # Check token file existence
            results["token_exists"] = os.path.exists(token_path)
            results["ca_cert_exists"] = os.path.exists(ca_cert_path)
            
            if results["token_exists"]:
                # Try to read token
                try:
                    with open(token_path, 'r') as f:
                        token_content = f.read().strip()
                    if token_content:
                        results["token_readable"] = True
                        logger.debug(f"Service account token length: {len(token_content)}")
                except Exception as e:
                    log_msg = f"{self.logger_prefix}: Could not read service account token: {e}"
                    logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            
            # Read current namespace
            if os.path.exists(namespace_path):
                try:
                    with open(namespace_path, 'r') as f:
                        results["namespace"] = f.read().strip()
                except Exception as e:
                    log_msg = f"{self.logger_prefix}: Could not read namespace: {e}"
                    logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
        
        # Test API permissions (always perform, regardless of kubeconfig_path)
        try:
            self.core_api.list_namespace(limit=1, _request_timeout=5)
            results["can_list_namespaces"] = True
        except Exception as e:
            logger.debug(f"Permission test (list_namespaces) failed: {e}")
        
        # Test KServe access (always perform, regardless of kubeconfig_path)
        try:
            self.custom_api.list_cluster_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                plural="inferenceservices",
                limit=1,
                timeout_seconds=5
            )
            results["can_access_kserve"] = True
        except Exception as e:
            logger.debug(f"Permission test (KServe) failed: {e}")
        
        return results

    def _test_connection(self) -> None:
        """Test Kubernetes API connection and validate service account."""
        try:
            log_msg = f"{self.logger_prefix}: Testing Kubernetes API connection..."
            logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            
            # Validate service account configuration
            validation_results = self._validate_service_account()
            
            # Log service account status (only for in-cluster config)
            if not self.settings.kubeconfig_path:
                if validation_results["token_exists"]:
                    log_msg = f"{self.logger_prefix}: Service account token found"
                    logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    if validation_results["token_readable"]:
                        log_msg = f"{self.logger_prefix}: Service account token is readable"
                        logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    else:
                        log_msg = f"{self.logger_prefix}: Service account token exists but is not readable"
                        logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                else:
                    log_msg = f"{self.logger_prefix}: Service account token NOT found - this will cause 401 errors in-cluster"
                    logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    log_msg = f"{self.logger_prefix}: Ensure Pod spec has 'automountServiceAccountToken: true' and serviceAccountName is set"
                    logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                
                if validation_results["ca_cert_exists"]:
                    log_msg = f"{self.logger_prefix}: Service account CA certificate found"
                    logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                else:
                    log_msg = f"{self.logger_prefix}: Service account CA certificate NOT found"
                    logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                
                if validation_results["namespace"]:
                    log_msg = f"{self.logger_prefix}: Current namespace: {validation_results['namespace']}"
                    logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            
            # Test connection by listing namespaces (simple API call)
            # Set timeout to prevent hanging (10 seconds)
            namespaces = self.core_api.list_namespace(limit=1, _request_timeout=10)
            log_msg = f"{self.logger_prefix}: Kubernetes API connection successful. Cluster accessible (tested via namespace list)"
            logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            
            # Log permission test results
            if validation_results["can_list_namespaces"]:
                log_msg = f"{self.logger_prefix}: RBAC permission verified: can list namespaces"
                logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            else:
                log_msg = f"{self.logger_prefix}: RBAC permission check failed: cannot list namespaces"
                logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            
            if validation_results["can_access_kserve"]:
                log_msg = f"{self.logger_prefix}: RBAC permission verified: can access KServe InferenceServices"
                logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            else:
                log_msg = f"{self.logger_prefix}: RBAC permission check failed: cannot access KServe InferenceServices"
                logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
        except ApiException as e:
            if e.status == 401:
                # Enhanced 401 error diagnostics
                validation_results = self._validate_service_account()
                
                log_msg = f"{self.logger_prefix}: Kubernetes API authentication failed (401 Unauthorized)"
                logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                
                # Detailed diagnostics
                logger.error("=" * 80)
                logger.error(f"{self.logger_prefix}: DIAGNOSTIC INFORMATION FOR 401 ERROR")
                logger.error("=" * 80)
                
                # ServiceAccount token status (only for in-cluster config)
                if not self.settings.kubeconfig_path:
                    if validation_results["token_exists"]:
                        logger.error(f"✓ Service account token file exists")
                        if validation_results["token_readable"]:
                            logger.error(f"✓ Service account token is readable")
                        else:
                            logger.error(f"✗ Service account token exists but is NOT readable - check file permissions")
                    else:
                        logger.error(f"✗ Service account token file NOT found at /var/run/secrets/kubernetes.io/serviceaccount/token")
                        logger.error(f"  → This is the ROOT CAUSE of 401 errors in-cluster")
                        logger.error(f"  → Solution: Ensure Pod spec has:")
                        logger.error(f"     1. serviceAccountName: <service-account-name>")
                        logger.error(f"     2. automountServiceAccountToken: true")
                    
                    # CA certificate status
                    if validation_results["ca_cert_exists"]:
                        logger.error(f"✓ Service account CA certificate exists")
                    else:
                        logger.error(f"✗ Service account CA certificate NOT found")
                    
                    # Namespace information
                    if validation_results["namespace"]:
                        logger.error(f"✓ Current namespace: {validation_results['namespace']}")
                    else:
                        logger.error(f"✗ Could not determine current namespace")
                else:
                    logger.error(f"Using external kubeconfig: {self.settings.kubeconfig_path}")
                    logger.error(f"  → Check kubeconfig file permissions and authentication credentials")
                
                # RBAC permission status
                if validation_results["can_list_namespaces"]:
                    logger.error(f"✓ RBAC: Can list namespaces")
                else:
                    logger.error(f"✗ RBAC: Cannot list namespaces - check ClusterRoleBinding")
                
                if validation_results["can_access_kserve"]:
                    logger.error(f"✓ RBAC: Can access KServe InferenceServices")
                else:
                    logger.error(f"✗ RBAC: Cannot access KServe InferenceServices - check ClusterRole permissions")
                
                logger.error("=" * 80)
                
                # Try to refresh the token during initialization
                log_msg = f"{self.logger_prefix}: Attempting token refresh..."
                logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                
                if self.refresh_token():
                    log_msg = f"{self.logger_prefix}: Token refreshed during initialization, retrying connection test..."
                    logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    try:
                        namespaces = self.core_api.list_namespace(limit=1, _request_timeout=10)
                        log_msg = f"{self.logger_prefix}: Kubernetes API connection successful after token refresh. Cluster accessible (tested via namespace list)"
                        logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    except ApiException as retry_e:
                        log_msg = f"{self.logger_prefix}: Connection test still failed after token refresh: {retry_e}"
                        logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                else:
                    log_msg = f"{self.logger_prefix}: Token refresh failed during initialization"
                    logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                
                # Final error message
                log_msg = f"{self.logger_prefix}: Kubernetes API authentication failed (401 Unauthorized). "
                log_msg += "This may be due to expired credentials or insufficient permissions. "
                if self.logger_prefix:
                    log_msg += f"{self.logger_prefix} operations may fail until authentication is resolved. "
                else:
                    log_msg += "Operations may fail until authentication is resolved. "
                log_msg += f"Error: {e.reason}"
                logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            else:
                log_msg = f"{self.logger_prefix}: Failed to connect to Kubernetes API (status {e.status}): {e.reason}. "
                if self.logger_prefix:
                    log_msg += f"{self.logger_prefix} operations may fail until connection is resolved."
                else:
                    log_msg += "Operations may fail until connection is resolved."
                logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
        except Exception as e:
            log_msg = f"{self.logger_prefix}: Failed to test Kubernetes API connection: {e}. "
            if self.logger_prefix:
                log_msg += f"{self.logger_prefix} operations may fail until connection is resolved."
            else:
                log_msg += "Operations may fail until connection is resolved."
            logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))

    def refresh_token(self) -> bool:
        """
        Refresh Kubernetes authentication token for in-cluster operations.
        
        Returns:
            True if refresh was successful, False otherwise.
        """
        try:
            log_msg = f"{self.logger_prefix}: Attempting to refresh Kubernetes authentication token..."
            logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            # Reload in-cluster config - let it handle authentication automatically
            token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
            ca_cert_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

            if os.path.exists(token_path) and os.path.exists(ca_cert_path):
                log_msg = f"{self.logger_prefix}: Service account files available during refresh - token: {token_path}, ca_cert: {ca_cert_path}"
                logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                k8s_config.load_incluster_config()
                log_msg = f"{self.logger_prefix}: Successfully refreshed Kubernetes authentication token (automatic)"
                logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                return True
            else:
                log_msg = f"{self.logger_prefix}: Service account files not found during refresh - token: {os.path.exists(token_path)}, ca_cert: {os.path.exists(ca_cert_path)}"
                logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                # Still try to refresh as fallback
                k8s_config.load_incluster_config()
                log_msg = f"{self.logger_prefix}: Attempted token refresh (fallback)"
                logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                return True
        except Exception as e:
            log_msg = f"{self.logger_prefix}: Failed to refresh Kubernetes token: {e}"
            logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
            return False

    @contextmanager
    def handle_401_retry(self, operation_name: str = "API call"):
        """
        Context manager for handling 401 errors with automatic retry.
        
        Usage:
            with self.k8s_client.handle_401_retry("create InferenceService"):
                result = self.custom_api.create_namespaced_custom_object(...)
        
        Args:
            operation_name: Name of the operation for logging purposes
        """
        try:
            yield
        except ApiException as e:
            if e.status == 401:
                log_msg = f"{self.logger_prefix}: Kubernetes API authentication failed (401 Unauthorized) during {operation_name}. "
                log_msg += "Attempting token refresh..."
                logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                
                if self.refresh_token():
                    log_msg = f"{self.logger_prefix}: Token refreshed, retrying {operation_name}..."
                    logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    # Re-raise to allow caller to retry
                    raise
                else:
                    log_msg = f"{self.logger_prefix}: Token refresh failed, cannot retry {operation_name}"
                    logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    raise
            else:
                raise

    def call_with_401_retry(
        self,
        api_call: Callable[[], T],
        operation_name: str = "API call",
        max_retries: int = 1,
    ) -> T:
        """
        Execute an API call with automatic 401 retry.
        
        Usage:
            result = self.k8s_client.call_with_401_retry(
                lambda: self.custom_api.create_namespaced_custom_object(...),
                "create InferenceService"
            )
        
        Args:
            api_call: Callable that performs the API call
            operation_name: Name of the operation for logging purposes
            max_retries: Maximum number of retries (default: 1)
        
        Returns:
            Result of the API call
        
        Raises:
            ApiException: If the API call fails after retries
        """
        retries = 0
        while retries <= max_retries:
            try:
                return api_call()
            except ApiException as e:
                if e.status == 401 and retries < max_retries:
                    log_msg = f"{self.logger_prefix}: Kubernetes API authentication failed (401 Unauthorized) during {operation_name}. "
                    log_msg += "Attempting token refresh..."
                    logger.warning(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                    
                    if self.refresh_token():
                        log_msg = f"{self.logger_prefix}: Token refreshed, retrying {operation_name}..."
                        logger.info(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                        retries += 1
                        continue
                    else:
                        log_msg = f"{self.logger_prefix}: Token refresh failed, cannot retry {operation_name}"
                        logger.error(log_msg if self.logger_prefix else log_msg.replace(": ", ""))
                        raise
                else:
                    raise
            except Exception as e:
                # For non-ApiException errors, don't retry
                raise
        
        # Should not reach here, but just in case
        raise RuntimeError(f"Failed to execute {operation_name} after {max_retries} retries")

