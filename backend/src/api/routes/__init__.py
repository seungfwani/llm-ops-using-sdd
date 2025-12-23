from fastapi import FastAPI

from . import catalog, governance, inference, serving, training, workflows, health, experiments, prompts


def include_routes(app: FastAPI) -> None:
    app.include_router(catalog.router)
    app.include_router(training.router)
    app.include_router(experiments.router)
    app.include_router(serving.router)
    app.include_router(inference.router)
    app.include_router(governance.router)
    app.include_router(workflows.router)
    app.include_router(health.router)
    app.include_router(prompts.router)

