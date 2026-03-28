from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.ciba import Auth0CIBAProvider
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.schemas.approvals import ApprovalRequest, ApprovalStatusResponse
from app.schemas.auth import AuthenticatedUser
from app.schemas.permissions import RiskCheckResponse
from app.services.activity_service import ActivityService
from app.services.permissions_service import PermissionsService


class ApprovalService:
    def __init__(self, session: Session, provider: Auth0CIBAProvider):
        self.provider = provider
        self.permissions_service = PermissionsService(session)
        self.activity_service = ActivityService(session)

    async def request(self, user: AuthenticatedUser, payload: ApprovalRequest) -> ApprovalStatusResponse:
        risk = self.permissions_service.evaluate(
            user.id,
            payload.agent_name,
            payload.provider,
            payload.tool_name,
        )
        if not risk.permission_allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tool is not allowed for this user.")
        if not risk.needs_approval:
            input_payload = dict(payload.input)
            meta = dict(input_payload.get("_consentos", {}))
            meta["approval_mode"] = "not-required"
            input_payload["_consentos"] = meta
            activity = self.activity_service.create(
                user.id,
                ActivityCreate(
                    agent_name=payload.agent_name,
                    provider=payload.provider,
                    tool_name=payload.tool_name,
                    action=payload.action,
                    input=input_payload,
                    status="approved",
                ),
            )
            return ApprovalStatusResponse(
                activity_log_id=activity.id,
                status="approved",
                authorization_request_id=activity.authorization_request_id,
                detail="Approval not required.",
                mode="not-required",
                approved_until=None,
            )

        try:
            start = await self.provider.start(
                user_sub=user.auth0_sub,
                binding_message=f"{payload.agent_name} wants to {payload.action}",
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        input_payload = dict(payload.input)
        meta = dict(input_payload.get("_consentos", {}))
        meta["approval_mode"] = start.mode
        input_payload["_consentos"] = meta
        activity = self.activity_service.create(
            user.id,
            ActivityCreate(
                agent_name=payload.agent_name,
                provider=payload.provider,
                tool_name=payload.tool_name,
                action=payload.action,
                input=input_payload,
                status="pending",
                authorization_request_id=start.authorization_request_id,
            ),
        )
        return ApprovalStatusResponse(
            activity_log_id=activity.id,
            status=activity.status,
            authorization_request_id=start.authorization_request_id,
            detail=start.detail,
            mode=start.mode,
            approved_until=None,
        )

    async def status(self, user: AuthenticatedUser, activity_id: int) -> ApprovalStatusResponse:
        record = self.activity_service.get(user.id, activity_id)
        if record.status in {"completed", "approved", "rejected", "failed"}:
            return ApprovalStatusResponse(
                activity_log_id=record.id,
                status=record.status,
                authorization_request_id=record.authorization_request_id,
                detail=self._resolve_terminal_detail(record.status),
                mode=self._resolve_mode(record.authorization_request_id),
                approved_until=self._read_approved_until(record.input),
            )
        if not record.authorization_request_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Activity is not linked to approval.")

        poll_result = await self.provider.poll(record.authorization_request_id)
        if poll_result.status in {"approved", "rejected"}:
            approval_window_minutes = self.permissions_service.approval_window_minutes_for_tool(
                user.id,
                record.agent_name,
                record.provider,
                record.tool_name,
            )
            updated = self.activity_service.update(
                user.id,
                activity_id,
                ActivityUpdate(status=poll_result.status, authorization_request_id=record.authorization_request_id),
            )
            return ApprovalStatusResponse(
                activity_log_id=updated.id,
                status=updated.status,
                authorization_request_id=updated.authorization_request_id,
                detail=poll_result.detail,
                mode=self._resolve_mode(updated.authorization_request_id),
                approved_until=self._persist_approval_window(user.id, updated, approval_window_minutes),
            )

        return ApprovalStatusResponse(
            activity_log_id=record.id,
            status=record.status,
            authorization_request_id=record.authorization_request_id,
            detail=poll_result.detail,
            mode=self._resolve_mode(record.authorization_request_id),
            approved_until=self._read_approved_until(record.input),
        )

    def require_approval(self, user_id: int, agent_name: str, provider: str, tool_name: str) -> RiskCheckResponse:
        return self.permissions_service.evaluate(user_id, agent_name, provider, tool_name)

    @staticmethod
    def _resolve_mode(authorization_request_id: str | None) -> str | None:
        if not authorization_request_id:
            return None
        if authorization_request_id.startswith("demo-"):
            return "demo-auto-approve"
        return "auth0-ciba"

    @staticmethod
    def _resolve_terminal_detail(status: str) -> str:
        if status == "failed":
            return "The approved action failed during execution."
        return "Approval already resolved."

    def _persist_approval_window(self, user_id: int, record, approval_window_minutes: int | None) -> str | None:
        if record.status != "approved":
            return self._read_approved_until(record.input)
        if not approval_window_minutes:
            return None
        input_payload = dict(record.input) if isinstance(record.input, dict) else {}
        meta = dict(input_payload.get("_consentos", {}))
        approved_until = (datetime.now(timezone.utc) + timedelta(minutes=approval_window_minutes)).isoformat()
        meta["approved_until"] = approved_until
        input_payload["_consentos"] = meta
        self.activity_service.update_input(user_id, record.id, input_payload)
        return approved_until

    @staticmethod
    def _read_approved_until(input_payload) -> str | None:
        if not isinstance(input_payload, dict):
            return None
        meta = input_payload.get("_consentos")
        if not isinstance(meta, dict):
            return None
        value = meta.get("approved_until")
        if isinstance(value, str):
            return value
        return None
