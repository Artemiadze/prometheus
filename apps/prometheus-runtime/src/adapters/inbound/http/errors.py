"""Privacy-safe FastAPI exception handlers and stable error responses."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from adapters.inbound.http.auth import UnauthorizedError
from adapters.inbound.http.security import CrossOriginForbiddenError, UntrustedHostError
from adapters.outbound.ollama.errors import (
    LlmContextExceededError,
    LlmModelNotFoundError,
    LlmTimeoutError,
    OllamaUnavailableError,
)
from application.errors import (
    DocumentTooLargeError,
    IndexCorruptedError,
    IndexRebuildRequiredError,
    JobNotFoundError,
    QueryTooShortError,
    RevisionConflictError,
    RuntimeVersionIncompatibleError,
    VaultNotIndexedError,
)
from domain.errors import (
    AdapterNotConfiguredError,
    ConfigurationError,
    InvalidIdentifierError,
    InvalidPathError,
    InvalidSearchScopeError,
    PrometheusError,
)

logger = logging.getLogger(__name__)

_STATUS_BY_TYPE: dict[type[PrometheusError], int] = {
    UnauthorizedError: 401,
    CrossOriginForbiddenError: 403,
    UntrustedHostError: 400,
    JobNotFoundError: 404,
    RevisionConflictError: 409,
    VaultNotIndexedError: 409,
    IndexCorruptedError: 409,
    IndexRebuildRequiredError: 409,
    RuntimeVersionIncompatibleError: 409,
    QueryTooShortError: 422,
    DocumentTooLargeError: 422,
    LlmContextExceededError: 422,
    InvalidIdentifierError: 400,
    InvalidPathError: 400,
    InvalidSearchScopeError: 400,
    OllamaUnavailableError: 503,
    LlmModelNotFoundError: 503,
    LlmTimeoutError: 504,
    ConfigurationError: 500,
    AdapterNotConfiguredError: 500,
}


def install_exception_handlers(
    app_exception_handler: Callable[[Request, Exception], Awaitable[Response]],
) -> dict[type[Exception], Callable[[Request, Exception], Awaitable[Response]]]:
    """Return handlers suitable for ``FastAPI.add_exception_handler``."""

    async def prometheus_error(request: Request, error: Exception) -> Response:
        assert isinstance(error, PrometheusError)
        return _envelope(request, error.code, str(error), _status_for(error))

    async def validation_error(request: Request, _: Exception) -> Response:
        return _envelope(request, "VALIDATION_ERROR", "Request payload is invalid", 422)

    return {
        PrometheusError: prometheus_error,
        RequestValidationError: validation_error,
        Exception: app_exception_handler,
    }


async def unhandled_exception(request: Request, error: Exception) -> Response:
    """Log implementation details locally but never serialize them to clients."""

    logger.exception("Unhandled HTTP adapter error", exc_info=error)
    return _envelope(request, "INTERNAL_ERROR", "An internal runtime error occurred", 500)


def _status_for(error: PrometheusError) -> int:
    for error_type, status in _STATUS_BY_TYPE.items():
        if isinstance(error, error_type):
            return status
    return 400


def _envelope(request: Request, code: str, message: str, status: int) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id}},
    )
