"""Base adapter interface for open-source tool integrations.

All integration adapters must implement this base interface to ensure
consistent behavior and enable tool swapping.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAdapter(ABC):
    """Base class for all integration adapters.
    
    Provides common functionality and ensures consistent interface
    across all tool integrations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize adapter with configuration.
        
        Args:
            config: Tool-specific configuration dictionary
        """
        self.config = config
        self.enabled = config.get("enabled", False)
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the tool service is available.
        
        Returns:
            True if tool is reachable and operational, False otherwise
        """
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the tool service.
        
        Returns:
            Dictionary with health status information:
            {
                "status": "healthy" | "degraded" | "unavailable",
                "message": str,
                "details": dict
            }
        """
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """Get adapter configuration.
        
        Returns:
            Configuration dictionary
        """
        return self.config
    
    def is_enabled(self) -> bool:
        """Check if adapter is enabled.
        
        Returns:
            True if enabled, False otherwise
        """
        return self.enabled

