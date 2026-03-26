from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.deps import get_current_user, get_settings
from app.schemas.auth import AuthMeResponse, AuthenticatedUser
from app.schemas.diagnostics import AuthDiagnosticsResponse
from app.services.auth0_diagnostics_service import Auth0DiagnosticsService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=AuthMeResponse)
def auth_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse(user=current_user)


@router.get("/diagnostics", response_model=AuthDiagnosticsResponse)
async def auth_diagnostics(
    _: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AuthDiagnosticsResponse:
    return await Auth0DiagnosticsService(settings).collect()
