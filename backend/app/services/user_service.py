from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.users import UserRepository


class UserService:
    def __init__(self, session: Session):
        self.repo = UserRepository(session)

    def ensure_user(self, auth0_sub: str, email: str | None = None):
        user = self.repo.get_by_auth0_sub(auth0_sub)
        if user is None:
            user = self.repo.create(auth0_sub)
        elif email:
            user = self.repo.update_email(user, email)
        return user

