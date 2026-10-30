"""Application factory."""
from typing import Optional

from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routes import router
from app.config import Settings, get_settings
from app.middleware.stack import install_middleware


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Day-ahead wind forecast portal API",
        version="1.0.0",
        description=(
            "Read-only API over Elexon wind actuals (FUELHH) and forecasts (WINDFOR) for purchase decisions "
            "made in January 2026. Convention everywhere: error = forecast - actual."
        ),
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    register_error_handlers(app)
    app.include_router(router)
    install_middleware(app, settings)
    return app


app = create_app()