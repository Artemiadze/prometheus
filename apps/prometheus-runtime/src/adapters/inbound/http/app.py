"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from adapters.inbound.http.errors import install_exception_handlers, unhandled_exception
from adapters.inbound.http.jobs import BackgroundJobRunner
from adapters.inbound.http.package_version import package_version
from adapters.inbound.http.routes.chat import router as chat_router
from adapters.inbound.http.routes.documents import router as documents_router
from adapters.inbound.http.routes.health import router as health_router
from adapters.inbound.http.routes.jobs import router as jobs_router
from adapters.inbound.http.routes.reindex import router as reindex_router
from adapters.inbound.http.routes.search import router as search_router
from adapters.inbound.http.routes.status import router as status_router
from adapters.inbound.http.routes.sync import router as sync_router
from adapters.outbound.filesystem.logging_setup import log_context
from application.ports.job_store import JobStore


def create_app(
    container: object | None = None,
    *,
    vault_registry: object | None = None,
    job_store: JobStore | None = None,
) -> FastAPI:
    """Create the HTTP adapter without resolving lazy runtime dependencies."""

    app = FastAPI(
        title="Prometheus Runtime",
        version=package_version(),
        docs_url=None,
        redoc_url=None,
    )
    app.state.container = container
    app.state.vault_registry = vault_registry
    app.state.job_store = job_store
    app.state.job_runner = None if job_store is None else BackgroundJobRunner(job_store)
    app.include_router(health_router)
    app.include_router(status_router)
    app.include_router(documents_router)
    app.include_router(sync_router)
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(reindex_router)
    app.include_router(jobs_router)

    for error_type, handler in install_exception_handlers(unhandled_exception).items():
        app.add_exception_handler(error_type, handler)

    @app.middleware("http")
    async def correlation_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        with log_context(request_id=request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    return app
