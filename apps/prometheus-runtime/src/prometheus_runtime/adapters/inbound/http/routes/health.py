"""Unauthenticated readiness endpoint."""

from fastapi import APIRouter

from prometheus_runtime import __version__

router = APIRouter()


@router.get("/v1/health")
def health() -> dict[str, str]:
    """Report process readiness without initializing heavy adapters."""

    return {"status": "ok", "version": __version__}
