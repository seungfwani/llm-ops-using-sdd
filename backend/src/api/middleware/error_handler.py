"""Global error handling middleware for FastAPI."""
from __future__ import annotations

import logging
import traceback
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import OperationalError, DisconnectionError
from psycopg import OperationalError as PsycopgOperationalError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to catch all exceptions and return standardized error responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle any exceptions."""
        try:
            response = await call_next(request)
            return response
        except RequestValidationError as e:
            # Handle Pydantic validation errors
            logger.warning(f"Validation error on {request.url.path}: {e.errors()}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,  # Always return 200 per constitution
                content={
                    "status": "fail",
                    "message": f"Validation error: {', '.join([err['msg'] for err in e.errors()])}",
                    "data": None,
                },
            )
        except HTTPException as e:
            # Handle HTTP exceptions (4xx, 5xx)
            status_code = e.status_code
            error_category = "client_error" if 400 <= status_code < 500 else "server_error"
            logger.error(
                f"HTTP {status_code} on {request.url.path}: {e.detail}",
                extra={"error_category": error_category, "status_code": status_code},
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,  # Always return 200 per constitution
                content={
                    "status": "fail",
                    "message": e.detail,
                    "data": None,
                },
            )
        except (OperationalError, DisconnectionError, PsycopgOperationalError) as e:
            # Handle database connection errors
            error_id = id(e)
            logger.error(
                f"Database connection error on {request.url.path} (error_id={error_id}): {str(e)}",
                exc_info=True,
                extra={
                    "error_id": error_id,
                    "path": request.url.path,
                    "method": request.method,
                    "error_type": "database_connection_error",
                },
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "fail",
                    "message": f"Database connection error. Please try again or contact support if the issue persists (error_id={error_id}).",
                    "data": None,
                },
            )
        except ValueError as e:
            # Handle value errors (business logic errors)
            logger.warning(f"Value error on {request.url.path}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "fail",
                    "message": str(e),
                    "data": None,
                },
            )
        except Exception as e:
            # Handle all other exceptions (5xx equivalent)
            error_id = id(e)
            logger.error(
                f"Unhandled exception on {request.url.path} (error_id={error_id}): {str(e)}",
                exc_info=True,
                extra={
                    "error_id": error_id,
                    "path": request.url.path,
                    "method": request.method,
                    "traceback": traceback.format_exc(),
                },
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,  # Always return 200 per constitution
                content={
                    "status": "fail",
                    "message": f"Internal server error (error_id={error_id}). Please contact support.",
                    "data": None,
                },
            )


def add_error_handler(app: ASGIApp) -> None:
    """Add error handler middleware to FastAPI app."""
    app.add_middleware(ErrorHandlerMiddleware)

