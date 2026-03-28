from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.users import UserRepository
from app.services.activity_service import ActivityService
from app.schemas.security import ReceiptIntegritySummary, WriteControlResponse, WriteControlUpdateRequest


class SecurityService:
    def __init__(self, session: Session):
        self.activity_service = ActivityService(session)
        self.users = UserRepository(session)

    def verify_receipt_chain(self, user_id: int) -> ReceiptIntegritySummary:
        result = self.activity_service.verify_integrity(user_id)
        return ReceiptIntegritySummary(
            status=result.status,
            checked_records=result.checked_records,
            broken_record_ids=result.broken_record_ids,
            latest_receipt_hash=result.latest_receipt_hash,
            detail="Tamper-evident receipt chain is valid." if result.status == "ok" else "Receipt chain mismatch detected.",
        )

    def write_control_status(self, user_id: int) -> WriteControlResponse:
        user = self.users.get_by_id(user_id)
        enabled = bool(user and user.emergency_write_blocked)
        detail = "Emergency write block is ON. Write actions are paused." if enabled else "Emergency write block is OFF."
        return WriteControlResponse(enabled=enabled, detail=detail)

    def set_write_control(self, user_id: int, payload: WriteControlUpdateRequest) -> WriteControlResponse:
        user = self.users.set_emergency_write_blocked(user_id, blocked=payload.enabled)
        enabled = bool(user and user.emergency_write_blocked)
        detail = "Emergency write block updated." if user is not None else "User not found while updating write control."
        return WriteControlResponse(enabled=enabled, detail=detail)
