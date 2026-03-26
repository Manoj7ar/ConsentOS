from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from consentos_mcp.shared.auth_context import AgentContext, default_server_context
from consentos_mcp.shared.backend_client import BackendClient
from consentos_mcp.shared.provider_http import (
    ProviderApiError,
    cents_from_amount,
    exchange_provider_access_token,
    format_currency_amount,
    request_json,
)
from consentos_mcp.shared.settings import get_settings
from consentos_mcp.shared.tool_utils import schedule_after_approval

mcp = FastMCP("ConsentOS Stripe")

TOOLS = {
    "stripe:read_recent_payments": {
        "provider": "stripe",
        "risk": "low",
        "description": "Read recent Stripe payments.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "stripe:create_payment_link": {
        "provider": "stripe",
        "risk": "high",
        "description": "Create a Stripe payment link.",
        "requires_connected_account": True,
        "approval_mode": "always-step-up",
    },
}
RESOURCES = {
    "stripe://recent_payments": {"provider": "stripe", "description": "Recent Stripe payments."},
}


async def fetch_recent_payments(context: AgentContext) -> list[dict[str, Any]]:
    settings = get_settings()
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="stripe")
    payload = await request_json(
        provider="stripe",
        method="GET",
        url=f"{settings.stripe_api_base_url}/payment_intents",
        access_token=access_token,
        params={"limit": settings.stripe_recent_limit},
    )
    payments: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        payments.append(
            {
                "id": item.get("id"),
                "customer": item.get("receipt_email") or item.get("customer") or "unknown",
                "amount": format_currency_amount(item.get("amount"), item.get("currency")),
                "status": item.get("status", "unknown"),
            }
        )
    return payments


async def recent_payments_text(context: AgentContext) -> str:
    try:
        payments = await fetch_recent_payments(context)
    except ProviderApiError as exc:
        return f"Failed to load recent payments: {exc.detail}"
    return "\n".join(f"- {payment['customer']} | {payment['amount']} | {payment['status']}" for payment in payments)


async def read_recent_payments_action(context: AgentContext) -> dict[str, Any]:
    backend = BackendClient()
    try:
        payments = await fetch_recent_payments(context)
    except ProviderApiError as exc:
        activity = await backend.create_activity(
            context,
            provider="stripe",
            tool_name="stripe:read_recent_payments",
            action="read_recent_payments",
            input={},
            status="failed",
        )
        return {
            "status": "failed",
            "provider": "stripe",
            "tool_name": "stripe:read_recent_payments",
            "activity_log_id": activity["id"],
            "detail": exc.detail,
        }

    summary = "\n".join(f"- {payment['customer']} | {payment['amount']} | {payment['status']}" for payment in payments)
    activity = await backend.create_activity(
        context,
        provider="stripe",
        tool_name="stripe:read_recent_payments",
        action="read_recent_payments",
        input={"payment_count": len(payments)},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "stripe",
        "tool_name": "stripe:read_recent_payments",
        "activity_log_id": activity["id"],
        "summary": summary,
        "payments": payments,
    }


async def create_payment_link_action(context: AgentContext, client_email: str, amount: str) -> dict[str, Any]:
    backend = BackendClient()
    risk = await backend.require_approval(context, "stripe", "stripe:create_payment_link")
    if not risk["permission_allowed"]:
        return {
            "status": "blocked",
            "provider": "stripe",
            "tool_name": "stripe:create_payment_link",
            "detail": "Payment link creation is disabled.",
        }

    approval = await backend.request_approval(
        context,
        provider="stripe",
        tool_name="stripe:create_payment_link",
        action="create_payment_link",
        input={"client_email": client_email, "amount": amount},
    )

    async def performer() -> None:
        await _create_payment_link(context, client_email, amount)

    schedule_after_approval(
        backend=backend,
        context=context,
        activity_log_id=approval["activity_log_id"],
        performer=performer,
    )
    return {
        "status": "pending_approval",
        "provider": "stripe",
        "tool_name": "stripe:create_payment_link",
        "activity_log_id": approval["activity_log_id"],
        "authorization_request_id": approval["authorization_request_id"],
        "detail": approval["detail"],
        "approval_mode": approval.get("mode"),
    }


async def _create_payment_link(context: AgentContext, client_email: str, amount: str) -> dict[str, Any]:
    settings = get_settings()
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="stripe")
    cents = cents_from_amount(amount)
    return await request_json(
        provider="stripe",
        method="POST",
        url=f"{settings.stripe_api_base_url}/payment_links",
        access_token=access_token,
        form_body={
            "line_items[0][price_data][currency]": settings.stripe_default_currency,
            "line_items[0][price_data][product_data][name]": f"Invoice follow-up for {client_email}",
            "line_items[0][price_data][unit_amount]": str(cents),
            "line_items[0][quantity]": "1",
            "metadata[client_email]": client_email,
        },
        headers={"content-type": "application/x-www-form-urlencoded"},
    )


@mcp.resource("stripe://recent_payments")
async def recent_payments_resource() -> str:
    return await recent_payments_text(default_server_context())


@mcp.tool(name="stripe:create_payment_link")
async def create_payment_link(client_email: str, amount: str) -> dict[str, Any]:
    """Create a Stripe payment link. Risk: high."""
    return await create_payment_link_action(default_server_context(), client_email, amount)


@mcp.tool(name="stripe:read_recent_payments")
async def read_recent_payments() -> dict[str, Any]:
    """Read recent Stripe payments. Risk: low."""
    return await read_recent_payments_action(default_server_context())


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
