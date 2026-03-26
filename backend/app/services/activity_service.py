from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.activity_log import ActivityLogRepository
from app.schemas.activity import ActivityCreate, ActivityMeta, ActivityRead, ActivityUpdate


class ActivityService:
    def __init__(self, session: Session):
        self.repo = ActivityLogRepository(session)

    def list_activity(self, user_id: int) -> list[ActivityRead]:
        return [self._to_read_model(record) for record in self.repo.list_for_user(user_id)]

    def create(self, user_id: int, payload: ActivityCreate) -> ActivityRead:
        record = self.repo.create(
            user_id=user_id,
            agent_name=payload.agent_name,
            provider=payload.provider,
            tool_name=payload.tool_name,
            action=payload.action,
            input=payload.input,
            status=payload.status,
            authorization_request_id=payload.authorization_request_id,
        )
        return self._to_read_model(record)

    def update(self, user_id: int, activity_id: int, payload: ActivityUpdate) -> ActivityRead:
        record = self.repo.get_for_user(user_id, activity_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
        record = self.repo.update(
            record,
            status=payload.status,
            authorization_request_id=payload.authorization_request_id,
        )
        return self._to_read_model(record)

    def get(self, user_id: int, activity_id: int):
        record = self.repo.get_for_user(user_id, activity_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
        return record

    @staticmethod
    def _to_read_model(record) -> ActivityRead:
        meta_payload = record.input.get("_consentos", {}) if isinstance(record.input, dict) else {}
        return ActivityRead(
            id=record.id,
            agent_name=record.agent_name,
            provider=record.provider,
            tool_name=record.tool_name,
            action=record.action,
            input=record.input,
            activity_meta=ActivityMeta(
                workflow_id=meta_payload.get("workflow_id"),
                workflow_run_id=meta_payload.get("workflow_run_id"),
                policy_decision=meta_payload.get("policy_decision"),
                approval_mode=meta_payload.get("approval_mode"),
            ),
            status=record.status,
            authorization_request_id=record.authorization_request_id,
            created_at=record.created_at,
        )
