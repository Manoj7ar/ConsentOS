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
            )
            self.session.add(permission)
        else:
            permission.is_allowed = is_allowed
            permission.risk_level = risk_level
        self.session.flush()
        return permission

