from __future__ import annotations

from typing import Any

import httpx

from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared.settings import MCPSettings, get_settings


class BackendClient:
    def __init__(self, settings: MCPSettings | None = None):
        self.settings = settings or get_settings()

    def _headers(self, context: AgentContext) -> dict[str, str]:
        headers = {
            "x-consentos-internal-secret": self.settings.internal_api_shared_secret,
            "x-consentos-user-sub": context.user_sub,
        }
        if context.email:
            headers["x-consentos-user-email"] = context.email
        if context.auth0_subject_token:
            headers["x-consentos-auth0-subject-token"] = context.auth0_subject_token
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        context: AgentContext,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.settings.backend_base_url, timeout=20) as client:
            response = await client.request(method, path, headers=self._headers(context), json=json)
            response.raise_for_status()
            return response.json()

    async def exchange_token(self, context: AgentContext, provider: str) -> dict[str, Any]:
        return await self._request("POST", "/api/token-vault/exchange", context, {"provider": provider})

    async def create_activity(
        self,
        context: AgentContext,
        *,
        provider: str,
        tool_name: str,
        action: str,
        input: dict[str, Any],
        status: str,
        authorization_request_id: str | None = None,
    ) -> dict[str, Any]:
        enriched_input = self._with_activity_meta(context, input, policy_decision="executed")
        return await self._request(
            "POST",
            "/api/activity",
            context,
            {
                "agent_name": context.agent_name,
                "provider": provider,
                "tool_name": tool_name,
                "action": action,
                "input": enriched_input,
                "status": status,
                "authorization_request_id": authorization_request_id,
            },
        )

    async def update_activity(self, context: AgentContext, activity_id: int, status: str) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            f"/api/activity/{activity_id}",
            context,
            {"status": status},
        )

    async def require_approval(self, context: AgentContext, provider: str, tool_name: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/risk/require_approval",
            context,
            {
                "agent_name": context.agent_name,
                "provider": provider,
                "tool_name": tool_name,
            },
        )

    async def request_approval(
        self,
        context: AgentContext,
        *,
        provider: str,
        tool_name: str,
        action: str,
        input: dict[str, Any],
        approval_window_minutes: int | None = None,
    ) -> dict[str, Any]:
        enriched_input = self._with_activity_meta(context, input, policy_decision="approval_required")
        return await self._request(
            "POST",
            "/api/approvals/request",
            context,
            {
                "agent_name": context.agent_name,
                "provider": provider,
                "tool_name": tool_name,
                "action": action,
                "input": enriched_input,
                "expires_in_minutes": approval_window_minutes,
            },
        )

    async def approval_status(self, context: AgentContext, activity_log_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/api/approvals/{activity_log_id}", context)

    @staticmethod
    def _with_activity_meta(
        context: AgentContext,
        input_payload: dict[str, Any],
        *,
        policy_decision: str,
    ) -> dict[str, Any]:
        payload = dict(input_payload)
        meta = dict(payload.get("_consentos", {}))
        if context.workflow_id:
            meta["workflow_id"] = context.workflow_id
        if context.workflow_run_id:
            meta["workflow_run_id"] = context.workflow_run_id
        meta["policy_decision"] = policy_decision
        payload["_consentos"] = meta
        return payload
