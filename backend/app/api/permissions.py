from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_db
from app.schemas.auth import AuthenticatedUser
from app.schemas.permissions import (
    BlastRadiusResponse,
    PermissionRuleRead,
    PermissionUpsert,
    PolicySimulationRequest,
    PolicySimulationResponse,
    ToolBlastRadius,
)
from app.services.permissions_service import PermissionsService

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


@router.get("", response_model=list[PermissionRuleRead])
def list_permissions(current_user: AuthenticatedUser = Depends(get_current_user), db=Depends(get_db)) -> list[PermissionRuleRead]:
    return PermissionsService(db).list_permissions(current_user.id)


@router.post("", response_model=PermissionRuleRead)
def upsert_permission(
    payload: PermissionUpsert,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
) -> PermissionRuleRead:
    return PermissionsService(db).upsert_permission(current_user.id, payload)


@router.post("/simulate", response_model=PolicySimulationResponse)
def simulate_policy(
    payload: PolicySimulationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
) -> PolicySimulationResponse:
    return PermissionsService(db).simulate(current_user.id, payload)


@router.get("/blast-radius", response_model=BlastRadiusResponse)
def blast_radius(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
) -> BlastRadiusResponse:
    raw = PermissionsService(db).blast_radius(current_user.id)
    return BlastRadiusResponse(items=[ToolBlastRadius(**item) for item in raw["items"]])

