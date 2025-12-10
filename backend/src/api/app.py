from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add src directory to Python path
# app.py is at backend/src/api/app.py, so parent.parent is backend/src
src_dir = Path(__file__).parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.observability import add_observability
from core.database import SessionLocal
from core.settings import get_settings
from governance.middleware import PolicyEngine, RBACMiddleware
from api.middleware.error_handler import add_error_handler
from api.routes import include_routes
from training.services import TrainingJobService

logger = logging.getLogger(__name__)


def custom_openapi(app: FastAPI):
    """Custom OpenAPI schema that includes authentication headers."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security headers to all paths
    security_headers = {
        "X-User-Id": {
            "type": "apiKey",
            "name": "X-User-Id",
            "in": "header",
            "description": "User ID for authentication",
        },
        "X-User-Roles": {
            "type": "apiKey",
            "name": "X-User-Roles",
            "in": "header",
            "description": "Comma-separated list of user roles (e.g., 'llm-ops-user')",
        },
    }
    
    # Add headers as parameters to all paths
    for path, path_item in openapi_schema.get("paths", {}).items():
        # Skip docs endpoints
        if path in ["/llm-ops/v1/docs", "/llm-ops/v1/openapi.json", "/llm-ops/v1/redoc"]:
            continue
            
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                if "parameters" not in operation:
                    operation["parameters"] = []
                
                # Add headers if not already present
                existing_params = {p["name"] for p in operation["parameters"] if p.get("in") == "header"}
                
                if "X-User-Id" not in existing_params:
                    operation["parameters"].append({
                        "name": "X-User-Id",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "User ID for authentication",
                        "example": "test-user",
                    })
                
                if "X-User-Roles" not in existing_params:
                    operation["parameters"].append({
                        "name": "X-User-Roles",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Comma-separated list of user roles",
                        "example": "llm-ops-user",
                    })
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def sync_training_job_statuses():
    """Background task to sync training job statuses with Kubernetes."""
    settings = get_settings()
    if settings.training_job_status_sync_interval <= 0:
        return
    
    session = SessionLocal()
    try:
        service = TrainingJobService(session)
        updated_count = service.sync_all_active_jobs()
        if updated_count > 0:
            logger.debug(f"Synced {updated_count} training job(s) with Kubernetes")
    except Exception as e:
        logger.error(f"Error syncing training job statuses: {e}", exc_info=True)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    settings = get_settings()
    scheduler = None
    
    # Start scheduler if interval is configured
    if settings.training_job_status_sync_interval > 0:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            sync_training_job_statuses,
            trigger=IntervalTrigger(seconds=settings.training_job_status_sync_interval),
            id="sync_training_jobs",
            name="Sync training job statuses with Kubernetes",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(
            f"Started training job status sync scheduler "
            f"(interval: {settings.training_job_status_sync_interval}s)"
        )
    
    yield
    
    # Shutdown scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("Stopped training job status sync scheduler")


def create_app() -> FastAPI:
    app = FastAPI(
        title="LLM Ops Platform API",
        version="0.1.0",
        docs_url="/llm-ops/v1/docs",
        openapi_url="/llm-ops/v1/openapi.json",
        swagger_ui_init_oauth={
            "clientId": "llm-ops-client",
            "appName": "LLM Ops Platform",
        },
        swagger_ui_parameters={
            "persistAuthorization": True,
        },
        lifespan=lifespan,
    )
    
    # Override OpenAPI schema to include auth headers
    app.openapi = lambda: custom_openapi(app)

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add error handler first to catch all exceptions
    add_error_handler(app)
    add_observability(app)
    register_routes(app)
    app.add_middleware(RBACMiddleware, policy_engine=PolicyEngine())
    return app


def register_routes(app: FastAPI) -> None:
    include_routes(app)


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from core.settings import get_settings
    
    settings = get_settings()
    # Map log level string to uvicorn log level
    uvicorn_log_level = settings.log_level.lower()
    
    # Use import string for reload to work properly
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"],
        log_level=uvicorn_log_level,
    )
