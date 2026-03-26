from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.servers import calendar_server, github_server, gmail_server, slack_server, stripe_server


@dataclass(slots=True)
class ToolDescriptor:
    name: str
    provider: str
    risk: str
    description: str
    requires_connected_account: bool = True
    approval_mode: str = "policy"


@dataclass(slots=True)
class ResourceDescriptor:
    uri: str
    provider: str
    description: str


class ToolCatalog:
    def __init__(self):
        self._tool_handlers = {
            "gmail:read_inbox_summary": gmail_server.read_inbox_summary_action,
            "gmail:read_unpaid_clients": gmail_server.read_unpaid_clients_action,
            "gmail:draft_followup_email": gmail_server.draft_followup_email_action,
            "gmail:send_email": gmail_server.send_email_action,
            "calendar:read_upcoming_meetings": calendar_server.read_upcoming_meetings_action,
            "calendar:create_meeting": calendar_server.create_meeting_action,
            "github:read_open_issues": github_server.read_open_issues_action,
            "github:open_issue": github_server.open_issue_action,
            "stripe:read_recent_payments": stripe_server.read_recent_payments_action,
            "slack:read_recent_mentions": slack_server.read_recent_mentions_action,
            "stripe:create_payment_link": stripe_server.create_payment_link_action,
            "slack:post_message": slack_server.post_message_action,
        }
        self._resource_handlers = {
            "gmail://recent_invoices": gmail_server.recent_invoices_text,
            "gmail://unpaid_clients": gmail_server.unpaid_clients_text,
            "calendar://upcoming_meetings": calendar_server.upcoming_meetings_text,
            "stripe://recent_payments": stripe_server.recent_payments_text,
            "slack://recent_mentions": slack_server.recent_mentions_text,
        }

    def list_tools(self) -> list[ToolDescriptor]:
        raw = {}
        raw.update(gmail_server.TOOLS)
        raw.update(calendar_server.TOOLS)
        raw.update(github_server.TOOLS)
        raw.update(stripe_server.TOOLS)
        raw.update(slack_server.TOOLS)
        return [ToolDescriptor(name=name, **payload) for name, payload in raw.items()]

    def list_resources(self) -> list[ResourceDescriptor]:
        raw = {}
        raw.update(gmail_server.RESOURCES)
        raw.update(calendar_server.RESOURCES)
        raw.update(github_server.RESOURCES)
        raw.update(stripe_server.RESOURCES)
        raw.update(slack_server.RESOURCES)
        return [ResourceDescriptor(uri=uri, **payload) for uri, payload in raw.items()]

    async def call_tool(self, name: str, context: AgentContext, **kwargs: Any) -> Any:
        return await self._tool_handlers[name](context, **kwargs)

    async def read_resource(self, uri: str, context: AgentContext) -> str:
        return await self._resource_handlers[uri](context)
