"""Integration health check service.

Provides health checking for all open-source tool integrations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from datetime import datetime

from core.settings import get_settings
from integrations.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class IntegrationHealthCheck:
    """Service for checking health of all integrations."""
    
    def __init__(self, adapters: Dict[str, BaseAdapter]):
        """Initialize health check service.
        
        Args:
            adapters: Dictionary mapping integration names to adapter instances
        """
        self.adapters = adapters
        self.settings = get_settings()
    
    def check_all(self) -> Dict[str, Any]:
        """Check health of all integrations.
        
        Returns:
            Dictionary with health status for each integration:
            {
                "overall_status": "healthy" | "degraded" | "unavailable",
                "integrations": {
                    "integration_name": {
                        "status": "healthy" | "degraded" | "unavailable",
                        "enabled": bool,
                        "message": str,
                        "details": dict,
                        "checked_at": datetime
                    }
                }
            }
        """
        results = {}
        overall_status = "healthy"
        
        for name, adapter in self.adapters.items():
            try:
                if not adapter.is_enabled():
                    results[name] = {
                        "status": "disabled",
                        "enabled": False,
                        "message": "Integration is disabled",
                        "details": {},
                        "checked_at": datetime.utcnow().isoformat(),
                    }
                    continue
                
                health = adapter.health_check()
                status = health.get("status", "unavailable")
                
                results[name] = {
                    "status": status,
                    "enabled": True,
                    "message": health.get("message", ""),
                    "details": health.get("details", {}),
                    "checked_at": datetime.utcnow().isoformat(),
                }
                
                # Update overall status
                if status == "unavailable" and overall_status == "healthy":
                    overall_status = "degraded"
                elif status == "unavailable":
                    overall_status = "unavailable"
                elif status == "degraded" and overall_status == "healthy":
                    overall_status = "degraded"
            
            except Exception as e:
                logger.exception(f"Error checking health of {name}")
                results[name] = {
                    "status": "unavailable",
                    "enabled": adapter.is_enabled() if hasattr(adapter, "is_enabled") else False,
                    "message": f"Health check failed: {str(e)}",
                    "details": {},
                    "checked_at": datetime.utcnow().isoformat(),
                }
                if overall_status == "healthy":
                    overall_status = "degraded"
                else:
                    overall_status = "unavailable"
        
        return {
            "overall_status": overall_status,
            "integrations": results,
            "checked_at": datetime.utcnow().isoformat(),
        }
    
    def check_integration(self, integration_name: str) -> Dict[str, Any]:
        """Check health of a specific integration.
        
        Args:
            integration_name: Name of the integration to check
        
        Returns:
            Dictionary with health status
        
        Raises:
            ValueError: If integration not found
        """
        if integration_name not in self.adapters:
            raise ValueError(f"Integration {integration_name} not found")
        
        adapter = self.adapters[integration_name]
        
        if not adapter.is_enabled():
            return {
                "status": "disabled",
                "enabled": False,
                "message": "Integration is disabled",
                "details": {},
                "checked_at": datetime.utcnow().isoformat(),
            }
        
        try:
            health = adapter.health_check()
            return {
                "status": health.get("status", "unavailable"),
                "enabled": True,
                "message": health.get("message", ""),
                "details": health.get("details", {}),
                "checked_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.exception(f"Error checking health of {integration_name}")
            return {
                "status": "unavailable",
                "enabled": True,
                "message": f"Health check failed: {str(e)}",
                "details": {},
                "checked_at": datetime.utcnow().isoformat(),
            }

