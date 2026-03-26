from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_ciba_provider, get_current_user, get_db
from app.schemas.approvals import ApprovalRequest, ApprovalStatusResponse
from app.schemas.auth import AuthenticatedUser
from app.schemas.permissions import RiskCheckRequest, RiskCheckResponse
from app.services.approval_service import ApprovalService

router = APIRouter(tags=["approvals"])


@router.post("/api/risk/require_approval", response_model=RiskCheckResponse)
def require_approval(
    payload: RiskCheckRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    ciba_provider=Depends(get_ciba_provider),
) -> RiskCheckResponse:
    return ApprovalService(db, ciba_provider).require_approval(
        current_user.id,
        payload.agent_name,
        payload.provider,
        payload.tool_name,
    )


@router.post("/api/approvals/request", response_model=ApprovalStatusResponse)
async def request_approval(
    payload: ApprovalRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    ciba_provider=Depends(get_ciba_provider),
) -> ApprovalStatusResponse:
    return await ApprovalService(db, ciba_provider).request(current_user, payload)


@router.get("/api/approvals/{activity_id}", response_model=ApprovalStatusResponse)
async def approval_status(
    activity_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    ciba_provider=Depends(get_ciba_provider),
) -> ApprovalStatusResponse:
    return await ApprovalService(db, ciba_provider).status(current_user, activity_id)

