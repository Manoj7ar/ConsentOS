from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_db
from app.schemas.auth import AuthenticatedUser
from app.schemas.security import ReceiptIntegritySummary, WriteControlResponse, WriteControlUpdateRequest
from app.services.security_service import SecurityService

router = APIRouter(prefix="/api/security", tags=["security"])


@router.get("/receipt-chain/verify", response_model=ReceiptIntegritySummary)
def verify_receipt_chain(current_user: AuthenticatedUser = Depends(get_current_user), db=Depends(get_db)) -> ReceiptIntegritySummary:
    return SecurityService(db).verify_receipt_chain(current_user.id)


@router.get("/write-control", response_model=WriteControlResponse)
def get_write_control(current_user: AuthenticatedUser = Depends(get_current_user), db=Depends(get_db)) -> WriteControlResponse:
    return SecurityService(db).write_control_status(current_user.id)


@router.post("/write-control", response_model=WriteControlResponse)
def set_write_control(
    payload: WriteControlUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
) -> WriteControlResponse:
    return SecurityService(db).set_write_control(current_user.id, payload)
