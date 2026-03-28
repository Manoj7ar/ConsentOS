from __future__ import annotations

import pytest

from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared.backend_client import BackendClient


@pytest.mark.anyio
async def test_request_approval_json_uses_expires_in_minutes(monkeypatch):
    captured: dict = {}

    async def capture_request(self, method, path, context, json=None):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = dict(json or {})
        return {}

    monkeypatch.setattr(BackendClient, "_request", capture_request)
    client = BackendClient()
    ctx = AgentContext(user_sub="auth0|u", email="u@example.com")
    await client.request_approval(
        ctx,
        provider="google",
        tool_name="gmail:send",
        action="send",
        input={"x": 1},
        approval_window_minutes=45,
    )
    assert captured["path"] == "/api/approvals/request"
    assert captured["json"].get("expires_in_minutes") == 45
    assert "approval_window_minutes" not in captured["json"]
