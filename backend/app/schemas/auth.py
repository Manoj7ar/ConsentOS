from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    id: int
    auth0_sub: str
    emergency_write_blocked: bool = False
    email: str | None = None
    raw_access_token: str | None = None


class AuthMeResponse(BaseModel):
    user: AuthenticatedUser

