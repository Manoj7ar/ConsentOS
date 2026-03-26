from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_auth0_sub(self, auth0_sub: str) -> User | None:
        return self.session.scalar(select(User).where(User.auth0_sub == auth0_sub))

    def create(self, auth0_sub: str) -> User:
        user = User(auth0_sub=auth0_sub)
        self.session.add(user)
        self.session.flush()
        return user

