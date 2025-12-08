"""Error handling wrapper for open-source tool errors.

Provides consistent error handling and wrapping for tool-specific errors.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type
from functools import wraps

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration errors."""
    
    def __init__(
        self,
        message: str,
        tool_name: str,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize integration error.
        
        Args:
            message: Human-readable error message
            tool_name: Name of the tool that raised the error
            original_error: Original exception from the tool
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.tool_name = tool_name
        self.original_error = original_error
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses.
        
        Returns:
            Dictionary representation of the error
        """
        result = {
            "error": self.message,
            "tool": self.tool_name,
            "details": self.details,
        }
        if self.original_error:
            result["original_error"] = str(self.original_error)
        return result


class ToolUnavailableError(IntegrationError):
    """Raised when a tool service is unavailable."""
    pass


class ToolConfigurationError(IntegrationError):
    """Raised when tool configuration is invalid."""
    pass


class ToolOperationError(IntegrationError):
    """Raised when a tool operation fails."""
    pass


def handle_tool_errors(
    tool_name: str,
    default_message: str = "Tool operation failed",
):
    """Decorator to wrap tool operations with error handling.
    
    Args:
        tool_name: Name of the tool for error messages
        default_message: Default error message if no specific message can be determined
    
    Returns:
        Decorated function with error handling
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except IntegrationError:
                # Re-raise integration errors as-is
                raise
            except Exception as e:
                # Wrap other exceptions
                logger.exception(f"Error in {tool_name} operation: {func.__name__}")
                raise ToolOperationError(
                    message=f"{default_message}: {str(e)}",
                    tool_name=tool_name,
                    original_error=e,
                    details={"operation": func.__name__}
                )
        return wrapper
    return decorator


def wrap_tool_error(
    error: Exception,
    tool_name: str,
    operation: str,
    message: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> IntegrationError:
    """Wrap a tool-specific error in an IntegrationError.
    
    Args:
        error: Original exception
        tool_name: Name of the tool
        operation: Operation that failed
        message: Optional custom error message
        context: Optional context information to include in error details
    
    Returns:
        Wrapped IntegrationError
    """
    if isinstance(error, IntegrationError):
        return error
    
    error_message = message or f"{tool_name} {operation} failed: {str(error)}"
    
    # Build details dictionary
    details = {"operation": operation}
    if context:
        details.update(context)
    
    # Check for specific error types first
    error_type = type(error).__name__
    error_str = str(error).lower()
    
    # Handle Hugging Face specific errors
    if "RevisionNotFoundError" in error_type or "revision not found" in error_str:
        # This is not a configuration error, but an invalid revision/version
        return ToolOperationError(
            message=f"Invalid model version or revision: {str(error)}",
            tool_name=tool_name,
            original_error=error,
            details=details
        )
    
    # Check for common error patterns
    if "connection" in error_str or "timeout" in error_str or "unreachable" in error_str:
        return ToolUnavailableError(
            message=f"{tool_name} service is unavailable",
            tool_name=tool_name,
            original_error=error,
            details=details
        )
    elif "config" in error_str or ("invalid" in error_str and "revision" not in error_str and "version" not in error_str) or "missing" in error_str:
        return ToolConfigurationError(
            message=f"{tool_name} configuration error",
            tool_name=tool_name,
            original_error=error,
            details=details
        )
    else:
        return ToolOperationError(
            message=error_message,
            tool_name=tool_name,
            original_error=error,
            details=details
        )

