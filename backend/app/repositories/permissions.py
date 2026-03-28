from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.permission import Permission


class PermissionRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_user(self, user_id: int) -> list[Permission]:
        return list(
            self.session.scalars(
                select(Permission).where(Permission.user_id == user_id).order_by(Permission.provider, Permission.tool_name)
            )
        )

    def get_for_tool(self, user_id: int, agent_name: str, provider: str, tool_name: str) -> Permission | None:
        return self.session.scalar(
            select(Permission).where(
                Permission.user_id == user_id,
                Permission.agent_name == agent_name,
                Permission.provider == provider,
                Permission.tool_name == tool_name,
            )
        )

    def upsert(
        self,
        *,
        user_id: int,
        agent_name: str,
        provider: str,
        tool_name: str,
        is_allowed: bool,
        risk_level: str,
        approval_window_minutes: int | None = None,
    ) -> Permission:
        permission = self.get_for_tool(user_id, agent_name, provider, tool_name)
        if permission is None:
            permission = Permission(
                user_id=user_id,
                agent_name=agent_name,
                provider=provider,
                tool_name=tool_name,
                is_allowed=is_allowed,
                risk_level=risk_level,
                approval_window_minutes=approval_window_minutes,
            )
            self.session.add(permission)
        else:
            permission.is_allowed = is_allowed
            permission.risk_level = risk_level
            permission.approval_window_minutes = approval_window_minutes
        self.session.flush()
        return permission

    def clear_expired_for_user(self, user_id: int) -> None:
        for row in self.list_for_user(user_id):
            # approval_window_minutes controls reuse window after approval and should
            # not auto-expire policy permissions by itself.
            if row.approval_window_minutes is None:
                continue
            if row.approval_window_minutes <= 0:
                row.approval_window_minutes = None
        self.session.flush()

