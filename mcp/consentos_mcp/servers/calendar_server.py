from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP

from consentos_mcp.shared.auth_context import AgentContext, default_server_context
from consentos_mcp.shared.backend_client import BackendClient
from consentos_mcp.shared.provider_http import (
    ProviderApiError,
    create_failed_activity,
    exchange_provider_access_token,
    failed_result,
    request_json,
)
from consentos_mcp.shared.settings import get_settings
from consentos_mcp.shared.tool_utils import schedule_after_approval

mcp = FastMCP("ConsentOS Calendar")

TOOLS = {
    "calendar:read_upcoming_meetings": {
        "provider": "google",
        "risk": "low",
        "description": "List upcoming meetings.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "calendar:create_meeting": {
        "provider": "google",
        "risk": "medium",
        "description": "Create a calendar event.",
        "requires_connected_account": True,
        "approval_mode": "policy-step-up",
    },
}
RESOURCES = {
    "calendar://upcoming_meetings": {"provider": "google", "description": "Upcoming meetings."},
}


async def fetch_upcoming_meetings(context: AgentContext) -> list[dict[str, Any]]:
    settings = get_settings()
    backend = BackendClient()
    access_token = await exchange_provider_access_token(backend=backend, context=context, provider="google")
    now = datetime.now(UTC)
    time_max = now + timedelta(days=settings.calendar_lookahead_days)
    payload = await request_json(
        provider="google",
        method="GET",
        url=f"{settings.calendar_api_base_url}/calendars/{quote(settings.calendar_id, safe='')}/events",
        access_token=access_token,
        params={
            "timeMin": now.isoformat().replace("+00:00", "Z"),
            "timeMax": time_max.isoformat().replace("+00:00", "Z"),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": settings.calendar_recent_limit,
        },
    )
    events: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        start = item.get("start", {})
        attendees = [attendee["email"] for attendee in item.get("attendees", []) if attendee.get("email")]
        date_value = start.get("dateTime") or start.get("date") or ""
        events.append(
            {
                "title": item.get("summary", "(untitled event)"),
                "date": date_value[:10],
                "time": _extract_time(date_value),
                "attendees": attendees,
                "event_id": item.get("id"),
                "html_link": item.get("htmlLink"),
            }
        )
    return events


async def upcoming_meetings_text(context: AgentContext) -> str:
    try:
        meetings = await fetch_upcoming_meetings(context)
    except ProviderApiError as exc:
        return f"Failed to load upcoming meetings: {exc.detail}"
    return "\n".join(f"- {m['date']} {m['time']} | {m['title']}" for m in meetings)


async def read_upcoming_meetings_action(context: AgentContext) -> dict[str, Any]:
    backend = BackendClient()
    try:
        meetings = await fetch_upcoming_meetings(context)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="google",
            tool_name="calendar:read_upcoming_meetings",
            action="read_calendar",
            input_payload={},
            detail=exc.detail,
        )
        return failed_result(
            provider="google",
            tool_name="calendar:read_upcoming_meetings",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    summary = "\n".join(f"- {m['date']} {m['time']} | {m['title']}" for m in meetings)
    activity = await backend.create_activity(
        context,
        provider="google",
        tool_name="calendar:read_upcoming_meetings",
        action="read_calendar",
        input={"event_count": len(meetings)},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "google",
        "tool_name": "calendar:read_upcoming_meetings",
        "activity_log_id": activity["id"],
        "summary": summary,
        "events": meetings,
    }


async def create_meeting_action(context: AgentContext, title: str, date: str, attendee_email: str) -> dict[str, Any]:
    backend = BackendClient()
    risk = await backend.require_approval(context, "google", "calendar:create_meeting")
    if not risk["permission_allowed"]:
        return {
            "status": "blocked",
            "provider": "google",
            "tool_name": "calendar:create_meeting",
            "detail": "Calendar creation is disabled.",
        }

    if risk["needs_approval"]:
        approval = await backend.request_approval(
            context,
            provider="google",
            tool_name="calendar:create_meeting",
            action="create_meeting",
            input={"title": title, "date": date, "attendee_email": attendee_email},
        )

        async def performer() -> None:
            await _create_event(context, title, date, attendee_email)

        schedule_after_approval(
            backend=backend,
            context=context,
            activity_log_id=approval["activity_log_id"],
            performer=performer,
        )
        return {
            "status": "pending_approval",
            "provider": "google",
            "tool_name": "calendar:create_meeting",
            "activity_log_id": approval["activity_log_id"],
            "authorization_request_id": approval["authorization_request_id"],
            "detail": approval["detail"],
            "approval_mode": approval.get("mode"),
        }

    try:
        event_payload = await _create_event(context, title, date, attendee_email)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="google",
            tool_name="calendar:create_meeting",
            action="create_meeting",
            input_payload={"title": title, "date": date, "attendee_email": attendee_email},
            detail=exc.detail,
        )
        return failed_result(
            provider="google",
            tool_name="calendar:create_meeting",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    activity = await backend.create_activity(
        context,
        provider="google",
        tool_name="calendar:create_meeting",
        action="create_meeting",
        input={"title": title, "date": date, "attendee_email": attendee_email},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "google",
        "tool_name": "calendar:create_meeting",
        "activity_log_id": activity["id"],
        "event_id": event_payload.get("id"),
        "html_link": event_payload.get("htmlLink"),
        "risk_level": risk["risk_level"],
    }


async def _create_event(context: AgentContext, title: str, date: str, attendee_email: str) -> dict[str, Any]:
    settings = get_settings()
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="google")
    return await request_json(
        provider="google",
        method="POST",
        url=f"{settings.calendar_api_base_url}/calendars/{quote(settings.calendar_id, safe='')}/events",
        access_token=access_token,
        json_body=_build_event_payload(title, date, attendee_email),
    )


def _build_event_payload(title: str, date: str, attendee_email: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": title,
        "attendees": [{"email": attendee_email}],
    }
    if "T" in date:
        start_time = date if date.endswith("Z") else f"{date}Z"
        start_dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(hours=1)
        payload["start"] = {"dateTime": start_time}
        payload["end"] = {"dateTime": end_dt.isoformat().replace("+00:00", "Z")}
        return payload

    start_date = datetime.strptime(date, "%Y-%m-%d").date()
    end_date = start_date + timedelta(days=1)
    payload["start"] = {"date": start_date.isoformat()}
    payload["end"] = {"date": end_date.isoformat()}
    return payload


def _extract_time(value: str) -> str:
    if "T" not in value:
        return "all-day"
    return value[11:16]


@mcp.resource("calendar://upcoming_meetings")
async def upcoming_meetings_resource() -> str:
    return await upcoming_meetings_text(default_server_context())


@mcp.tool(name="calendar:read_upcoming_meetings")
async def read_upcoming_meetings() -> dict[str, Any]:
    """Read upcoming meetings. Risk: low."""
    return await read_upcoming_meetings_action(default_server_context())


@mcp.tool(name="calendar:create_meeting")
async def create_meeting(title: str, date: str, attendee_email: str) -> dict[str, Any]:
    """Create a meeting. Risk: medium."""
    return await create_meeting_action(default_server_context(), title, date, attendee_email)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
