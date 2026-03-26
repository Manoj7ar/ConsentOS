from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


class ActivityLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_user(self, user_id: int) -> list[ActivityLog]:
        return list(
            self.session.scalars(
                select(ActivityLog).where(ActivityLog.user_id == user_id).order_by(ActivityLog.created_at.desc())
            )
        )

    def get_for_user(self, user_id: int, activity_id: int) -> ActivityLog | None:
        return self.session.scalar(
            select(ActivityLog).where(ActivityLog.user_id == user_id, ActivityLog.id == activity_id)
        )

    def create(
        self,
        *,
        user_id: int,
        agent_name: str,
        provider: str,
        tool_name: str,
        action: str,
        input: dict,
        status: str,
        authorization_request_id: str | None = None,
    ) -> ActivityLog:
        record = ActivityLog(
            user_id=user_id,
            agent_name=agent_name,
            provider=provider,
            tool_name=tool_name,
            action=action,
            input=input,
            status=status,
            authorization_request_id=authorization_request_id,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def update(self, record: ActivityLog, *, status: str, authorization_request_id: str | None = None) -> ActivityLog:
        record.status = status
        if authorization_request_id is not None:
            record.authorization_request_id = authorization_request_id
        self.session.flush()
        return record
