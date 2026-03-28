from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    agent_name: str
    provider: str
    tool_name: str
    action: str
    expires_in_minutes: int | None = None
    input: dict[str, Any] = Field(default_factory=dict)


class ApprovalStatusResponse(BaseModel):
    activity_log_id: int
    status: str
    authorization_request_id: str | None = None
    detail: str | None = None
    mode: str | None = None
    approved_until: str | None = None
