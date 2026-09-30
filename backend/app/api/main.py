import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

from app.api.routes import auth, events, system, tasks
from app.core.errors import register_error_handlers
from app.core.logging import setup_from_settings


def create_app() -> FastAPI:
    setup_from_settings()
    app = FastAPI(title="AI Task Bot")
    register_error_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(tasks.stats_router)
    app.include_router(events.router)
    return app


app = create_app()
