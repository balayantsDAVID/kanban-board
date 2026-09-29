from fastapi import FastAPI

from app.api.routes import auth, system, tasks
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="AI Task Bot")
    register_error_handlers(app)
    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(tasks.stats_router)
    return app


app = create_app()
