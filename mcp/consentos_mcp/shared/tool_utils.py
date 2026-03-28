from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared.backend_client import BackendClient
from consentos_mcp.shared.settings import get_settings


async def wait_for_approval(
    backend: BackendClient,
    context: AgentContext,
    activity_log_id: int,
) -> dict[str, Any]:
    settings = get_settings()
    max_attempts = max(1, settings.approval_timeout_seconds // settings.approval_poll_interval_seconds)
    for _ in range(max_attempts):
        status = await backend.approval_status(context, activity_log_id)
        expires_at = status.get("approved_until") or status.get("expires_at")
        if _is_iso_expired(expires_at):
            return {"status": "failed", "detail": "Approval window expired before execution."}
        if status["status"] in {"approved", "rejected", "completed", "failed"}:
            return status
        await asyncio.sleep(settings.approval_poll_interval_seconds)
    return {"status": "failed", "detail": "Approval timed out before the action could run."}


def schedule_after_approval(
    *,
    backend: BackendClient,
    context: AgentContext,
    activity_log_id: int,
    performer: Callable[[], Awaitable[None]],
) -> None:
    async def runner() -> None:
        resolution = await wait_for_approval(backend, context, activity_log_id)
        if resolution["status"] != "approved":
            if resolution["status"] == "failed":
                await backend.update_activity(context, activity_log_id, "failed")
            return
        try:
            await performer()
        except Exception:
            await backend.update_activity(context, activity_log_id, "failed")
            return
        await backend.update_activity(context, activity_log_id, "completed")

    asyncio.create_task(runner())


def _is_iso_expired(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= datetime.now(timezone.utc)
