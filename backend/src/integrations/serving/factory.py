"""Serving framework factory for creating adapter instances."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from integrations.serving.interface import ServingFrameworkAdapter
from integrations.serving.kserve_adapter import KServeAdapter
from integrations.serving.ray_serve_adapter import RayServeAdapter
from integrations.error_handler import ToolConfigurationError

logger = logging.getLogger(__name__)


class ServingFrameworkFactory:
    """Factory for creating serving framework adapters."""
    
    _adapters: Dict[str, type[ServingFrameworkAdapter]] = {
        "kserve": KServeAdapter,
        "ray_serve": RayServeAdapter,
    }
    
    @classmethod
    def create_adapter(
        cls,
        framework_name: str,
        config: Dict[str, Any],
    ) -> ServingFrameworkAdapter:
        """Create a serving framework adapter.
        
        Args:
            framework_name: Name of the framework ("kserve", "ray_serve")
            config: Configuration dictionary for the adapter
        
        Returns:
            ServingFrameworkAdapter instance
        
        Raises:
            ToolConfigurationError: If framework is not supported
        """
        if framework_name not in cls._adapters:
            raise ToolConfigurationError(
                message=f"Unsupported serving framework: {framework_name}",
                tool_name=framework_name,
                details={"supported_frameworks": list(cls._adapters.keys())},
            )
        
        adapter_class = cls._adapters[framework_name]
        return adapter_class(config)
    
    @classmethod
    def get_supported_frameworks(cls) -> list[str]:
        """Get list of supported serving frameworks.
        
        Returns:
            List of framework names
        """
        return list(cls._adapters.keys())
    
    @classmethod
    def register_adapter(
        cls,
        framework_name: str,
        adapter_class: type[ServingFrameworkAdapter],
    ) -> None:
        """Register a new adapter class.
        
        Args:
            framework_name: Name of the framework
            adapter_class: Adapter class implementing ServingFrameworkAdapter
        """
        cls._adapters[framework_name] = adapter_class
        logger.info(f"Registered serving framework adapter: {framework_name}")

