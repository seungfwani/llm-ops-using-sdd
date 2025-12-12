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
from fastapi.staticfiles import StaticFiles
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
        # Try to create service - Kubernetes connection may fail in some environments
        try:
            service = TrainingJobService(session)
        except Exception as init_error:
            # Kubernetes API connection/auth failure - skip sync this time
            # This can happen if kubeconfig is invalid or cluster is unavailable
            error_msg = str(init_error)
            if "401" in error_msg or "Unauthorized" in error_msg:
                logger.debug(
                    f"Skipping training job status sync: Kubernetes API authentication failed. "
                    f"This is normal if running outside Kubernetes cluster or with invalid kubeconfig."
                )
            else:
                logger.warning(
                    f"Skipping training job status sync: Failed to initialize Kubernetes client: {init_error}"
                )
            return
        
        # Sync job statuses
        try:
            updated_count = service.sync_all_active_jobs()
            if updated_count > 0:
                logger.debug(f"Synced {updated_count} training job(s) with Kubernetes")
        except Exception as sync_error:
            # Handle API errors during sync (e.g., 401, 403, network issues)
            error_msg = str(sync_error)
            if "401" in error_msg or "Unauthorized" in error_msg:
                logger.debug(
                    f"Skipping training job status sync: Kubernetes API authentication failed. "
                    f"Error: {sync_error}"
                )
            elif "403" in error_msg or "Forbidden" in error_msg:
                logger.warning(
                    f"Skipping training job status sync: Kubernetes API permission denied. "
                    f"Error: {sync_error}"
                )
            else:
                logger.error(f"Error syncing training job statuses: {sync_error}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error in sync_training_job_statuses: {e}", exc_info=True)
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
    
    # Shutdown scheduler gracefully with timeout
    if scheduler:
        try:
            logger.info("Shutting down training job status sync scheduler...")
            # Shutdown with timeout to prevent hanging
            # wait=True: wait for running jobs to complete
            # timeout=5: maximum 5 seconds to wait
            scheduler.shutdown(wait=True, timeout=5)
            logger.info("Stopped training job status sync scheduler")
        except Exception as e:
            logger.warning(f"Error during scheduler shutdown: {e}, forcing shutdown")
            # Force shutdown if graceful shutdown fails
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass
            logger.info("Forced scheduler shutdown completed")


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
    
    # Mount static files for frontend (if static directory exists)
    # static directory is at /app/static in Docker container
    # In Docker: /app/static (from backend/src/api/app.py -> /app/backend/src/api/app.py -> /app/static)
    # In local dev: backend/../static (project root/static)
    static_dir = Path(__file__).parent.parent.parent.parent / "static"
    if not static_dir.exists():
        # Try alternative path for Docker container
        static_dir = Path("/app/static")
    
    if static_dir.exists():
        logger.info(f"Serving static files from: {static_dir}")
        
        # Mount static assets (JS, CSS, etc.) - must be before catch-all route
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
            logger.info(f"Mounted /assets from: {assets_dir}")
        
        # Serve index.html and other static files for SPA routing
        # This catch-all route must be registered last to not interfere with API routes
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve frontend SPA for all non-API routes."""
            # Don't serve SPA for API routes or already handled paths
            if (full_path.startswith("llm-ops/v1") or 
                full_path.startswith("docs") or 
                full_path.startswith("openapi.json") or 
                full_path.startswith("redoc") or
                full_path.startswith("assets")):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not found")
            
            # Try to serve the file if it exists (e.g., favicon.ico)
            file_path = static_dir / full_path
            if file_path.exists() and file_path.is_file():
                from fastapi.responses import FileResponse
                return FileResponse(str(file_path))
            
            # Otherwise serve index.html for SPA routing
            index_path = static_dir / "index.html"
            if index_path.exists():
                from fastapi.responses import FileResponse
                return FileResponse(str(index_path))
            
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
    
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
