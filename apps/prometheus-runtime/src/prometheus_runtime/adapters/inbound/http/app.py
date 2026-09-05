"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from prometheus_runtime import __version__
from prometheus_runtime.adapters.inbound.http.routes.health import router as health_router
from prometheus_runtime.adapters.outbound.filesystem.logging_setup import log_context


def create_app(container: object | None = None) -> FastAPI:
    """Create the HTTP adapter without resolving lazy runtime dependencies."""

    app = FastAPI(
        title="Prometheus Runtime",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )
    app.state.container = container
    app.include_router(health_router)

    @app.middleware("http")
    async def correlation_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        with log_context(request_id=request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    return app
