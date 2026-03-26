from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.config import Settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ApprovalStartResult:
    authorization_request_id: str
    detail: str
    mode: str
    interval: int = 2


@dataclass
class ApprovalPollResult:
    status: str
    detail: str


class Auth0CIBAProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._mock_approvals: dict[str, datetime] = {}

    async def start(self, *, user_sub: str, binding_message: str) -> ApprovalStartResult:
        if self._can_use_auth0():
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{self.settings.auth0_base_url}/bc-authorize",
                    data={
                        "client_id": self.settings.auth0_ciba_client_id,
                        "client_secret": self.settings.auth0_ciba_client_secret,
                        "scope": self.settings.auth0_ciba_scope,
                        "login_hint": user_sub,
                        "binding_message": binding_message[:128],
                        "requested_expiry": self.settings.auth0_ciba_requested_expiry,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return ApprovalStartResult(
                    authorization_request_id=payload["auth_req_id"],
                    detail="Approval requested via Auth0 CIBA.",
                    mode="auth0-ciba",
                    interval=int(payload.get("interval", 2)),
                )

        if not self.settings.auto_approve_when_ciba_unavailable:
            raise RuntimeError("Auth0 CIBA is not configured and demo auto-approval is disabled.")

        auth_req_id = f"demo-{secrets.token_urlsafe(10)}"
        self._mock_approvals[auth_req_id] = utcnow() + timedelta(seconds=self.settings.auto_approve_delay_seconds)
        return ApprovalStartResult(
            authorization_request_id=auth_req_id,
            detail="Approval queued in demo mode.",
            mode="demo-auto-approve",
        )

    async def poll(self, authorization_request_id: str) -> ApprovalPollResult:
        if authorization_request_id.startswith("demo-"):
            ready_at = self._mock_approvals.get(authorization_request_id)
            if ready_at is None:
                return ApprovalPollResult(status="rejected", detail="Unknown approval request.")
            if utcnow() >= ready_at:
                return ApprovalPollResult(status="approved", detail="Demo approval completed.")
            return ApprovalPollResult(status="pending", detail="Waiting for demo approval.")

        if not self._can_use_auth0():
            return ApprovalPollResult(status="pending", detail="Waiting for Auth0 approval.")

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.settings.auth0_base_url}/oauth/token",
                data={
                    "grant_type": "urn:openid:params:grant-type:ciba",
                    "auth_req_id": authorization_request_id,
                    "client_id": self.settings.auth0_ciba_client_id,
                    "client_secret": self.settings.auth0_ciba_client_secret,
                },
            )
            if response.status_code == 200:
                return ApprovalPollResult(status="approved", detail="Approved by Auth0.")
            payload = response.json()
            error = payload.get("error")
            if error == "authorization_pending":
                return ApprovalPollResult(status="pending", detail="Approval still pending.")
            if error in {"access_denied", "expired_token"}:
                return ApprovalPollResult(status="rejected", detail=payload.get("error_description", error))
            response.raise_for_status()
            return ApprovalPollResult(status="pending", detail="Approval pending.")

    def _can_use_auth0(self) -> bool:
        return bool(
            self.settings.auth0_base_url
            and self.settings.auth0_ciba_client_id
            and self.settings.auth0_ciba_client_secret
        )

