from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_auth0_sub(self, auth0_sub: str) -> User | None:
        return self.session.scalar(select(User).where(User.auth0_sub == auth0_sub))

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def create(self, auth0_sub: str) -> User:
        user = User(auth0_sub=auth0_sub)
        self.session.add(user)
        self.session.flush()
        return user

    def set_emergency_write_blocked(self, user_id: int, *, blocked: bool) -> User | None:
        user = self.session.get(User, user_id)
        if user is None:
            return None
        user.emergency_write_blocked = blocked
        self.session.flush()
        return user

    def update_email(self, user: User, email: str | None) -> User:
        if hasattr(user, "email"):
            user.email = email
            self.session.flush()
        return user

