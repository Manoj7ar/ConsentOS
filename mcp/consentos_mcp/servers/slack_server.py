from __future__ import annotations

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

mcp = FastMCP("ConsentOS Slack")

TOOLS = {
    "slack:read_recent_mentions": {
        "provider": "slack",
        "risk": "low",
        "description": "Read recent Slack mentions and urgent messages.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "slack:post_message": {
        "provider": "slack",
        "risk": "medium",
        "description": "Post a Slack message.",
        "requires_connected_account": True,
        "approval_mode": "policy-step-up",
    },
}
RESOURCES = {
    "slack://recent_mentions": {"provider": "slack", "description": "Recent Slack mentions."},
}


async def fetch_recent_mentions(context: AgentContext) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.slack_mention_channel_ids:
        raise ProviderApiError(
            provider="slack",
            detail="Set MCP_SLACK_MENTION_CHANNEL_IDS to read recent mentions from Slack.",
        )

    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="slack")
    auth_payload = await request_json(
        provider="slack",
        method="POST",
        url=f"{settings.slack_api_base_url}/auth.test",
        access_token=access_token,
    )
    user_id = auth_payload.get("user_id")
    if not user_id:
        raise ProviderApiError(provider="slack", detail="Slack auth.test did not return a user id.")

    mentions: list[dict[str, Any]] = []
    author_ids: set[str] = set()
    keywords = tuple(keyword.lower() for keyword in settings.slack_mention_keywords)
    for channel_id in settings.slack_mention_channel_ids:
        payload = await request_json(
            provider="slack",
            method="GET",
            url=f"{settings.slack_api_base_url}/conversations.history",
            access_token=access_token,
            params={"channel": channel_id, "limit": settings.slack_recent_limit},
        )
        for message in payload.get("messages", []):
            text = str(message.get("text", ""))
            lowered = text.lower()
            if f"<@{user_id}>" not in text and not any(keyword in lowered for keyword in keywords):
                continue
            author_id = message.get("user")
            if author_id:
                author_ids.add(author_id)
            mentions.append(
                {
                    "channel": channel_id,
                    "user_id": author_id or "unknown",
                    "text": text,
                    "ts": message.get("ts"),
                }
            )

    user_names = await _resolve_user_names(access_token, author_ids)
    for mention in mentions:
        mention["user"] = user_names.get(mention["user_id"], mention["user_id"])
    return mentions


async def recent_mentions_text(context: AgentContext) -> str:
    try:
        mentions = await fetch_recent_mentions(context)
    except ProviderApiError as exc:
        return f"Failed to load recent mentions: {exc.detail}"
    return "\n".join(f"- {item['channel']} | {item['user']}: {item['text']}" for item in mentions)


async def read_recent_mentions_action(context: AgentContext) -> dict[str, Any]:
    backend = BackendClient()
    try:
        mentions = await fetch_recent_mentions(context)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="slack",
            tool_name="slack:read_recent_mentions",
            action="read_recent_mentions",
            input_payload={},
            detail=exc.detail,
        )
        return failed_result(
            provider="slack",
            tool_name="slack:read_recent_mentions",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    summary = "\n".join(f"- {item['channel']} | {item['user']}: {item['text']}" for item in mentions) or "No recent mentions matched the configured filters."
    activity = await backend.create_activity(
        context,
        provider="slack",
        tool_name="slack:read_recent_mentions",
        action="read_recent_mentions",
        input={"mention_count": len(mentions)},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "slack",
        "tool_name": "slack:read_recent_mentions",
        "activity_log_id": activity["id"],
        "summary": summary,
        "mentions": mentions,
    }


async def post_message_action(context: AgentContext, channel: str, text: str) -> dict[str, Any]:
    backend = BackendClient()
    risk = await backend.require_approval(context, "slack", "slack:post_message")
    if not risk["permission_allowed"]:
        return {
            "status": "blocked",
            "provider": "slack",
            "tool_name": "slack:post_message",
            "detail": "Slack posting is disabled.",
        }
    if risk["needs_approval"]:
        approval = await backend.request_approval(
            context,
            provider="slack",
            tool_name="slack:post_message",
            action="post_message",
            input={"channel": channel, "text": text},
        )

        async def performer() -> None:
            await _post_message(context, channel, text)

        schedule_after_approval(
            backend=backend,
            context=context,
            activity_log_id=approval["activity_log_id"],
            performer=performer,
        )
        return {
            "status": "pending_approval",
            "provider": "slack",
            "tool_name": "slack:post_message",
            "activity_log_id": approval["activity_log_id"],
            "authorization_request_id": approval["authorization_request_id"],
            "detail": approval["detail"],
            "approval_mode": approval.get("mode"),
        }
    try:
        payload = await _post_message(context, channel, text)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="slack",
            tool_name="slack:post_message",
            action="post_message",
            input_payload={"channel": channel, "text": text},
            detail=exc.detail,
        )
        return failed_result(
            provider="slack",
            tool_name="slack:post_message",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    activity = await backend.create_activity(
        context,
        provider="slack",
        tool_name="slack:post_message",
        action="post_message",
        input={"channel": channel, "text": text},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "slack",
        "tool_name": "slack:post_message",
        "activity_log_id": activity["id"],
        "message_ts": payload.get("ts"),
        "channel": payload.get("channel"),
    }


async def _resolve_user_names(access_token: str, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    settings = get_settings()
    resolved: dict[str, str] = {}
    for user_id in user_ids:
        payload = await request_json(
            provider="slack",
            method="GET",
            url=f"{settings.slack_api_base_url}/users.info",
            access_token=access_token,
            params={"user": user_id},
        )
        profile = payload.get("user", {})
        resolved[user_id] = profile.get("real_name") or profile.get("name") or user_id
    return resolved


async def _post_message(context: AgentContext, channel: str, text: str) -> dict[str, Any]:
    settings = get_settings()
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="slack")
    return await request_json(
        provider="slack",
        method="POST",
        url=f"{settings.slack_api_base_url}/chat.postMessage",
        access_token=access_token,
        json_body={"channel": channel, "text": text},
    )


@mcp.resource("slack://recent_mentions")
async def recent_mentions_resource() -> str:
    return await recent_mentions_text(default_server_context())


@mcp.tool(name="slack:post_message")
async def post_message(channel: str, text: str) -> dict[str, Any]:
    """Post a Slack message. Risk: medium."""
    return await post_message_action(default_server_context(), channel, text)


@mcp.tool(name="slack:read_recent_mentions")
async def read_recent_mentions() -> dict[str, Any]:
    """Read recent Slack mentions. Risk: low."""
    return await read_recent_mentions_action(default_server_context())


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
