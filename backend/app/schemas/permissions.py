from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PermissionRuleRead(BaseModel):
    id: int | None = None
    agent_name: str
    provider: str
    tool_name: str
    is_allowed: bool
    risk_level: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PermissionUpsert(BaseModel):
    agent_name: str
    provider: str
    tool_name: str
    is_allowed: bool
    risk_level: str


class RiskCheckRequest(BaseModel):
    agent_name: str
    provider: str
    tool_name: str


class RiskCheckResponse(BaseModel):
    permission_allowed: bool
    needs_approval: bool
    risk_level: str


class PolicySimulationRequest(BaseModel):
    agent_name: str
    provider: str
    tool_name: str
    connected_account_required: bool = True
    connected_account_present: bool | None = None
    strict_live_required: bool = True
    permission_allowed_override: bool | None = None


class PolicySimulationResponse(BaseModel):
    decision: str
    risk_level: str
    permission_allowed: bool
    needs_approval: bool
    connected_account_status: str
    strict_live_mode: bool
    reason_codes: list[str] = Field(default_factory=list)
    explanation: str
