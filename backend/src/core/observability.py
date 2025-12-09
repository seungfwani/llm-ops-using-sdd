from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram

from core.settings import get_settings

REQUEST_COUNT = Counter(
    "llm_ops_request_total",
    "Total number of HTTP requests",
    labelnames=("method", "route", "status"),
)

REQUEST_LATENCY = Histogram(
    "llm_ops_request_latency_seconds",
    "Latency of HTTP requests in seconds",
    labelnames=("method", "route"),
)


def setup_logging() -> None:
    """Setup logging configuration from settings."""
    settings = get_settings()
    
    # Map string log level to logging constant
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    log_level = log_level_map.get(settings.log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start_time

        route = request.url.path
        REQUEST_LATENCY.labels(request.method, route).observe(elapsed)
        REQUEST_COUNT.labels(request.method, route, response.status_code).inc()

        return response


def add_observability(app: FastAPI) -> None:
    setup_logging()
    app.add_middleware(ObservabilityMiddleware)

