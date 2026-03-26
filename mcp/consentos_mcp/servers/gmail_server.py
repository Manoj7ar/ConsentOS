from __future__ import annotations

import asyncio
import base64
from email.utils import parsedate_to_datetime
import re
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

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

mcp = FastMCP("ConsentOS Gmail")

TOOLS = {
    "gmail:read_inbox_summary": {
        "provider": "google",
        "risk": "low",
        "description": "Summarize invoice-related email.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "gmail:read_unpaid_clients": {
        "provider": "google",
        "risk": "low",
        "description": "List clients with overdue invoices.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "gmail:draft_followup_email": {
        "provider": "google",
        "risk": "low",
        "description": "Create a follow-up email draft.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "gmail:send_email": {
        "provider": "google",
        "risk": "high",
        "description": "Send a draft email after approval.",
        "requires_connected_account": True,
        "approval_mode": "policy-step-up",
    },
}
RESOURCES = {
    "gmail://recent_invoices": {"provider": "google", "description": "Recent invoice emails."},
    "gmail://unpaid_clients": {"provider": "google", "description": "Clients with overdue invoices."},
}

_AMOUNT_RE = re.compile(r"\$[0-9][0-9,]*(?:\.[0-9]{2})?")
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_EMAIL_RE = re.compile(r"<([^>]+)>")


async def fetch_recent_invoices(context: AgentContext) -> list[dict[str, str]]:
    settings = get_settings()
    backend = BackendClient()
    access_token = await exchange_provider_access_token(backend=backend, context=context, provider="google")
    payload = await request_json(
        provider="google",
        method="GET",
        url=f"{settings.gmail_api_base_url}/users/me/messages",
        access_token=access_token,
        params={"q": settings.gmail_recent_query, "maxResults": settings.gmail_recent_limit},
    )
    messages = payload.get("messages", [])
    if not messages:
        return []

    details = await asyncio.gather(
        *[_fetch_message_detail(settings.gmail_api_base_url, access_token, item["id"]) for item in messages],
        return_exceptions=True,
    )

    invoices: list[dict[str, str]] = []
    for detail in details:
        if isinstance(detail, Exception):
            raise detail
        invoices.append(detail)
    return invoices


async def list_unpaid_clients_data(context: AgentContext) -> list[dict[str, str]]:
    invoices = await fetch_recent_invoices(context)
    clients: list[dict[str, str]] = []
    for row in invoices:
        content = f"{row['subject']} {row['snippet']}"
        clients.append(
            {
                "client_email": row["client_email"],
                "amount": _extract_amount(content) or "unknown",
                "due_date": _extract_due_date(content),
            }
        )
    return clients


async def recent_invoices_text(context: AgentContext) -> str:
    try:
        invoices = await fetch_recent_invoices(context)
    except ProviderApiError as exc:
        return f"Failed to load recent invoices: {exc.detail}"
    return "\n".join(
        f"- {item['date']} | {item['sender']} | {item['subject']} | {item['snippet']}" for item in invoices
    )


async def unpaid_clients_text(context: AgentContext) -> str:
    try:
        clients = await list_unpaid_clients_data(context)
    except ProviderApiError as exc:
        return f"Failed to load unpaid clients: {exc.detail}"
    return "\n".join(
        f"- {item['client_email']} owes {item['amount']} (due {item['due_date']})" for item in clients
    )


async def read_inbox_summary_action(context: AgentContext) -> dict[str, Any]:
    backend = BackendClient()
    try:
        invoices = await fetch_recent_invoices(context)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="google",
            tool_name="gmail:read_inbox_summary",
            action="read_inbox",
            input_payload={},
            detail=exc.detail,
        )
        return failed_result(
            provider="google",
            tool_name="gmail:read_inbox_summary",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    summary = "\n".join(
        f"- {item['date']} | {item['sender']} | {item['subject']} | {item['snippet']}" for item in invoices
    )
    activity = await backend.create_activity(
        context,
        provider="google",
        tool_name="gmail:read_inbox_summary",
        action="read_inbox",
        input={"message_count": len(invoices)},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "google",
        "tool_name": "gmail:read_inbox_summary",
        "activity_log_id": activity["id"],
        "summary": summary,
        "message_count": len(invoices),
    }


async def read_unpaid_clients_action(context: AgentContext) -> dict[str, Any]:
    backend = BackendClient()
    try:
        clients = await list_unpaid_clients_data(context)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="google",
            tool_name="gmail:read_unpaid_clients",
            action="read_unpaid_clients",
            input_payload={},
            detail=exc.detail,
        )
        return failed_result(
            provider="google",
            tool_name="gmail:read_unpaid_clients",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    summary = "\n".join(f"- {item['client_email']} owes {item['amount']} (due {item['due_date']})" for item in clients)
    activity = await backend.create_activity(
        context,
        provider="google",
        tool_name="gmail:read_unpaid_clients",
        action="read_unpaid_clients",
        input={"client_count": len(clients)},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "google",
        "tool_name": "gmail:read_unpaid_clients",
        "activity_log_id": activity["id"],
        "summary": summary,
        "clients": clients,
    }


async def draft_followup_email_action(
    context: AgentContext,
    client_email: str,
    amount: str,
    due_date: str,
) -> dict[str, Any]:
    backend = BackendClient()
    message = EmailMessage()
    message["To"] = client_email
    message["Subject"] = f"Quick follow-up on your outstanding invoice ({amount})"
    message.set_content(
        (
            f"Hi,\n\nThis is a quick follow-up on the outstanding invoice for {amount}, which was due on {due_date}. "
            "Please let me know if you need the invoice resent or if there is anything blocking payment.\n\nBest,\nConsentOS"
        )
    )
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8").rstrip("=")

    try:
        access_token = await exchange_provider_access_token(backend=backend, context=context, provider="google")
        payload = await request_json(
            provider="google",
            method="POST",
            url=f"{get_settings().gmail_api_base_url}/users/me/drafts",
            access_token=access_token,
            json_body={"message": {"raw": raw}},
        )
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="google",
            tool_name="gmail:draft_followup_email",
            action="draft_email",
            input_payload={"client_email": client_email, "amount": amount, "due_date": due_date},
            detail=exc.detail,
        )
        return failed_result(
            provider="google",
            tool_name="gmail:draft_followup_email",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    activity = await backend.create_activity(
        context,
        provider="google",
        tool_name="gmail:draft_followup_email",
        action="draft_email",
        input={"client_email": client_email, "amount": amount, "due_date": due_date},
        status="drafted",
    )
    return {
        "status": "drafted",
        "provider": "google",
        "tool_name": "gmail:draft_followup_email",
        "activity_log_id": activity["id"],
        "to": client_email,
        "subject": str(message["Subject"]),
        "body": message.get_content(),
        "draft_id": payload["id"],
    }


async def send_email_action(context: AgentContext, draft_id: str) -> dict[str, Any]:
    backend = BackendClient()
    risk = await backend.require_approval(context, "google", "gmail:send_email")
    if not risk["permission_allowed"]:
        return {
            "status": "blocked",
            "provider": "google",
            "tool_name": "gmail:send_email",
            "detail": "Sending email is disabled for this agent/user combination.",
        }

    if risk["needs_approval"]:
        approval = await backend.request_approval(
            context,
            provider="google",
            tool_name="gmail:send_email",
            action="send_email",
            input={"draft_id": draft_id},
        )

        async def performer() -> None:
            await _send_draft(context, draft_id)

        schedule_after_approval(
            backend=backend,
            context=context,
            activity_log_id=approval["activity_log_id"],
            performer=performer,
        )
        return {
            "status": "pending_approval",
            "provider": "google",
            "tool_name": "gmail:send_email",
            "activity_log_id": approval["activity_log_id"],
            "authorization_request_id": approval["authorization_request_id"],
            "detail": approval["detail"],
            "approval_mode": approval.get("mode"),
        }

    try:
        payload = await _send_draft(context, draft_id)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="google",
            tool_name="gmail:send_email",
            action="send_email",
            input_payload={"draft_id": draft_id},
            detail=exc.detail,
        )
        return failed_result(
            provider="google",
            tool_name="gmail:send_email",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    activity = await backend.create_activity(
        context,
        provider="google",
        tool_name="gmail:send_email",
        action="send_email",
        input={"draft_id": draft_id},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "google",
        "tool_name": "gmail:send_email",
        "activity_log_id": activity["id"],
        "message_id": payload.get("id", draft_id),
    }


async def _fetch_message_detail(gmail_api_base_url: str, access_token: str, message_id: str) -> dict[str, str]:
    payload = await request_json(
        provider="google",
        method="GET",
        url=f"{gmail_api_base_url}/users/me/messages/{message_id}",
        access_token=access_token,
        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
    )
    headers = {header["name"].lower(): header["value"] for header in payload.get("payload", {}).get("headers", [])}
    sender = headers.get("from", "unknown")
    subject = headers.get("subject", "(no subject)")
    date = headers.get("date", datetime.now(UTC).strftime("%Y-%m-%d"))
    snippet = payload.get("snippet", "")
    return {
        "id": message_id,
        "subject": subject,
        "sender": sender,
        "date": _normalize_date(date),
        "snippet": snippet,
        "client_email": _extract_email(sender),
    }


async def _send_draft(context: AgentContext, draft_id: str) -> dict[str, Any]:
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="google")
    return await request_json(
        provider="google",
        method="POST",
        url=f"{get_settings().gmail_api_base_url}/users/me/drafts/send",
        access_token=access_token,
        json_body={"id": draft_id},
    )


def _extract_email(value: str) -> str:
    matched = _EMAIL_RE.search(value)
    if matched:
        return matched.group(1)
    return value.strip()


def _extract_amount(value: str) -> str | None:
    matched = _AMOUNT_RE.search(value)
    return matched.group(0) if matched else None


def _extract_due_date(value: str) -> str:
    matched = _DATE_RE.search(value)
    if matched:
        return matched.group(0)
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _normalize_date(value: str) -> str:
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        matched = _DATE_RE.search(value)
        if matched:
            return matched.group(0)
    return value


@mcp.resource("gmail://recent_invoices")
async def recent_invoices_resource() -> str:
    return await recent_invoices_text(default_server_context())


@mcp.resource("gmail://unpaid_clients")
async def unpaid_clients_resource() -> str:
    return await unpaid_clients_text(default_server_context())


@mcp.tool(name="gmail:read_inbox_summary")
async def read_inbox_summary() -> dict[str, Any]:
    """Read and summarize invoice-related email. Risk: low."""
    return await read_inbox_summary_action(default_server_context())


@mcp.tool(name="gmail:read_unpaid_clients")
async def read_unpaid_clients() -> dict[str, Any]:
    """Read overdue invoice clients. Risk: low."""
    return await read_unpaid_clients_action(default_server_context())


@mcp.tool(name="gmail:draft_followup_email")
async def draft_followup_email(client_email: str, amount: str, due_date: str) -> dict[str, Any]:
    """Draft a follow-up email. Risk: low."""
    return await draft_followup_email_action(default_server_context(), client_email, amount, due_date)


@mcp.tool(name="gmail:send_email")
async def send_email(draft_id: str) -> dict[str, Any]:
    """Send a Gmail draft after approval. Risk: high."""
    return await send_email_action(default_server_context(), draft_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
