from fastapi import FastAPI

from app.api.routes import system
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="AI Task Bot")
    register_error_handlers(app)
    app.include_router(system.router)
    return app


app = create_app()
