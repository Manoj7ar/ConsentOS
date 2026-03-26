from __future__ import annotations

from pydantic import BaseModel


class TokenExchangeRequest(BaseModel):
    provider: str
    login_hint: str | None = None


class TokenExchangeResponse(BaseModel):
    external_access_token: str
    expires_in: int
    scope: str
    provider: str
    source: str

