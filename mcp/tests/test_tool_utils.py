from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared import tool_utils


class FakeBackend:
    def __init__(self, statuses: list[dict[str, str]]):
        self._statuses = list(statuses)
        self.updated: list[tuple[int, str]] = []

    async def approval_status(self, context: AgentContext, activity_log_id: int) -> dict[str, str]:
        if self._statuses:
            return self._statuses.pop(0)
        return {"status": "pending", "detail": "still waiting"}

    async def update_activity(self, context: AgentContext, activity_id: int, status: str) -> dict[str, str | int]:
        self.updated.append((activity_id, status))
        return {"id": activity_id, "status": status}


@pytest.mark.anyio
async def test_wait_for_approval_treats_failed_as_terminal(monkeypatch):
    monkeypatch.setattr(
        tool_utils,
        "get_settings",
        lambda: SimpleNamespace(approval_timeout_seconds=10, approval_poll_interval_seconds=1),
    )
    backend = FakeBackend([{"status": "failed", "detail": "execution failed"}])
    context = AgentContext(user_sub="auth0|demo-user", email="demo@example.com")

    result = await tool_utils.wait_for_approval(backend, context, 42)

    assert result["status"] == "failed"
    assert result["detail"] == "execution failed"


@pytest.mark.anyio
async def test_schedule_after_approval_marks_timeout_as_failed(monkeypatch):
    monkeypatch.setattr(
        tool_utils,
        "get_settings",
        lambda: SimpleNamespace(approval_timeout_seconds=1, approval_poll_interval_seconds=1),
    )

    async def fake_sleep(_: int) -> None:
        return None

    scheduled: list[object] = []

    def fake_create_task(coro: object) -> SimpleNamespace:
        scheduled.append(coro)
        return SimpleNamespace()

    monkeypatch.setattr(tool_utils.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(tool_utils.asyncio, "create_task", fake_create_task)

    backend = FakeBackend([{"status": "pending", "detail": "waiting"}])
    context = AgentContext(user_sub="auth0|demo-user", email="demo@example.com")
    performer_called = False

    async def performer() -> None:
        nonlocal performer_called
        performer_called = True

    tool_utils.schedule_after_approval(
        backend=backend,
        context=context,
        activity_log_id=42,
        performer=performer,
    )

    assert len(scheduled) == 1
    await scheduled[0]
    await asyncio.sleep(0)

    assert performer_called is False
    assert backend.updated == [(42, "failed")]


@pytest.mark.anyio
async def test_wait_for_approval_honors_expiry_in_response(monkeypatch):
    monkeypatch.setattr(
        tool_utils,
        "get_settings",
        lambda: SimpleNamespace(approval_timeout_seconds=10, approval_poll_interval_seconds=1),
    )
    backend = FakeBackend(
        [
            {
                "status": "pending",
                "detail": "waiting",
                "expires_at": "2000-01-01T00:00:00+00:00",
            }
        ]
    )
    context = AgentContext(user_sub="auth0|demo-user", email="demo@example.com")

    result = await tool_utils.wait_for_approval(backend, context, 99)

    assert result["status"] == "failed"
    assert "expired" in result["detail"].lower()
