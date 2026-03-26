from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.deps import get_settings
from app.schemas.diagnostics import ReadinessResponse
from app.services.auth0_diagnostics_service import Auth0DiagnosticsService

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", response_model=ReadinessResponse)
async def health_ready(settings: Settings = Depends(get_settings)) -> ReadinessResponse:
    return await Auth0DiagnosticsService(settings).readiness()
