from __future__ import annotations

from pydantic import BaseModel, Field


class DiagnosticCheck(BaseModel):
    key: str
    status: str
    code: str
    detail: str


class ReadinessResponse(BaseModel):
    status: str
    strict_live_mode: bool = False
    checks: list[DiagnosticCheck] = Field(default_factory=list)
    blocking_checks: list[DiagnosticCheck] = Field(default_factory=list)


class AuthDiagnosticsResponse(ReadinessResponse):
    environment: str
    mock_fallbacks_enabled: list[str] = Field(default_factory=list)
