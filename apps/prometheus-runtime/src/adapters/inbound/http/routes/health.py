"""Unauthenticated readiness endpoint."""

from fastapi import APIRouter

from adapters.inbound.http.package_version import package_version

router = APIRouter()


@router.get("/v1/health")
def health() -> dict[str, str]:
    """Report process readiness without initializing heavy adapters."""

    return {"status": "ok", "version": package_version()}
