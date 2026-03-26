from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ActivityCreate(BaseModel):
    agent_name: str
    provider: str
    tool_name: str
    action: str
    input: dict[str, Any] = Field(default_factory=dict)
    status: str
    authorization_request_id: str | None = None


class ActivityUpdate(BaseModel):
    status: str
    authorization_request_id: str | None = None


class ActivityMeta(BaseModel):
    workflow_id: str | None = None
    workflow_run_id: str | None = None
    policy_decision: str | None = None
    approval_mode: str | None = None


class ActivityRead(BaseModel):
    id: int
    agent_name: str
    provider: str
    tool_name: str
    action: str
    input: dict[str, Any]
    activity_meta: ActivityMeta = Field(default_factory=ActivityMeta)
    status: str
    authorization_request_id: str | None = None
    created_at: datetime


class ActivityListResponse(BaseModel):
    items: list[ActivityRead]
